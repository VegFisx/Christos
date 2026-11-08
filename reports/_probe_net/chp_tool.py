from collections.abc import Generator
from typing import Any
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

import dashscope
from http import HTTPStatus

from dotenv import load_dotenv
import os
import json
import requests
from pathlib import Path


class ChpSearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:

        dashscope.api_key = self.runtime.credentials.get("dashscope_api_key")

        try:
            # embedding
            query = tool_parameters.get("query")

            response = dashscope.TextEmbedding.call(
                model="text-embedding-v4",
                input=str(query),
                dimension=1024,
                output_type="dense&sparse"
            )
            query_embedding = []
            if response.status_code == HTTPStatus.OK:
                query_embedding = response.output["embeddings"][0]["embedding"]
            else:
                yield self.create_text_message("query embedding error")
                return

            # search zilliz cloud
            current_file = Path(__file__).absolute()
            parent_dir = current_file.parent.parent
            env_dir = os.path.join(parent_dir, ".env")
            load_dotenv(env_dir)
            token = os.getenv("ZILLIZ_CLOUD_TOKEN")
            url = os.getenv("ZILLIZ_CLOUD_URL")
            if token is None or url is None:
                yield self.create_text_message("zilliz cloud token or url is None")
                return

            url = f"{url}/v2/vectordb/entities/search"
            payload = {"collectionName": "yaodian_collection", "data": [query_embedding], "limit": 10,
                       "outputFields": ["*"]}
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            search_res = []
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            if response and response.json().get("code") == 0:
                search_res = response.json().get("data")
                if len(search_res) == 0:
                    yield self.create_text_message("no search result")
            else:
                yield self.create_text_message("query search error")
                return

            # re-rank
            # documents = [res.entity.name for res in search_res]
            documents = self._handle_rerank(search_res)
            num = tool_parameters.get("limit", 1)
            response = dashscope.TextReRank.call(
                model="gte-rerank-v2",
                query=query,
                documents=documents,
                top_n=num,
                return_documents=True
            )

            if response.status_code == HTTPStatus.OK:
                final_result = ""
                for res in response.output.results:
                    index = res.index
                    final_result += "### " + search_res[index].get("name") + "\n" + search_res[index].get("content")
                    final_result += "\n\n\n\n\n"
                    final_result += "\n---\n"
                yield self.create_text_message(final_result)
            else:
                yield self.create_text_message("query rerank error")
        except Exception as e:
            yield self.create_text_message(f"error: {e}")

    def _handle_rerank(self, search_res: list[dict[str, Any]]):
        """
        process rerank inputs
        :return:
        """

        documents = []
        for res in search_res:
            name = res.get("name")
            content = res.get("content")
            documents.append(name + "\n" + content)
        return documents
