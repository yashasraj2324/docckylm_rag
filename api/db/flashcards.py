from typing import cast

from supabase import Client


def save_flashcards(
    client: Client,
    notebook_id: str,
    flashcards: list[dict[str, str]],
    deck_id: str = None,
    topic: str = None,
    difficulty: str = None,
) -> None:
    # Don't delete existing flashcards, just append new ones!
    rows = [
        {
            "notebook_id": notebook_id,
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
        client.table("flashcards").insert(rows).execute()


def list_flashcards(client: Client, notebook_id: str) -> list[dict[str, str]]:
    response = (
        client.table("flashcards")
        .select("*")
        .eq("notebook_id", notebook_id)
        .order("card_order")
        .execute()
    )
    rows = cast(list[dict[str, str]], response.data or [])
    return rows


def delete_flashcards(client: Client, notebook_id: str) -> None:
    client.table("flashcards").delete().eq("notebook_id", notebook_id).execute()


def delete_flashcard_deck(client: Client, deck_id: str) -> None:
    client.table("flashcards").delete().eq("deck_id", deck_id).execute()
