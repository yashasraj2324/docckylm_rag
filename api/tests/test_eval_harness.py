"""Offline tests for the eval harness (no network, no credentials).

They run the real pydantic_evals Dataset/evaluators against a stubbed RAG task and a
fake judge model, so metric wiring and failure reporting are verified without the
live stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from pydantic_ai.models.function import FunctionModel  # noqa: E402
from pydantic_ai.models.test import TestModel  # noqa: E402

from evals.aggregate import report_to_records, summarize_run, summarize_runs  # noqa: E402
from evals.evaluators import default_evaluators  # noqa: E402
from evals.golden_dataset import CASES, build_dataset  # noqa: E402
from evals.judge import JudgeConfigError, judge_model_spec  # noqa: E402
from evals.schemas import CaseInputs, RagOutput, SourceRef  # noqa: E402
from evals.task import NO_CONTEXT_MESSAGE, is_model_refusal, parse_citation  # noqa: E402


def test_dataset_composition():
    ds = build_dataset("nb")
    assert len(ds.cases) == len(CASES) == 34
    assert sum(c.metadata.is_adversarial for c in ds.cases) == 15
    assert len({c.name for c in ds.cases}) == 34
    assert all(c.metadata.expected_sources for c in ds.cases if not c.metadata.is_adversarial)


def test_no_context_message_matches_chat_route():
    src = (API_DIR / "routes" / "chat.py").read_text(encoding="utf-8")
    assert NO_CONTEXT_MESSAGE in src


def test_parse_citation_and_refusal_detection():
    assert parse_citation("a.pdf — Page 4") == SourceRef(file="a.pdf", page=4)
    assert parse_citation("a.pdf — Page 4 — Asset x (/u)") == SourceRef(file="a.pdf", page=4)
    assert parse_citation("web page") == SourceRef(file="web page", page=None)
    assert is_model_refusal("I couldn’t find relevant information in your sources.")
    assert not is_model_refusal("The answer is 512.")


def _fake_task(refuse_adversarial=True):
    def task(inputs: CaseInputs) -> RagOutput:
        case = next(c for c in CASES if c.query == inputs.question)
        if case.is_adversarial:
            return RagOutput(answer=NO_CONTEXT_MESSAGE if refuse_adversarial else "It is X.",
                             refused=refuse_adversarial, refusal_reason="gate" if refuse_adversarial else None,
                             retrieved=[SourceRef(file="1706.03762v7.pdf", page=1)],
                             citations=["1706.03762v7.pdf — Page 1"], retrieved_context="ctx")
        refs = [SourceRef(file=f, page=p) for f in case.expected_source_files for p in (case.expected_pages or [])]
        # expected doc ranked 2nd, so MRR == 0.5 for single-page-hit cases
        retrieved = [SourceRef(file="other.pdf", page=99), *refs]
        return RagOutput(answer="answer", refused=False, retrieved=retrieved,
                         citations=[f"{f} — Page 1" for f in case.expected_source_files],
                         retrieved_context="ctx")
    return task


def _run(task, judge):
    ds = build_dataset("nb")
    for ev in default_evaluators(judge):
        ds.add_evaluator(ev)
    report = ds.evaluate_sync(task, progress=False)
    return summarize_run(report_to_records(report))


def test_metrics_and_sample_sizes():
    judge = TestModel(custom_output_args={"reason": "ok", "pass": True, "score": 0.8})
    s = _run(_fake_task(), judge)["overall"]
    assert s["Recall@5"]["value"] == pytest.approx(1.0) and s["Recall@5"]["n"] == 19
    assert s["MRR"]["n"] == 19 and 0.2 < s["MRR"]["value"] <= 0.5
    assert s["CitationAccuracy"]["value"] == pytest.approx(1.0)
    assert s["Faithfulness"]["value"] == pytest.approx(0.8) and s["Faithfulness"]["n"] == 19
    assert s["Faithfulness"]["n_not_applicable"] == 15  # adversarial cases, counted
    assert s["AdversarialRefusalRate"] == {"value": 1.0, "n": 15, "numerator": 15, "n_task_failed": 0}
    assert s["FalseRefusalRate"]["value"] == 0.0 and s["FalseRefusalRate"]["n"] == 19
    assert s["RefusalCorrect"]["value"] == 1.0 and s["RefusalCorrect"]["n"] == 34


def test_refusal_correctness_catches_hallucination():
    judge = TestModel(custom_output_args={"reason": "ok", "pass": True, "score": 1.0})
    s = _run(_fake_task(refuse_adversarial=False), judge)["overall"]
    assert s["AdversarialRefusalRate"]["value"] == 0.0
    assert s["RefusalCorrect"]["value"] == pytest.approx(19 / 34)


def test_failed_judge_calls_are_reported_not_dropped():
    def boom(messages, info):
        raise RuntimeError("judge endpoint down")

    run = _run(_fake_task(), FunctionModel(boom))
    s = run["overall"]
    assert s["Faithfulness"]["n"] == 0 and s["Faithfulness"]["value"] is None
    assert s["Faithfulness"]["n_failed"] == 19
    assert run["evaluator_failures"]["FaithfulnessJudge"] == 19


def test_out_of_range_judge_score_is_a_failure():
    judge = TestModel(custom_output_args={"reason": "ok", "pass": True, "score": 7.0})
    run = _run(_fake_task(), judge)
    assert run["overall"]["Faithfulness"]["n_failed"] == 19


def test_task_crash_is_counted():
    inner = _fake_task()

    def task(inputs):
        if "speed of light" in inputs.question:
            raise RuntimeError("qdrant down")
        return inner(inputs)

    judge = TestModel(custom_output_args={"reason": "ok", "pass": True, "score": 1.0})
    run = _run(task, judge)
    assert run["n_task_failed"] == 1 and run["n_cases_with_output"] == 33
    assert run["overall"]["AdversarialRefusalRate"]["n"] == 14


def test_cross_run_spread():
    judge = TestModel(custom_output_args={"reason": "ok", "pass": True, "score": 0.8})
    r = _run(_fake_task(), judge)
    agg = summarize_runs([r, r, r])
    assert agg["n_runs"] == 3 and agg["overall"]["Faithfulness"]["std"] == 0.0
    assert agg["overall"]["Faithfulness"]["n_per_run"] == [19, 19, 19]


def test_judge_must_differ_from_answer_model(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.delenv("EVAL_JUDGE_MODEL", raising=False)
    with pytest.raises(JudgeConfigError):
        judge_model_spec()
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "azure:GPT-4o-mini")
    with pytest.raises(JudgeConfigError):
        judge_model_spec()
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "azure:gpt-4.1")
    assert judge_model_spec() == "azure:gpt-4.1"


def test_aggregation_tolerates_category_missing_from_a_run():
    judge = TestModel(custom_output_args={"reason": "ok", "pass": True, "score": 0.8})
    full = _run(_fake_task(), judge)

    def task(inputs):  # every adversarial case crashes in this run
        if "adversarial" in {c.category for c in CASES if c.query == inputs.question}:
            raise RuntimeError("azure 429")
        return _fake_task()(inputs)

    partial = _run(task, judge)
    assert "adversarial" not in partial["by_category"]
    agg = summarize_runs([full, partial, full])
    assert agg["by_category"]["adversarial"]["AdversarialRefusalRate"]["n_per_run"] == [15, 0, 15]
    assert agg["task_failures_total"] == 15
