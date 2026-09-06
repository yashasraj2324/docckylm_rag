"""
Generation-layer evaluation: Faithfulness, Answer Relevance, Citation Accuracy,
Keyword Coverage.

This module evaluates the full RAG pipeline (retrieval + LLM) in the same way
a user would experience it.  For each non-adversarial EvalCase it:
  1. Calls prepare_answer() to get context + citations (no LLM yet).
  2. Streams the answer from the chat model, collecting the full text.
  3. Scores with LLM-as-judge: Faithfulness and Answer Relevance.
  4. Computes Citation Accuracy deterministically.
  5. Computes Keyword Coverage deterministically.

Adversarial cases are handled separately: no context → judge skips
faithfulness; citation accuracy checks for absence of citations.

Usage (run from the ``api/`` directory):

    python -m evals.generation_eval [--notebook-id ID] [--verbose]

The script reads ``evals/.test_notebook.json`` to get the notebook_id.
If the file does not exist, run ``python -m evals.bootstrap_notebook`` first.

Environment: standard FastAPI env vars are required
  (MONGODB_URI, QDRANT_URL, QDRANT_API_KEY, AZURE_OPENAI_*,
   NVIDIA_API_KEY, QDRANT_COLLECTION_NAME).
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Ensure this package is importable when running from api/
_script_dir = Path(__file__).parent.resolve()
_api_dir = _script_dir.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

import logfire
from telemetry import init_telemetry

# Logfire must be configured before any logfire.span() call.
# send_to_logfire="if-token-present" makes this safe even when LOGFIRE_TOKEN is unset.
init_telemetry(app=None)

from evals.golden_dataset import CASES, EvalCase
from evals.prompts import ANSWER_RELEVANCE_PROMPT, FAITHFULNESS_PROMPT

from ingestion.embedder import get_embedding_model
from llm.chat_model import get_chat_model
from pipeline.query import prepare_answer, stream_answer

EVAL_DIR = _script_dir
CONFIG_PATH = EVAL_DIR / ".test_notebook.json"

# Keywords that indicate a "no context" / adversarial refusal.
_REFUSAL_PATTERNS = [
    "couldn't find relevant information",
    "could not find relevant information",
    "i don't have access to",
    "i do not have access to",
    "not in your sources",
    "no relevant information",
    "not found in your",
    "unable to find",
    "cannot find relevant",
]


# =============================================================================
# Citation parsing
# =============================================================================


def _extract_filename_from_citation(citation: str) -> str:
    """
    Extract the source filename from a citation string produced by _format_citation().

    Format options:
      - "filename — Page N"
      - "filename — Asset XYZ"
      - "filename"
    """
    # Strip " — Page N" or " — Asset ..." suffix
    name = re.sub(r"\s*—\s*Page\s*\d+.*", "", citation)
    name = re.sub(r"\s*—\s*Asset.*", "", name)
    return name.strip()


def _extract_cited_files(sources: list[str]) -> set[str]:
    """Return the set of filenames cited in the answer."""
    return {_extract_filename_from_citation(c) for c in sources if c.strip()}


# =============================================================================
# Deterministic scores
# =============================================================================


def _citation_accuracy(
    cited_files: set[str], case: EvalCase
) -> float:
    """
    Deterministic citation accuracy score.

    Rules:
      - If expected_source_files is empty (adversarial), return 1.0 only if
        no citations were produced.
      - Otherwise: fraction of expected files that were cited, minus 0.2 per
        false positive citation (floored at 0.0).
    """
    expected = set(case.expected_source_files)

    if not expected:
        # Adversarial / no-ground-truth case
        return 1.0 if not cited_files else 0.0

    if not cited_files:
        return 0.0

    true_positives = len(expected & cited_files)
    false_positives = len(cited_files - expected)

    score = true_positives / len(expected) - 0.2 * false_positives
    return max(0.0, score)


def _keyword_coverage(answer: str, case: EvalCase) -> float:
    """
    Deterministic keyword coverage score.

    Returns the fraction of expected_answer_keywords present in the answer
    (case-insensitive substring match).
    """
    if not case.expected_answer_keywords:
        return 1.0  # nothing to match

    answer_lower = answer.lower()
    found = sum(
        1 for kw in case.expected_answer_keywords if kw.lower() in answer_lower
    )
    return found / len(case.expected_answer_keywords)


# =============================================================================
# LLM judge
# =============================================================================


def _score_with_judge(
    prompt_template: str,
    query: str,
    context: str,
    answer: str,
    chat_model,
) -> float | None:
    """
    Call the LLM judge with the given prompt template and return a float score.

    Parses the first float found in the model's response.  Returns None on
    parse failure (logs a warning and returns None — the caller skips the
    score).
    """
    try:
        prompt = prompt_template.format(query=query, context=context, answer=answer)
    except KeyError:
        # Prompt template may not use all of the kwargs
        prompt = prompt_template.format(query=query, answer=answer)
    try:
        with logfire.span("eval.judge_call", prompt_length=len(prompt)):
            response = chat_model.invoke(prompt)
        text = response.content.strip()
        # Try to extract a float from the response
        match = re.search(r"0?\.\d+|1\.0+|[01](?:\.0+)?", text)
        if match:
            return float(match.group(0))
        logfire.warn("Judge response did not contain a parseable score", response=text)
        return None
    except Exception as exc:
        logfire.error("Judge call failed", error=str(exc))
        return None


# =============================================================================
# Per-case evaluation
# =============================================================================


class GenerationResult:
    """Results for one eval case."""

    __slots__ = (
        "faithfulness",
        "relevance",
        "citation_accuracy",
        "keyword_coverage",
        "has_context",
        "is_refusal",
    )

    def __init__(self) -> None:
        self.faithfulness: float | None = None
        self.relevance: float | None = None
        self.citation_accuracy: float | None = None
        self.keyword_coverage: float | None = None
        self.has_context: bool = False
        self.is_refusal: bool = False


def _is_refusal(answer: str) -> bool:
    return any(pat in answer.lower() for pat in _REFUSAL_PATTERNS)


def evaluate_case(
    case: EvalCase,
    notebook_id: str,
    chat_model,
    embedding_model,
) -> GenerationResult:
    """
    Evaluate a single EvalCase against the live RAG pipeline.

    Returns a GenerationResult with all four scores (faithfulness, relevance,
    citation_accuracy, keyword_coverage) and the has_context / is_refusal flags.
    """
    result = GenerationResult()

    with logfire.span("eval.prepare_context", case_id=case.id, category=case.category):
        try:
            prompt, citations, context, has_context = prepare_answer(
                embedding_model,
                case.query,
                notebook_id,
                history=None,
                asset_loader=None,
            )
        except Exception as exc:
            logfire.error("prepare_answer failed", case_id=case.id, error=str(exc))
            result.is_refusal = True
            return result

    result.has_context = has_context

    if not has_context:
        # No context retrieved at all
        result.is_refusal = True
        return result

    # Stream the answer
    answer_chunks: list[str] = []
    with logfire.span("eval.stream_answer", case_id=case.id):
        for chunk in stream_answer(chat_model, prompt):
            answer_chunks.append(chunk)

    answer_text = "".join(answer_chunks)
    result.is_refusal = _is_refusal(answer_text)

    # Parse citations
    cited_files = _extract_cited_files(citations)

    # ── Deterministic scores ────────────────────────────────────────────────
    result.citation_accuracy = _citation_accuracy(cited_files, case)
    result.keyword_coverage = _keyword_coverage(answer_text, case)

    # ── LLM judge scores ────────────────────────────────────────────────────
    if case.is_adversarial:
        # Adversarial: skip faithfulness, score relevance as refusal-check
        if result.is_refusal:
            result.faithfulness = None  # N/A for adversarial
            result.relevance = 1.0
        else:
            # Hallucination: gave an answer when it shouldn't have
            result.faithfulness = None
            result.relevance = 0.0
    else:
        # Normal case: judge faithfulness + relevance
        result.faithfulness = _score_with_judge(
            FAITHFULNESS_PROMPT, case.query, context, answer_text, chat_model
        )
        result.relevance = _score_with_judge(
            ANSWER_RELEVANCE_PROMPT, case.query, context, answer_text, chat_model
        )

    return result


# =============================================================================
# Metrics aggregation
# =============================================================================


class GenerationMetrics:
    """Accumulates mean scores for a group of eval cases."""

    __slots__ = (
        "faithfulness_sum",
        "relevance_sum",
        "citation_sum",
        "keyword_sum",
        "faithfulness_count",
        "relevance_count",
        "citation_count",
        "keyword_count",
        "count",
    )

    def __init__(self) -> None:
        self.faithfulness_sum: float = 0.0
        self.faithfulness_count: int = 0
        self.relevance_sum: float = 0.0
        self.relevance_count: int = 0
        self.citation_sum: float = 0.0
        self.citation_count: int = 0
        self.keyword_sum: float = 0.0
        self.keyword_count: int = 0
        self.count: int = 0

    def update(self, r: GenerationResult) -> None:
        if r.faithfulness is not None:
            self.faithfulness_sum += r.faithfulness
            self.faithfulness_count += 1
        if r.relevance is not None:
            self.relevance_sum += r.relevance
            self.relevance_count += 1
        if r.citation_accuracy is not None:
            self.citation_sum += r.citation_accuracy
            self.citation_count += 1
        if r.keyword_coverage is not None:
            self.keyword_sum += r.keyword_coverage
            self.keyword_count += 1
        self.count += 1

    def mean(self) -> dict[str, float]:
        def _mean(total: float, n: int) -> float:
            return (total / n) if n > 0 else float("nan")

        return {
            "Faithfulness": _mean(self.faithfulness_sum, self.faithfulness_count),
            "Relevance": _mean(self.relevance_sum, self.relevance_count),
            "Citation Accuracy": _mean(self.citation_sum, self.citation_count),
            "Keyword Coverage": _mean(self.keyword_sum, self.keyword_count),
            "N": float(self.count),
        }


# =============================================================================
# Table formatting
# =============================================================================


def _format_table(
    category_metrics: dict[str, GenerationMetrics],
    overall: GenerationMetrics,
) -> None:
    cats = ["factual", "summarization", "multi-hop", "visual"]
    cat_labels = [c.capitalize() for c in cats]
    fields = ["Faithfulness", "Relevance", "Citation Accuracy", "Keyword Coverage"]

    col_w = [20, 12, 12, 12, 12, 12, 12]
    headers = ["Category", "Faithful.", "Relevance", "Cit. Acc.", "Kw. Cover", "N"]
    sep = "  " + "-" * (sum(col_w) + len(col_w) - 1)

    def fmt_row(label: str, m: GenerationMetrics) -> str:
        vals = m.mean()
        parts = [label]
        for f in fields:
            v = vals[f]
            parts.append(f"{v:.3f}" if v == v else "N/A")  # nan-check
        parts.append(f"{int(vals['N'])}")
        return "  " + "  ".join(p.rjust(w) for p, w in zip(parts, col_w))

    print()
    print("  Generation Evaluation Summary")
    print("  " + "=" * 90)
    print("  " + "  ".join(h.rjust(w) for h, w in zip(headers, col_w)))
    print(sep)
    for label, cat in zip(cat_labels, cats):
        print(fmt_row(label, category_metrics[cat]))
    print(sep)
    print(fmt_row("Overall", overall))
    print("  " + "=" * 90)
    print()
    print("  Note: Faithfulness and Relevance are scored by LLM-as-judge.")
    print("        Citation Accuracy and Keyword Coverage are deterministic.")
    print()


# =============================================================================
# Main
# =============================================================================


def main(notebook_id: str | None = None, verbose: bool = False) -> dict:
    if notebook_id is None:
        config = CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(config)
        notebook_id = data["notebook_id"]
        print(f"[generation_eval] Using notebook_id from config: {notebook_id}")

    chat_model = get_chat_model()
    embedding_model = get_embedding_model()

    category_metrics: dict[str, GenerationMetrics] = defaultdict(GenerationMetrics)
    per_case: dict[str, dict] = {}

    non_adversarial = [c for c in CASES if not c.is_adversarial]
    all_cases = [c for c in CASES]  # includes adversarial for counting
    total = len(all_cases)
    n_adv = sum(1 for c in all_cases if c.is_adversarial)
    print(
        f"[generation_eval] Running generation eval for {len(non_adversarial)} "
        f"non-adversarial cases ({n_adv} adversarial, {total} total)..."
    )

    with logfire.span(
        "eval.generation_run",
        case_count=len(non_adversarial),
        notebook_id=notebook_id,
    ):
        for case in CASES:
            with logfire.span("eval.case", case_id=case.id, category=case.category):
                try:
                    result = evaluate_case(
                        case, notebook_id, chat_model, embedding_model
                    )
                except Exception as exc:
                    print(f"[generation_eval] ERROR on case '{case.id}': {exc}")
                    logfire.error("Generation eval case failed", case_id=case.id, error=str(exc))
                    continue

                # Adversarial cases are excluded from per-category metrics per the spec.
                if not case.is_adversarial:
                    category_metrics[case.category].update(result)

                if verbose:
                    ctx = ""
                    if result.faithfulness is not None:
                        ctx += f"Faith={result.faithfulness:.2f} "
                    else:
                        ctx += "Faith=N/A "
                    ctx += f"Rel={result.relevance:.2f} " if result.relevance is not None else "Rel=N/A "
                    ctx += f"CitAcc={result.citation_accuracy:.2f} "
                    ctx += f"KwCov={result.keyword_coverage:.2f} "
                    ctx += f"[refusal={result.is_refusal}]"
                    print(f"  [{case.category:<12}] {case.id:<50s}  {ctx}")

                per_case[case.id] = {
                    "category": case.category,
                    "is_adversarial": case.is_adversarial,
                    "has_context": result.has_context,
                    "is_refusal": result.is_refusal,
                    "faithfulness": result.faithfulness,
                    "relevance": result.relevance,
                    "citation_accuracy": result.citation_accuracy,
                    "keyword_coverage": result.keyword_coverage,
                }

    # Aggregate overall (adversarial cases are not in category_metrics)
    overall = GenerationMetrics()
    for cat in ["factual", "summarization", "multi-hop", "visual"]:
        m = category_metrics[cat]
        for key in (
            "faithfulness_sum",
            "relevance_sum",
            "citation_sum",
            "keyword_sum",
        ):
            setattr(overall, key, getattr(overall, key) + getattr(m, key))
        for key in (
            "faithfulness_count",
            "relevance_count",
            "citation_count",
            "keyword_count",
            "count",
        ):
            setattr(overall, key, getattr(overall, key) + getattr(m, key))

    _format_table(category_metrics, overall)

    return {
        "category_metrics": {k: v.mean() for k, v in category_metrics.items()},
        "overall": overall.mean(),
        "per_case": per_case,
    }


if __name__ == "__main__":
    notebook_id_arg: str | None = None
    verbose = False

    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print("Usage: python -m evals.generation_eval [--notebook-id ID] [--verbose]")
        print()
        print("Options:")
        print("  --notebook-id ID  Override the notebook_id (default: read from evals/.test_notebook.json)")
        print("  --verbose         Print one line per eval case")
        print("  --help, -h        Show this help message")
        sys.exit(0)

    i = 0
    while i < len(args):
        if args[i] == "--notebook-id" and i + 1 < len(args):
            notebook_id_arg = args[i + 1]
            i += 2
        elif args[i] == "--verbose":
            verbose = True
            i += 1
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            sys.exit(1)

    if not CONFIG_PATH.exists():
        print(
            f"[generation_eval] ERROR: {CONFIG_PATH} not found.",
            file=sys.stderr,
        )
        print(
            "  Run 'python -m evals.bootstrap_notebook' first to create the test notebook.",
            file=sys.stderr,
        )
        sys.exit(1)

    main(notebook_id=notebook_id_arg, verbose=verbose)
