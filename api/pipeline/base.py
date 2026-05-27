from ingestion.embedder import get_embedding_model
from llm.chat_model import get_chat_model
from pipeline.flashcards import generate_flashcards
from pipeline.ingest import ingest
from pipeline.query import ask, prepare_answer, stream_answer


class RAGPipeline:

    def __init__(self):
        self.embedding_model = get_embedding_model()
        self.chat_model = get_chat_model()

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest(self, pdf_path, notebook_id, source_id):
        ingest(self.embedding_model, pdf_path, notebook_id, source_id)

    # ── Query / Answer ────────────────────────────────────────────────────────

    def ask(self, query, notebook_id):
        return ask(self.chat_model, self.embedding_model, query, notebook_id)

    def prepare_answer(self, query, notebook_id):
        return prepare_answer(self.embedding_model, query, notebook_id)

    def stream_answer(self, prompt):
        return stream_answer(self.chat_model, prompt)

    # ── Flashcards ────────────────────────────────────────────────────────────

    def generate_flashcards(self, notebook_id: str, num_cards: int = 10):
        return generate_flashcards(self.chat_model, notebook_id, num_cards)
