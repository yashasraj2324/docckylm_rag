"""
LLM-as-judge prompts for the generation evaluation.

These prompts are used by generation_eval.py to score the LLM answer on
faithfulness and answer relevance.  The judge is the same Azure OpenAI chat
model used by the RAG pipeline itself.
"""

# ----------------------------------------------------------------------
# Faithfulness
# ----------------------------------------------------------------------
#
# Scores whether every factual claim in the answer is directly supported
# by the retrieved context.  Returns a float in [0, 1].

FAITHFULNESS_PROMPT = """You are an expert academic fact-checker. Your task is to evaluate whether the answer is faithful to the provided context.

Score the answer on the following scale:
- 1.0: Every factual claim in the answer is directly and explicitly supported by the context. No fabrications or unsupported additions.
- 0.5: Most claims are supported, but the answer contains 1-2 minor unsupported details or slightly overstates what the context says.
- 0.0: The answer contains significant fabricated content that is NOT in the context, or the core claim of the answer contradicts the context.

IMPORTANT:
- Only evaluate what is explicitly stated or directly implied by the context.
- Do not penalize the answer for saying it cannot answer if the context doesn't contain the information (that is scored separately).
- Respond with ONLY a single float number between 0.0 and 1.0 (e.g., "0.75"). No explanation.

Context:
{context}

Answer:
{answer}

Score:"""


# ----------------------------------------------------------------------
# Answer relevance
# ----------------------------------------------------------------------
#
# Scores whether the answer directly addresses the user's question,
# ignoring whether the answer happens to be correct.  Returns a float in [0, 1].

ANSWER_RELEVANCE_PROMPT = """You are an expert academic tutor. Your task is to evaluate whether the answer is relevant to the question asked.

Score the answer on the following scale:
- 1.0: The answer directly addresses all aspects of the question. It is clearly focused and on-topic.
- 0.5: The answer partially addresses the question but misses one or more important aspects, or provides tangential information.
- 0.0: The answer is completely off-topic, evades the question, or is factually wrong in a way that shows it didn't understand the question.

Respond with ONLY a single float number between 0.0 and 1.0 (e.g., "0.75"). No explanation.

Question: {query}

Answer:
{answer}

Score:"""
