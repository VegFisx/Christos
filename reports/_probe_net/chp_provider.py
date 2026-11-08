from typing import Any
from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from http import HTTPStatus
import dashscope


class ChinesePharmacopoeiaProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            dashscope.api_key = credentials.get("dashscope_api_key")
            # 测试是否会产生异常
            messages = [{'role': 'system', 'content': '你是一个AI助手，请用中文回答问题。'},
                        {'role': 'user', 'content': '给《中国药典》写一个简短的概述。'}]

            response = dashscope.Generation.call(
                model='qwen-plus',
                messages=messages,
                result_format='message',  # set the result to be "message" format.
            )

            if response.status_code == HTTPStatus.OK:
                print(response.output.choices[0].message.content)
            else:
                print('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
                    response.request_id, response.status_code,
                    response.code, response.message
                ))

        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e))


    #########################################################################################
    # If OAuth is supported, uncomment the following functions.
    # Warning: please make sure that the sdk version is 0.4.2 or higher.
    #########################################################################################
    # def _oauth_get_authorization_url(self, redirect_uri: str, system_credentials: Mapping[str, Any]) -> str:
    #     """
    #     Generate the authorization URL for chinese_pharmacopoeia OAuth.
    #     """
    #     try:
    #         """
    #         IMPLEMENT YOUR AUTHORIZATION URL GENERATION HERE
    #         """
    #     except Exception as e:
    #         raise ToolProviderOAuthError(str(e))
    #     return ""
        
    # def _oauth_get_credentials(
    #     self, redirect_uri: str, system_credentials: Mapping[str, Any], request: Request
    # ) -> Mapping[str, Any]:
    #     """
    #     Exchange code for access_token.
    #     """
    #     try:
    #         """
    #         IMPLEMENT YOUR CREDENTIALS EXCHANGE HERE
    #         """
    #     except Exception as e:
    #         raise ToolProviderOAuthError(str(e))
    #     return dict()

    # def _oauth_refresh_credentials(
    #     self, redirect_uri: str, system_credentials: Mapping[str, Any], credentials: Mapping[str, Any]
    # ) -> OAuthCredentials:
    #     """
    #     Refresh the credentials
    #     """
    #     return OAuthCredentials(credentials=credentials, expires_at=-1)
