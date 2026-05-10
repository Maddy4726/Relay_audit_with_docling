# relay_section_detector

Semantic **section segmentation** for industrial relay testing reports: PDF → Docling markdown → numbered lines → overlapping chunks → OpenAI-compatible LLM → merged `sections.json`.

This project intentionally does **not** implement auditing, pass/fail logic, value extraction, or schema validation.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Put a PDF under samples/ (default: samples/report.pdf) and set RELAY_LLM_API_KEY
```

## Run

```bash
python3 main.py                 # uses RELAY_PDF_PATH / default PDF path
python3 main.py /path/to.pdf    # override PDF path
```

Outputs:

- `output/raw_markdown.md` — Docling markdown
- `output/sections.json` — merged semantic sections
