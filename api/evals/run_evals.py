"""Run the pydantic_evals RAG suite N times and save results.

    python -m evals.run_evals [--notebook-id ID] [--repeat 3] [--max-concurrency 4]

Required env: the backend env (MONGODB_*, QDRANT_*, AZURE_OPENAI_*, NVIDIA_API_KEY)
plus EVAL_JUDGE_MODEL (must differ from AZURE_OPENAI_CHAT_DEPLOYMENT).
Results: evals/results/<UTC timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_api_dir = Path(__file__).resolve().parent.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

import logfire  # noqa: E402

from telemetry import init_telemetry  # noqa: E402

init_telemetry(app=None)
try:
    logfire.instrument_pydantic_ai()  # judge calls show up in traces
except Exception as err:  # pragma: no cover
    print(f"[run_evals] pydantic-ai instrumentation skipped: {err}")

import pydantic_evals  # noqa: E402

from evals.aggregate import format_summary, report_to_records, summarize_run, summarize_runs  # noqa: E402
from evals.evaluators import default_evaluators  # noqa: E402
from evals.golden_dataset import build_dataset  # noqa: E402
from evals.judge import (  # noqa: E402
    JudgeConfigError,
    build_judge_model,
    generation_model_id,
    judge_model_spec,
)
from evals.task import run_rag  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = EVAL_DIR / ".test_notebook.json"
RESULTS_DIR = EVAL_DIR / "results"


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_api_dir, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def _save_partial(out_dir: Path, stamp: str, runs: list) -> None:
    """Persist finished runs immediately so a later crash cannot lose them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stamp}.partial.json").write_text(
        json.dumps({"timestamp_utc": stamp, "runs": runs}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--notebook-id")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--max-concurrency", type=int, default=4)
    ap.add_argument("--no-judge", action="store_true",
                    help="skip the LLM-judged metrics (faithfulness, relevance)")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args(argv)

    notebook_id = args.notebook_id
    if not notebook_id:
        if not CONFIG_PATH.exists():
            print("No notebook: run `python -m evals.bootstrap_notebook` first.", file=sys.stderr)
            return 1
        notebook_id = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["notebook_id"]

    if args.no_judge:
        # Retrieval/refusal metrics only. Judge metrics will show n=0 (not run), not a score.
        judge_spec, judge = "none (--no-judge)", None
    else:
        try:
            judge_spec = judge_model_spec()  # fails if unset or equal to the answer model
        except JudgeConfigError as err:
            print(f"[run_evals] {err}", file=sys.stderr)
            return 2
        judge = build_judge_model()

    dataset = build_dataset(notebook_id)
    for ev in default_evaluators(judge):
        dataset.add_evaluator(ev)

    n_adv = sum(1 for c in dataset.cases if c.metadata and c.metadata.is_adversarial)
    print(f"[run_evals] {len(dataset.cases)} cases ({n_adv} adversarial), "
          f"{args.repeat} runs, answer model={generation_model_id()}, judge={judge_spec}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = []
    with logfire.span("eval.suite", repeat=args.repeat, notebook_id=notebook_id, judge=judge_spec):
        for i in range(1, args.repeat + 1):
            report = dataset.evaluate_sync(
                run_rag,
                name=f"rag-eval-run{i}",
                max_concurrency=args.max_concurrency,
                metadata={"run": i, "judge_model": judge_spec, "answer_model": generation_model_id()},
            )
            records = report_to_records(report)
            runs.append({"run": i, "summary": summarize_run(records), "cases": records["cases"]})
            _save_partial(args.out_dir, stamp, runs)
            tf = records["task_failures"]
            print(f"[run_evals] run {i}: {len(records['cases'])} cases scored, {len(tf)} pipeline failures")
            for kind, n in Counter(f["error"][:160] for f in tf).most_common(5):
                print(f"    {n}x {kind}")

    aggregate = summarize_runs([r["summary"] for r in runs])
    print()
    print(format_summary(aggregate))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "timestamp_utc": stamp,
                "git_commit": _git_commit(),
                "pydantic_evals_version": getattr(pydantic_evals, "__version__", None),
                "answer_model": generation_model_id(),
                "judge_model": judge_spec,
                "n_cases": len(dataset.cases),
                "n_adversarial": n_adv,
                "repeat": args.repeat,
                "aggregate": aggregate,
                "runs": runs,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved {path}")
    failed = aggregate["task_failures_total"] or sum(aggregate["evaluator_failures_total"].values())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
