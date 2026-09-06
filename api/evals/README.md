# AI Notebooks — Evaluation Dataset

This directory contains a **manually curated golden dataset** of 21 evaluation
cases used to test the RAG pipeline (retrieval + answer generation + citation
quality).

## Files

| File | Purpose |
|---|---|
| `golden_dataset.py` | Defines `EvalCase` pydantic model + the 21-case `CASES` list |
| `__init__.py` | Re-exports `CASES` and `EvalCase` |
| `bootstrap_notebook.py` | Script that creates a fresh "Eval Test Notebook" and indexes the PDFs |
| `1512.03385v1.pdf` | Reference PDF 1 — "Deep Residual Learning for Image Recognition" (He et al., 2015) |
| `1706.03762v7.pdf` | Reference PDF 2 — "Attention Is All You Need" (Vaswani et al., 2017) |
| `.test_notebook.json` | (Generated) Holds the IDs of the bootstrap-created notebook & sources |

> **Note** — the PDF filenames are the arXiv IDs, which are misleading:
> `1512.03385v1.pdf` is the ResNet paper, and `1706.03762v7.pdf` is the
> Transformer paper. The eval cases treat them by filename, so do not rename
> the PDFs.

## Case categories

The 21 cases split into 4 categories per the project spec:

| Category | Count | What it tests |
|---|---|---|
| `factual` | 5 | Single-fact lookup (e.g. "What is `d_model`?") |
| `summarization` | 4 | Synthesize a section or concept |
| `multi-hop` | 4 | Combine information from multiple sections/pages |
| `visual` | 5 | Answer requires reading a figure/table/diagram |
| `adversarial` (subset) | 3 | Topic is NOT in the PDFs — pipeline should refuse to answer |

Adversarial cases have `expected_source_files=[]` and `is_adversarial=True`.
The harness should treat them as passing when the model emits a "I couldn't
find relevant information"-style refusal.

## How to set up the test notebook

You need a notebook that contains both reference PDFs so the RAG pipeline can
retrieve from them. There are two ways to set this up.

### Option A — automated (recommended)

Run the bootstrap script from the `api/` directory:

```bash
cd api
python -m evals.bootstrap_notebook
```

This will:
1. Create (or find) a notebook titled "Eval Test Notebook" in MongoDB.
2. Upload each PDF in this directory to GridFS.
3. Trigger background ingestion for each source.
4. Poll until every source reaches `status="ready"` (max 5 min).
5. Write the resulting `notebook_id` and per-source `source_id` to
   `evals/.test_notebook.json`.

The script is **idempotent** — re-running it will reuse the existing notebook
and skip already-indexed sources.

**Requirements:** the FastAPI backend's standard environment variables
(`MONGODB_URI`, `MONGODB_DB`, `QDRANT_URL`, `QDRANT_API_KEY`,
`AZURE_OPENAI_*`, `NVIDIA_API_KEY`) must be set in `api/.env`.

### Option B — manual (via the FastAPI HTTP API)

Start the backend (`npm run backend` from the repo root, or
`uvicorn index:app --port 8001` from `api/`), then:

```bash
# 1. Create a notebook
NOTEBOOK_ID=$(curl -s -X POST http://127.0.0.1:8001/notebooks \
  -H "Content-Type: application/json" \
  -d '{"title":"Eval Test Notebook"}' | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Upload the two reference PDFs
curl -X POST "http://127.0.0.1:8001/notebooks/$NOTEBOOK_ID/sources" \
  -F "file=@api/evals/1512.03385v1.pdf"

curl -X POST "http://127.0.0.1:8001/notebooks/$NOTEBOOK_ID/sources" \
  -F "file=@api/evals/1706.03762v7.pdf"

# 3. (optional) Wait for ingestion to complete
curl -s "http://127.0.0.1:8001/notebooks/$NOTEBOOK_ID/sources" \
  | python -m json.tool
```

All sources should eventually show `"status": "ready"` in the GET response.

## Using the dataset

```python
from evals.golden_dataset import CASES, EvalCase

print(f"{len(CASES)} cases total")  # 21

# Group by category
from collections import Counter
counts = Counter(c.category for c in CASES)
print(counts)  # Counter({'visual': 5, 'factual': 5, 'summarization': 4, 'multi-hop': 4})

# Adversarial cases
adversarial = [c for c in CASES if c.is_adversarial]
print(len(adversarial))  # 3
```

To run an eval, your harness should:
1. Read `notebook_id` from `.test_notebook.json` (or accept it as an arg).
2. For each `EvalCase`, call `POST /notebooks/{notebook_id}/chat` with the
   `query`.
3. Score the streamed response against `expected_answer_keywords`,
   `expected_source_files`, and `expected_pages` (when applicable).
4. For `is_adversarial=True` cases, expect a refusal rather than an answer.

## Verifying the dataset

From the `api/` directory:

```bash
python -c "from evals.golden_dataset import CASES, EvalCase; print(f'{len(CASES)} cases'); [EvalCase(**c.model_dump()) for c in CASES]; print('All cases valid')"
```

Should output `21 cases` followed by `All cases valid`.

## Adding new cases

1. Add the new `EvalCase` to the `CASES` list in `golden_dataset.py`.
2. Use a stable kebab-case `id` slug (e.g. `factual-…`, `visual-…`,
   `adversarial-…`).
3. Keep `expected_answer_keywords` to 3–5 *concrete* facts from the source —
   not generic terms like "the" or "results".
4. If the case is for a new PDF, drop the file in this directory and update
   the source filename in `expected_source_files`. The
   `bootstrap_notebook.py` script auto-discovers new PDFs.
5. Re-run the verification command above to confirm all cases still load.
