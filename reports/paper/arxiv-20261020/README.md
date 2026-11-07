# Christos arXiv package (working directory)

This directory is a separate arXiv packaging copy of the English system paper.
It does not overwrite the DSH audit draft or the Chinese translation.

Files:

- `manuscript.md` — English manuscript with five embedded figures;
- `paper-en.css` — A4 print stylesheet;
- `figures/` — five English figures copied from `figures-system-20261020/en/`;
- `arxiv-submission.md` — metadata and final fill-in checklist.

Build the PDF:

```powershell
pandoc manuscript.md --from markdown+pipe_tables --to html5 --standalone `
  --css paper-en.css --metadata pagetitle="Christos arXiv manuscript" `
  --output manuscript.html

msedge.exe --headless=new --disable-gpu --no-first-run `
  --no-pdf-header-footer --print-to-pdf=manuscript.pdf `
  "file:///D:/ProgramData/DSHNS/chemreact-staging/reports/paper/arxiv-20261020/manuscript.html"
```

The PDF is a preprint draft with author and repository placeholders. Fill
`arxiv-submission.md` and the matching manuscript fields before uploading.
