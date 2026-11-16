# AI Notebooks — RAG evaluation (pydantic_evals)

A `pydantic_evals` suite that runs the real pipeline (`prepare_answer` →
context-support gate → streamed answer, the same flow as `routes/chat.py`)
over **34 cases** on two reference papers.

## Dataset

`golden_dataset.py` holds the cases; `build_dataset(notebook_id)` turns them into a
`pydantic_evals.Dataset` of `Case` objects
(`inputs` = question + notebook_id; `metadata` = category, expected `(file, page)` sources,
`is_adversarial`).

| Category | Cases |
|---|---|
| factual | 5 |
| summarization | 4 |
| multi-hop | 5 |
| visual | 5 |
| adversarial | 15 (3 original, 4 plain off-topic, 8 "tempting") |
| **total** | **34** (19 answerable + 15 adversarial) |

"Tempting" adversarial cases name real models/metrics or mix the two papers but ask for
facts that are not in either PDF (e.g. Transformer on WMT16 En-Ro, ResNet-152 parameter
count, BERT, carbon footprint). Absence was checked against the PDF text.

## Metrics

| Metric | Evaluator | Applies to |
|---|---|---|
| Recall@5, MRR | `RecallAt5`, `ReciprocalRank` (custom) | answerable (19), over reranked docs |
| Citation accuracy | `CitationAccuracy` (custom) | answerable |
| Refusal correctness | `RefusalCorrect` (custom) | all 34 |
| Faithfulness | `FaithfulnessJudge` (`LLMJudge`) | answerable and not refused |
| Answer relevance | `RelevanceJudge` (`LLMJudge`) | answerable (a refusal scores ~0) |

Reported separately: adversarial refusal rate (n=15) and false-refusal rate (n=19).
Every metric prints `n` (scored), failed, and not-applicable counts; nothing leaves an
average without being counted. Judge failures are evaluator failures (not dropped), and the
count is printed and makes the process exit non-zero.

The judge sees the question and the answer plus the retrieved context text, and **must be
a different model** from the answer model (`EVAL_JUDGE_MODEL`, checked at startup).

## Run

From `api/`, with `api/.env` configured (MongoDB, Qdrant, Azure OpenAI, NVIDIA):

```bash
python -m evals.fetch_reference_pdfs          # downloads + SHA-256-verifies the two papers
python -m evals.bootstrap_notebook            # creates/indexes the eval notebook
export EVAL_JUDGE_MODEL=azure:<other-deployment>   # must differ from AZURE_OPENAI_CHAT_DEPLOYMENT
python -m evals.run_evals                     # 3 runs; writes evals/results/<UTC timestamp>.json
```

Options: `--repeat N`, `--max-concurrency N`, `--notebook-id ID`, `--out-dir DIR`.
Eval runs are traced to Logfire (`eval.suite` span, pydantic_evals experiments, judge calls).

The results file holds mean/std/min/max across runs for every metric (overall and per
category) plus each run's per-case scores, judge reasons, failures and full pipeline output.
`evals/results/` is tracked in git; `*.pdf` and `.test_notebook.json` are not.

## Offline tests

```bash
python -m pytest        # from api/; no network or credentials needed
```

They run the real Dataset and evaluators against a stubbed pipeline and a fake judge.
