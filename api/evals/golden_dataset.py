

from typing import Literal

from pydantic import BaseModel


class EvalCase(BaseModel):

    id: str
    query: str
    expected_answer_keywords: list[str]
    expected_source_files: list[str]
    expected_pages: list[int] | None = None
    category: Literal[
        "factual",
        "summarization",
        "multi-hop",
        "visual",
    ]
    is_adversarial: bool = False


CASES: list[EvalCase] = [
    # ---------------------------------------------------------------- factual
    EvalCase(
        id="factual-transformer-architecture",
        query="What is the dimension of model vectors (d_model) in the base Transformer?",
        expected_answer_keywords=["dmodel", "512", "multi-head attention", "encoder", "decoder"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[3],
        category="factual",
    ),
    EvalCase(
        id="factual-resnet-key-contribution",
        query="What problem does the ResNet paper solve?",
        expected_answer_keywords=["degradation", "residual learning", "152 layers", "ImageNet", "shortcut connections"],
        expected_source_files=["1512.03385v1.pdf"],
        expected_pages=[1],
        category="factual",
    ),
    EvalCase(
        id="factual-attention-formula",
        query="What is the formula for scaled dot-product attention?",
        expected_answer_keywords=["softmax", "QKT", "√dk", "matrix", "values"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[4],
        category="factual",
    ),
    EvalCase(
        id="factual-transformer-training-cost",
        query="How long did it take to train the big Transformer on WMT EN-DE and on how many GPUs?",
        expected_answer_keywords=["3.5 days", "8 P100 GPUs", "28.4 BLEU", "English-to-German", "WMT 2014"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[8],
        category="factual",
    ),
    EvalCase(
        id="factual-resnet-won-2015",
        query="What competition did the ResNet submission win in 2015?",
        expected_answer_keywords=["ILSVRC 2015", "1st place", "ImageNet", "classification", "3.57%"],
        expected_source_files=["1512.03385v1.pdf"],
        expected_pages=[1],
        category="factual",
    ),
    # -------------------------------------------------------- summarization
    EvalCase(
        id="summarization-transformer-vs-rnn",
        query="Summarize the main argument for why Transformers are better than RNNs.",
        expected_answer_keywords=["attention mechanism", "parallelization", "recurrence", "global dependencies", "12 hours"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[1, 2],
        category="summarization",
    ),
    EvalCase(
        id="summarization-resnet-innovation",
        query="Summarize the residual learning framework proposed in this paper.",
        expected_answer_keywords=["identity mapping", "residual function", "F(x)+x", "shortcut connections", "degradation"],
        expected_source_files=["1512.03385v1.pdf"],
        expected_pages=[1, 3],
        category="summarization",
    ),
    EvalCase(
        id="summarization-multi-head-attention",
        query="What is multi-head attention and why is it used?",
        expected_answer_keywords=["h=8", "subspaces", "dk=dv=64", "parallel attention", "dmodel/h"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[4, 5],
        category="summarization",
    ),
    EvalCase(
        id="summarization-resnet-cifar-analysis",
        query="Summarize the findings from the CIFAR-10 experiments with deep ResNets.",
        expected_answer_keywords=["1000 layers", "CIFAR-10", "overfitting", "training error", "ResNet-110"],
        expected_source_files=["1512.03385v1.pdf"],
        expected_pages=[7, 8],
        category="summarization",
    ),
    # ------------------------------------------------------------- multi-hop
    EvalCase(
        id="multi-hop-transformer-en-fr",
        query="How does the English-to-French result of the Transformer compare to the English-to-German result, and what does the paper attribute the difference to?",
        expected_answer_keywords=["41.8 BLEU", "EN-FR", "WMT 2014", "English-to-French", "outperforms"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[1, 8],
        category="multi-hop",
    ),
    EvalCase(
        id="multi-hop-resnet-vs-vgg",
        query="How do ResNets compare to VGG nets in terms of depth and computational complexity?",
        expected_answer_keywords=["152 layers", "8× deeper", "VGG", "lower complexity", "11.3 billion FLOPs"],
        expected_source_files=["1512.03385v1.pdf"],
        expected_pages=[1, 7],
        category="multi-hop",
    ),
    EvalCase(
        id="multi-hop-attention-complexity",
        query="Compare the computational complexity of self-attention, recurrent, and convolutional layers.",
        expected_answer_keywords=["O(n²·d)", "O(n·d²)", "recurrent", "self-attention", "sequential"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[6, 7],
        category="multi-hop",
    ),
    EvalCase(
        id="multi-hop-transformer-vs-other-models",
        query="How does the Transformer big model compare to ConvS2S and GNMT in both BLEU score and training cost?",
        expected_answer_keywords=["28.4 BLEU", "ConvS2S", "GNMT", "3.3×10¹⁸ FLOPs", "2.3×10¹⁹ FLOPs"],
        expected_source_files=["1706.03762v7.pdf"],
        # Multi-page: ConvS2S and GNMT are introduced as related work on pages 1-2;
        # BLEU scores and FLOPs for all three models are in Table 2 on page 8.
        expected_pages=[1, 2, 8],
        category="multi-hop",
    ),
    EvalCase(
        id="multi-hop-transformer-complexity-tradeoff",
        query="The Transformer has O(n²·d) complexity for self-attention. How does this theoretical complexity affect its training cost compared to recurrent models, and what does the paper say about its parallelizability advantage?",
        expected_answer_keywords=["O(n²·d)", "O(n·d²)", "parallelization", "3.3×10¹⁸ FLOPs", "8 P100 GPUs"],
        expected_source_files=["1706.03762v7.pdf"],
        # Requires combining: architecture description (page 3), complexity analysis
        # (page 6), training data/baselines (page 7), and BLEU/FLOP results (page 8).
        expected_pages=[3, 6, 7, 8],
        category="multi-hop",
    ),
    # ---------------------------------------------------------------- visual
    EvalCase(
        id="visual-resnet-figure1",
        query="Describe the two plots in Figure 1 of the ResNet paper and what they demonstrate.",
        expected_answer_keywords=["CIFAR-10", "training error", "test error", "56-layer", "20-layer"],
        expected_source_files=["1512.03385v1.pdf"],
        expected_pages=[1],
        category="visual",
    ),
    EvalCase(
        id="visual-transformer-figure1",
        query="Describe the architecture diagram of the Transformer shown in Figure 1.",
        expected_answer_keywords=["encoder", "decoder", "N=6", "stacked", "positional encoding"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[3],
        category="visual",
    ),
    EvalCase(
        id="visual-transformer-figure2",
        query="What is shown in Figure 2 of the Transformer paper?",
        expected_answer_keywords=["Scaled Dot-Product Attention", "Multi-Head Attention", "parallel", "concatenated", "QKT/√dk"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[4],
        category="visual",
    ),
    EvalCase(
        id="visual-transformer-table2",
        query="What does Table 2 of the Transformer paper compare across models?",
        expected_answer_keywords=["BLEU", "WMT 2014", "training cost", "FLOPs", "ByteNet"],
        expected_source_files=["1706.03762v7.pdf"],
        expected_pages=[8],
        category="visual",
    ),
    EvalCase(
        id="visual-resnet-figure7",
        query="What does Figure 7 of the ResNet paper show about layer responses?",
        expected_answer_keywords=["standard deviations", "BN", "3x3 layer", "ResNets", "smaller responses"],
        expected_source_files=["1512.03385v1.pdf"],
        expected_pages=[8],
        category="visual",
    ),
    # ---------------------------------------------------------- adversarial
    # These queries are deliberately about topics NOT covered in either source paper.
    # The retriever should return NO relevant chunks, causing prepare_answer to set
    # has_context=False and the pipeline to return a refusal.
    # We avoid query terms that appear in ML papers (e.g. "language model",
    # "training", "attention", "transformer") — they would cause the retriever to
    # return spurious chunks and the LLM to hallucinate.
    EvalCase(
        id="adversarial-fifa-world-cup",
        query="Who won the FIFA World Cup in 2018?",
        expected_answer_keywords=[],
        expected_source_files=[],
        expected_pages=None,
        category="factual",
        is_adversarial=True,
    ),
    EvalCase(
        id="adversarial-australia-capital",
        query="What is the capital city of Australia?",
        expected_answer_keywords=[],
        expected_source_files=[],
        expected_pages=None,
        category="summarization",
        is_adversarial=True,
    ),
    EvalCase(
        id="adversarial-water-boiling-point",
        query="What is the boiling point of water at sea level?",
        expected_answer_keywords=[],
        expected_source_files=[],
        expected_pages=None,
        category="multi-hop",
        is_adversarial=True,
    ),
]
