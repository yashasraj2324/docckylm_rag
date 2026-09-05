"""
Flashcard CRUD operations for MongoDB.

Replaces Supabase version. Decks are virtual groupings (deck_id field, not a
separate collection). Flashcards are appended, never replaced.
"""

from typing import Any

from bson import ObjectId
from pymongo.database import Database as MongoDatabase

from db.mongo_client import _serialize_doc


def save_flashcards(
    db: MongoDatabase,
    notebook_id: str,
    flashcards: list[dict[str, str]],
    deck_id: str = None,
    topic: str = None,
    difficulty: str = None,
) -> None:
    rows = [
        {
            "notebook_id": ObjectId(notebook_id),
            "deck_id": deck_id,
            "topic": topic,
            "difficulty": difficulty,
            "question": card["question"],
            "answer": card["answer"],
            "card_order": i,
        }
        for i, card in enumerate(flashcards)
    ]
    if rows:
        db.flashcards.insert_many(rows)


def list_flashcards(db: MongoDatabase, notebook_id: str) -> list[dict[str, Any]]:
    docs = list(
        db.flashcards.find({"notebook_id": ObjectId(notebook_id)}).sort("card_order", 1)
    )
    return [_serialize_doc(d) for d in docs]


def delete_flashcards(db: MongoDatabase, notebook_id: str) -> None:
    db.flashcards.delete_many({"notebook_id": ObjectId(notebook_id)})


def delete_flashcard_deck(db: MongoDatabase, deck_id: str) -> None:
    db.flashcards.delete_many({"deck_id": deck_id})
