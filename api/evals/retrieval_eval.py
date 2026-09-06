"""
Retrieval-layer evaluation: Recall@12, Recall@5, Precision@5, MRR.

This module evaluates the retrieval + reranking pipeline in isolation from the LLM.
For each non-adversarial EvalCase it:
  1. Embeds the query and retrieves top-12 docs from Qdrant (notebook-filtered).
  2. Reranks with the NVIDIA reranker to top-5.
  3. Compares the retrieved docs against expected_source_files and expected_pages.
  4. Computes Recall@12, Recall@5, Precision@5, MRR.

Results are printed as a per-category and overall summary table.

Usage (run from the ``api/`` directory):

    python -m evals.retrieval_eval

The script reads ``evals/.test_notebook.json`` to get the notebook_id.
If the file does not exist, run ``python -m evals.bootstrap_notebook`` first.

Environment: standard FastAPI env vars are required
  (MONGODB_URI, QDRANT_URL, QDRANT_API_KEY, AZURE_OPENAI_*,
   NVIDIA_API_KEY, QDRANT_COLLECTION_NAME).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from langchain_core.documents import Document

from evals.golden_dataset import CASES, EvalCase

from ingestion.embedder import get_embedding_model
from retrieval.reranker import rerank_documents
from vectorstore.qdrant_db import (
    ensure_payload_indexes,
    get_vectorstore,
    notebook_filter,
)

EVAL_DIR = _script_dir
CONFIG_PATH = EVAL_DIR / ".test_notebook.json"
DEFAULT_K_RETRIEVE = 12  # matches query.py


# ----------------------------------------------------------------------------
# Relevance helpers
# ----------------------------------------------------------------------------


def _is_relevant(doc: "Document", case: EvalCase) -> bool:
    """
    Determine whether a retrieved document is relevant to the eval case.

    A doc is relevant iff:
      - Its file_name is in expected_source_files, AND
      - If expected_pages is set, its page number is in expected_pages.

    Chunks that span multiple pages carry a "pages" list in metadata (the
    first page is stored under the "page" key by the splitter, so we check
    that directly per the spec).
    """
    if not case.expected_source_files:
        return False

    file_name = doc.metadata.get("file_name") or doc.metadata.get("source", "")
    if file_name not in case.expected_source_files:
        return False

    if case.expected_pages is not None:
        page = doc.metadata.get("page")
        if page is None:
            return False
        # page is stored as int by PyMuPDF4LLMLoader
        if int(page) not in case.expected_pages:
            return False

    return True


def _build_relevant_set(case: EvalCase) -> set[tuple[str, int]]:
    """
    Build the universe of (file_name, page) pairs that are relevant.

    Used as the denominator for Recall@k — we need to know *all* relevant
    docs, not just the ones we retrieved.  Since we only know the pages
    from the eval case, we use (file_name, page) as the identity for each
    relevant chunk.
    """
    relevant: set[tuple[str, int]] = set()
    if not case.expected_source_files:
        return relevant
    pages = case.expected_pages if case.expected_pages is not None else [None]
    for fname in case.expected_source_files:
        for pg in pages:
            relevant.add((fname, pg))
    return relevant


# ----------------------------------------------------------------------------
# Retrieval (no LLM)
# ----------------------------------------------------------------------------


def run_retrieval(query: str, notebook_id: str, embedding_model) -> tuple[list["Document"], list["Document"]]:
    """
    Run the retrieval + reranking pipeline and return both the raw top-12
    results and the reranked top-5 results.

    This function intentionally mirrors query.py's prepare_answer() but stops
    before the LLM call, returning only the retrieved Document lists.

    Args:
        query:         The user question string.
        notebook_id:   The notebook to search within.
        embedding_model: An initialized AzureOpenAIEmbeddings model instance.

    Returns:
        (pre_rerank_docs, reranked_docs):
          - pre_rerank_docs: up to 12 docs from Qdrant (before reranking)
          - reranked_docs:   up to 5  docs after NVIDIA reranking
    """
    ensure_payload_indexes()
    vectorstore = get_vectorstore(embedding_model)

    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": DEFAULT_K_RETRIEVE,
            "filter": notebook_filter(notebook_id),
        }
    )

    with logfire.span("eval.qdrant_retrieve", k=DEFAULT_K_RETRIEVE, notebook_id=notebook_id):
        pre_rerank_docs = retriever.invoke(query)

    with logfire.span("eval.rerank", candidate_count=len(pre_rerank_docs)):
        reranked_docs = rerank_documents(query, pre_rerank_docs)

    return pre_rerank_docs, reranked_docs


# ----------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------


class RetrievalMetrics:
    """Accumulates metrics for a group of eval cases."""

    __slots__ = ("recall_at_12", "recall_at_5", "precision_at_5", "mrr", "count")

    def __init__(self) -> None:
        self.recall_at_12: float = 0.0
        self.recall_at_5: float = 0.0
        self.precision_at_5: float = 0.0
        self.mrr: float = 0.0
        self.count: int = 0

    def update(
        self,
        pre_rerank: list["Document"],
        reranked: list["Document"],
        case: EvalCase,
    ) -> None:
        relevant_set = _build_relevant_set(case)
        if not relevant_set:
            return  # adversarial or degenerate — skip

        def _doc_pair(doc: "Document") -> tuple[str, int] | None:
            fname = doc.metadata.get("file_name") or doc.metadata.get("source")
            page = doc.metadata.get("page")
            if fname is None or page is None:
                return None
            return (fname, int(page))

        # Recall@12: distinct (file, page) pairs in top-12 that overlap the relevant set
        pre_pairs = {_doc_pair(d) for d in pre_rerank[:12]}
        pre_pairs.discard(None)
        pre_hits = pre_pairs & relevant_set
        self.recall_at_12 += len(pre_hits) / len(relevant_set)

        # Recall@5: same after reranking
        reranked_5 = reranked[:5]
        reranked_pairs = {_doc_pair(d) for d in reranked_5}
        reranked_pairs.discard(None)
        reranked_hits = reranked_pairs & relevant_set
        self.recall_at_5 += len(reranked_hits) / len(relevant_set)

        # Precision@5: per-doc check (per IR convention — fraction of top-k slots
        # that are individually relevant)
        per_doc_relevant = sum(1 for d in reranked_5 if _is_relevant(d, case))
        self.precision_at_5 += per_doc_relevant / 5

        # MRR: 1 / rank of first individually-relevant doc in the reranked list
        mrr_value = 0.0
        for rank, doc in enumerate(reranked, start=1):
            if _is_relevant(doc, case):
                mrr_value = 1.0 / rank
                break
        self.mrr += mrr_value

        self.count += 1

    def mean(self) -> "RetrievalMetrics":
        """Return a new instance with mean values (mutates nothing)."""
        out = RetrievalMetrics()
        if self.count == 0:
            return out
        out.recall_at_12 = self.recall_at_12 / self.count
        out.recall_at_5 = self.recall_at_5 / self.count
        out.precision_at_5 = self.precision_at_5 / self.count
        out.mrr = self.mrr / self.count
        out.count = self.count
        return out

    def as_dict(self) -> dict[str, float]:
        return {
            "Recall@12": self.recall_at_12,
            "Recall@5": self.recall_at_5,
            "Precision@5": self.precision_at_5,
            "MRR": self.mrr,
        }


# ----------------------------------------------------------------------------
# Table formatting
# ----------------------------------------------------------------------------


def _format_row(label: str, m: RetrievalMetrics, total: int) -> str:
    if m.count == 0:
        return f"  {label:<20}  {'N/A':>10}  {'N/A':>10}  {'N/A':>10}  {'N/A':>10}  {'':>5}  (0 cases)"
    return (
        f"  {label:<20}  {m.recall_at_12:>10.3f}  {m.recall_at_5:>10.3f}  "
        f"{m.precision_at_5:>10.3f}  {m.mrr:>10.3f}  {m.count:>5}"
    )


def _print_table(category_metrics: dict[str, RetrievalMetrics], overall: RetrievalMetrics) -> None:
    separator = "  " + "-" * 20 + "  " + "-" * 10 + "  " + "-" * 10 + "  " + "-" * 10 + "  " + "-" * 10 + "  " + "-" * 5
    total = sum(m.count for m in category_metrics.values())

    print()
    print("  Retrieval Evaluation Summary")
    print("  " + "=" * 80)
    print(f"  {'Category':<20}  {'R@12':>10}  {'R@5':>10}  {'P@5':>10}  {'MRR':>10}  {'N':>5}")
    print(separator)
    for cat in ["factual", "summarization", "multi-hop", "visual"]:
        print(_format_row(cat.capitalize(), category_metrics[cat].mean(), total))
    print(separator)
    print(_format_row("Overall", overall.mean(), total))
    print("  " + "=" * 80)
    print()
    print("  Metrics: R@12 = Recall@12 (pre-rerank), R@5 = Recall@5 (post-rerank),")
    print("           P@5 = Precision@5 (post-rerank), MRR = Mean Reciprocal Rank")
    print()


# ----------------------------------------------------------------------------
# Per-case detail line (for debug / verbose mode)
# ----------------------------------------------------------------------------


def _case_detail(
    case: EvalCase,
    pre_rerank: list["Document"],
    reranked: list["Document"],
) -> str:
    total_relevant = len(_build_relevant_set(case))
    if total_relevant == 0:
        return "  SKIP (no relevant universe defined)"

    pre_hit = sum(1 for doc in pre_rerank[:12] if _is_relevant(doc, case))
    reranked_5 = reranked[:5]
    reranked_hit = sum(1 for doc in reranked_5 if _is_relevant(doc, case))

    r12 = pre_hit / total_relevant
    r5 = reranked_hit / total_relevant
    p5 = reranked_hit / 5

    mrr_val = 0.0
    for rank, doc in enumerate(reranked, start=1):
        if _is_relevant(doc, case):
            mrr_val = 1.0 / rank
            break

    sources = ", ".join(case.expected_source_files) or "none"
    pages = str(case.expected_pages) if case.expected_pages else "any"
    return (
        f"  [{case.category:<12}] {case.id:<50s}  "
        f"R@12={r12:.2f}  R@5={r5:.2f}  P@5={p5:.2f}  MRR={mrr_val:.2f}  "
        f"(src={sources}, pg={pages})"
    )


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main(notebook_id: str | None = None, verbose: bool = False) -> dict:
    """
    Run retrieval evaluation for all non-adversarial eval cases.

    Args:
        notebook_id: Notebook ID to search. If None, reads from
            evals/.test_notebook.json.
        verbose: If True, prints a line per case.

    Returns:
        A dict with 'category_metrics', 'overall', and 'per_case' keys.
    """
    if notebook_id is None:
        config = CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(config)
        notebook_id = data["notebook_id"]
        print(f"[retrieval_eval] Using notebook_id from config: {notebook_id}")

    embedding_model = get_embedding_model()

    category_metrics: dict[str, RetrievalMetrics] = defaultdict(RetrievalMetrics)
    per_case: dict[str, dict] = {}

    non_adversarial = [c for c in CASES if not c.is_adversarial]
    print(f"[retrieval_eval] Running retrieval eval for {len(non_adversarial)} non-adversarial cases...")

    with logfire.span(
        "eval.retrieval_run",
        case_count=len(non_adversarial),
        notebook_id=notebook_id,
    ):
        for case in non_adversarial:
            with logfire.span("eval.case", case_id=case.id, category=case.category):
                try:
                    pre_rerank, reranked = run_retrieval(case.query, notebook_id, embedding_model)
                except Exception as exc:
                    print(f"[retrieval_eval] ERROR on case '{case.id}': {exc}")
                    logfire.error("Retrieval eval case failed", case_id=case.id, error=str(exc))
                    continue

                metrics = RetrievalMetrics()
                metrics.update(pre_rerank, reranked, case)
                category_metrics[case.category].update(pre_rerank, reranked, case)

                if verbose:
                    print(_case_detail(case, pre_rerank, reranked))

                per_case[case.id] = {
                    "category": case.category,
                    "recall_at_12": metrics.recall_at_12,
                    "recall_at_5": metrics.recall_at_5,
                    "precision_at_5": metrics.precision_at_5,
                    "mrr": metrics.mrr,
                    "pre_rerank_count": len(pre_rerank),
                    "reranked_count": len(reranked),
                }

    # Aggregate overall
    overall = RetrievalMetrics()
    for cat, m in category_metrics.items():
        m_copy = RetrievalMetrics()
        m_copy.recall_at_12 = m.recall_at_12
        m_copy.recall_at_5 = m.recall_at_5
        m_copy.precision_at_5 = m.precision_at_5
        m_copy.mrr = m.mrr
        m_copy.count = m.count
        overall.recall_at_12 += m.recall_at_12
        overall.recall_at_5 += m.recall_at_5
        overall.precision_at_5 += m.precision_at_5
        overall.mrr += m.mrr
        overall.count += m.count

    _print_table(category_metrics, overall)

    return {
        "category_metrics": {k: v.mean().as_dict() for k, v in category_metrics.items()},
        "overall": overall.mean().as_dict(),
        "per_case": per_case,
    }


if __name__ == "__main__":
    notebook_id_arg = None
    verbose = False

    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print("Usage: python -m evals.retrieval_eval [--notebook-id ID] [--verbose]")
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
            print("Run with --help for usage.", file=sys.stderr)
            sys.exit(1)

    if not CONFIG_PATH.exists():
        print(
            f"[retrieval_eval] ERROR: {CONFIG_PATH} not found.",
            file=sys.stderr,
        )
        print(
            "  Run 'python -m evals.bootstrap_notebook' first to create the test notebook.",
            file=sys.stderr,
        )
        sys.exit(1)

    main(notebook_id=notebook_id_arg, verbose=verbose)
