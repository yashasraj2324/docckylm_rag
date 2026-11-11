"""Pure aggregation of eval reports: per-run metrics with sample sizes, then
mean/spread across runs. No metric silently drops cases: every metric carries
``n`` (scored), ``n_failed`` (evaluator raised), ``n_not_applicable`` and
``n_task_failed`` (pipeline crashed, so no output)."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any

SCORE_METRICS = {
    "Recall@5": "RecallAt5",
    "MRR": "ReciprocalRank",
    "CitationAccuracy": "CitationAccuracy",
    "Faithfulness": "FaithfulnessJudge",
    "AnswerRelevance": "RelevanceJudge",
}


def report_to_records(report) -> dict[str, Any]:
    """Flatten a pydantic_evals EvaluationReport into plain dicts."""
    cases = []
    for c in report.cases:
        cases.append(
            {
                "name": c.name,
                "category": c.metadata.category if c.metadata else None,
                "is_adversarial": bool(c.metadata and c.metadata.is_adversarial),
                "scores": {k: v.value for k, v in c.scores.items()},
                "score_reasons": {k: v.reason for k, v in c.scores.items() if v.reason},
                "assertions": {k: v.value for k, v in c.assertions.items()},
                "evaluator_failures": [
                    {"evaluator": f.name, "error": f.error_message, "type": f.error_type}
                    for f in c.evaluator_failures
                ],
                "output": c.output.model_dump(),
            }
        )
    task_failures = [
        {"name": f.name, "error": f.error_message} for f in report.failures
    ]
    return {"cases": cases, "task_failures": task_failures}


def _mean_metric(cases: list[dict], key: str, n_task_failed: int) -> dict[str, Any]:
    vals = [c["scores"][key] for c in cases if key in c["scores"]]
    failed = sum(1 for c in cases for f in c["evaluator_failures"] if f["evaluator"] == key)
    return {
        "value": statistics.fmean(vals) if vals else None,
        "n": len(vals),
        "n_failed": failed,
        "n_not_applicable": len(cases) - len(vals) - failed,
        "n_task_failed": n_task_failed,
    }


def _rate(num: int, den: int, n_task_failed: int = 0) -> dict[str, Any]:
    return {"value": (num / den) if den else None, "n": den, "numerator": num,
            "n_task_failed": n_task_failed}


def summarize_run(records: dict[str, Any]) -> dict[str, Any]:
    cases = records["cases"]
    n_task_failed = len(records["task_failures"])

    def build(subset: list[dict]) -> dict[str, Any]:
        out = {m: _mean_metric(subset, key, n_task_failed) for m, key in SCORE_METRICS.items()}
        adv = [c for c in subset if c["is_adversarial"]]
        ans = [c for c in subset if not c["is_adversarial"]]
        out["AdversarialRefusalRate"] = _rate(sum(c["output"]["refused"] for c in adv), len(adv))
        out["FalseRefusalRate"] = _rate(sum(c["output"]["refused"] for c in ans), len(ans))
        scored = [c for c in subset if "RefusalCorrect" in c["assertions"]]
        out["RefusalCorrect"] = _rate(sum(c["assertions"]["RefusalCorrect"] for c in scored), len(scored))
        return out

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        by_cat[c["category"]].append(c)
    return {
        "n_cases_with_output": len(cases),
        "n_task_failed": n_task_failed,
        "overall": build(cases),
        "by_category": {k: build(v) for k, v in sorted(by_cat.items())},
        "refusal_reasons": dict(Counter(
            c["output"]["refusal_reason"] for c in cases if c["output"]["refused"]
        )),
        "evaluator_failures": dict(Counter(
            f["evaluator"] for c in cases for f in c["evaluator_failures"]
        )),
        "task_failures": records["task_failures"],
    }


def _spread(values: list[float]) -> dict[str, Any]:
    return {
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def _across(metric_dicts: list[dict[str, Any]]) -> dict[str, Any]:
    vals = [m["value"] for m in metric_dicts if m["value"] is not None]
    out = _spread(vals) if vals else {"mean": None, "std": None, "min": None, "max": None}
    out["runs_with_value"] = len(vals)
    out["per_run"] = [m["value"] for m in metric_dicts]
    out["n_per_run"] = [m["n"] for m in metric_dicts]
    for extra in ("n_failed", "n_not_applicable", "n_task_failed"):
        if any(extra in m for m in metric_dicts):
            out[f"{extra}_per_run"] = [m.get(extra, 0) for m in metric_dicts]
    return out


def summarize_runs(run_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    names = run_summaries[0]["overall"].keys()
    # A category can be absent from a run when all its cases failed in the pipeline;
    # it then counts as n=0 for that run instead of crashing the aggregation.
    cats = sorted({c for r in run_summaries for c in r["by_category"]})
    empty = {"value": None, "n": 0, "n_failed": 0, "n_not_applicable": 0, "n_task_failed": 0}

    def cat_metric(r, c, m):
        return r["by_category"].get(c, {}).get(m, empty)

    return {
        "n_runs": len(run_summaries),
        "overall": {m: _across([r["overall"][m] for r in run_summaries]) for m in names},
        "by_category": {
            c: {m: _across([cat_metric(r, c, m) for r in run_summaries]) for m in names}
            for c in cats
        },
        "evaluator_failures_total": dict(sum((Counter(r["evaluator_failures"]) for r in run_summaries), Counter())),
        "task_failures_total": sum(r["n_task_failed"] for r in run_summaries),
    }


def format_summary(agg: dict[str, Any]) -> str:
    lines = [f"Evaluation summary over {agg['n_runs']} runs (mean ± std [min, max]; n = cases scored per run)", ""]
    lines.append(f"{'Metric':<24}{'mean':>8}{'std':>8}{'min':>8}{'max':>8}   n per run / failed / n.a.")
    for m, s in agg["overall"].items():
        if s["mean"] is None:
            lines.append(f"{m:<24}{'N/A':>8}   n={s['n_per_run']}")
            continue
        extra = ""
        if "n_failed_per_run" in s:
            extra = f" / failed={s['n_failed_per_run']} / n.a.={s['n_not_applicable_per_run']}"
        lines.append(
            f"{m:<24}{s['mean']:>8.3f}{s['std']:>8.3f}{s['min']:>8.3f}{s['max']:>8.3f}   n={s['n_per_run']}{extra}"
        )
    lines += ["", f"Evaluator (judge) failures across all runs: {agg['evaluator_failures_total'] or 0}",
              f"Pipeline (task) failures across all runs: {agg['task_failures_total']}"]
    return "\n".join(lines)
