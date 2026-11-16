"""Custom evaluators + LLMJudge subclasses for the RAG suite.

An evaluator returns ``{}`` when a metric does not apply to a case; the runner
counts those so no case disappears from an average unreported.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_evals.evaluators import Evaluator, EvaluatorContext, LLMJudge
from pydantic_evals.evaluators.common import OutputConfig

from evals.schemas import CaseInputs, CaseMetadata, RagOutput, SourceRef
from evals.task import parse_citation

Ctx = EvaluatorContext[CaseInputs, RagOutput, CaseMetadata]
K = 5


def _matches(ref: SourceRef, expected: SourceRef) -> bool:
    return ref.file == expected.file and (expected.page is None or ref.page == expected.page)


@dataclass(repr=False)
class RecallAt5(Evaluator[CaseInputs, RagOutput, CaseMetadata]):
    """Fraction of expected (file, page) pairs present in the top-5 reranked docs."""

    def evaluate(self, ctx: Ctx) -> dict[str, float]:
        md = ctx.metadata
        if md is None or md.is_adversarial or not md.expected_sources:
            return {}
        top = ctx.output.retrieved[:K]
        hit = sum(1 for e in md.expected_sources if any(_matches(r, e) for r in top))
        return {"RecallAt5": hit / len(md.expected_sources)}


@dataclass(repr=False)
class ReciprocalRank(Evaluator[CaseInputs, RagOutput, CaseMetadata]):
    """1/rank of the first relevant reranked doc (0 if none). Mean over cases = MRR."""

    def evaluate(self, ctx: Ctx) -> dict[str, float]:
        md = ctx.metadata
        if md is None or md.is_adversarial or not md.expected_sources:
            return {}
        for rank, ref in enumerate(ctx.output.retrieved, start=1):
            if any(_matches(ref, e) for e in md.expected_sources):
                return {"ReciprocalRank": 1.0 / rank}
        return {"ReciprocalRank": 0.0}


@dataclass(repr=False)
class CitationAccuracy(Evaluator[CaseInputs, RagOutput, CaseMetadata]):
    """Fraction of expected files cited, minus 0.2 per unexpected file (floored at 0)."""

    def evaluate(self, ctx: Ctx) -> dict[str, float]:
        md = ctx.metadata
        if md is None or md.is_adversarial or not md.expected_sources:
            return {}
        expected = {e.file for e in md.expected_sources}
        cited = {parse_citation(c).file for c in ctx.output.citations}
        if not cited:
            return {"CitationAccuracy": 0.0}
        score = len(expected & cited) / len(expected) - 0.2 * len(cited - expected)
        return {"CitationAccuracy": max(0.0, score)}


@dataclass(repr=False)
class RefusalCorrect(Evaluator[CaseInputs, RagOutput, CaseMetadata]):
    """Adversarial cases must refuse; answerable cases must not."""

    def evaluate(self, ctx: Ctx) -> dict[str, bool]:
        md = ctx.metadata
        if md is None:
            return {}
        return {"RefusalCorrect": ctx.output.refused == md.is_adversarial}


# --------------------------------------------------------------------------- judges

FAITHFULNESS_RUBRIC = """\
Grade FAITHFULNESS of output.answer against output.retrieved_context.
Only the text in output.retrieved_context counts as evidence; ignore your own world
knowledge and ignore whether the answer is correct in the real world.
Break output.answer into its factual claims (numbers, names, results, definitions).
Score = (claims directly supported by retrieved_context) / (total claims), in [0, 1].
A claim that is true in the real world but absent from retrieved_context is UNSUPPORTED.
Formatting, headings and restatements of supported content are not claims.
Return score 1.0 only if every claim is supported; 0.0 if none are. Set pass=true
only when score >= 0.9."""

RELEVANCE_RUBRIC = """\
Grade ANSWER RELEVANCE of output.answer to the user's question (the Input question).
1.0 = directly and completely answers what was asked; 0.5 = partially answers, is
off-target in places, or omits a main part; 0.0 = does not answer the question
(including any refusal such as "I couldn't find relevant information") or is about
something else. Judge responsiveness only, not factual accuracy.
Set pass=true only when score >= 0.7."""


def _checked(result: dict, name: str) -> dict:
    value = result.get(name)
    score = getattr(value, "value", value)
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0.0 <= score <= 1.0:
        raise ValueError(f"judge returned an invalid {name} score: {score!r}")
    return result


@dataclass(repr=False)
class FaithfulnessJudge(LLMJudge):
    """Skipped (not applicable) for adversarial cases and refused answers."""

    rubric: str = FAITHFULNESS_RUBRIC
    include_input: bool = True
    score: OutputConfig | bool = False
    assertion: OutputConfig | bool = False

    def __post_init__(self):
        self.score = OutputConfig(evaluation_name="FaithfulnessJudge", include_reason=True)

    async def evaluate(self, ctx: Ctx):  # type: ignore[override]
        if ctx.metadata is None or ctx.metadata.is_adversarial or ctx.output.refused:
            return {}
        return _checked(await super().evaluate(ctx), "FaithfulnessJudge")


@dataclass(repr=False)
class RelevanceJudge(LLMJudge):
    """Skipped for adversarial cases. Refused answerable cases ARE judged (expected ~0)."""

    rubric: str = RELEVANCE_RUBRIC
    include_input: bool = True
    score: OutputConfig | bool = False
    assertion: OutputConfig | bool = False

    def __post_init__(self):
        self.score = OutputConfig(evaluation_name="RelevanceJudge", include_reason=True)

    async def evaluate(self, ctx: Ctx):  # type: ignore[override]
        if ctx.metadata is None or ctx.metadata.is_adversarial:
            return {}
        return _checked(await super().evaluate(ctx), "RelevanceJudge")


def default_evaluators(judge_model) -> list[Evaluator]:
    """Programmatic evaluators always; the LLM judges only when a judge model is given."""
    evaluators: list[Evaluator] = [
        RecallAt5(),
        ReciprocalRank(),
        CitationAccuracy(),
        RefusalCorrect(),
    ]
    if judge_model is not None:
        evaluators += [FaithfulnessJudge(model=judge_model), RelevanceJudge(model=judge_model)]
    return evaluators
