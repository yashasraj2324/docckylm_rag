/**
 * Frontend API client for AI Notebooks.
 *
 * All requests proxy through Next.js rewrites: /api/python/* → http://127.0.0.1:5328/*
 * In production, Vercel routes via vercel.json.
 */

const API_BASE = "/api/python";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Notebook {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Source {
  id: string;
  notebook_id: string;
  file_name: string;
  status: string;
  type: string;
  gridfs_file_id?: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
}

export interface Flashcard {
  question: string;
  answer: string;
}

export interface FlashcardDeck {
  id: string;
  topic: string;
  difficulty: string;
  cards: Flashcard[];
  createdAt?: number;
}

export interface Podcast {
  id: string;
  notebook_id: string;
  gridfs_file_id: string;
  format: string;
  language: string;
  created_at: string;
}

export interface MindMap {
  id: string;
  notebook_id: string;
  topic: string;
  data: MindMapNode;
  created_at: string;
}

export interface MindMapNode {
  name: string;
  children?: MindMapNode[];
}

// ── Notebooks ─────────────────────────────────────────────────────────────────

export async function fetchNotebooks(): Promise<Notebook[]> {
  const res = await fetch(`${API_BASE}/notebooks`);
  if (!res.ok) throw new Error("Failed to fetch notebooks");
  return res.json();
}

export async function createNotebook(title: string): Promise<Notebook> {
  const res = await fetch(`${API_BASE}/notebooks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Failed to create notebook");
  return res.json();
}

export async function deleteNotebook(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/notebooks/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete notebook");
}

// ── Sources ───────────────────────────────────────────────────────────────────

export async function getSources(notebookId: string): Promise<Source[]> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/sources`);
  if (!res.ok) throw new Error("Failed to fetch sources");
  return res.json();
}

export async function uploadSource(
  notebookId: string,
  file: File,
): Promise<Source> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/sources`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload source");
  return res.json();
}

export async function addWebsiteSource(
  notebookId: string,
  url: string,
): Promise<Source> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/sources/website`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error("Failed to add website source");
  return res.json();
}

export async function addSearchSource(
  notebookId: string,
  query: string,
): Promise<Source[]> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/sources/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error("Failed to search for sources");
  return res.json();
}

export async function deleteSource(
  notebookId: string,
  sourceId: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/notebooks/${notebookId}/sources/${sourceId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error("Failed to delete source");
}

// ── Messages ──────────────────────────────────────────────────────────────────

export async function getMessages(notebookId: string): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/messages`);
  if (!res.ok) throw new Error("Failed to fetch messages");
  return res.json();
}

// ── Chat (SSE Streaming) ──────────────────────────────────────────────────────

export function streamChat(
  notebookId: string,
  query: string,
  onChunk: (chunk: string) => void,
  onCitations: (citations: string[]) => void,
  onDone: () => void,
  onError: (err: string) => void,
): AbortController | null {
  const abortCtrl = new AbortController();

  fetch(`${API_BASE}/notebooks/${notebookId}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query }),
    signal: abortCtrl.signal,
  })
    .then(async (response) => {
      if (!response.ok || !response.body) {
        onError("Failed to start chat stream");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data === "[DONE]") {
              onDone();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === "chunk" && parsed.content) {
                onChunk(parsed.content);
              } else if (parsed.type === "citations" && parsed.citations) {
                onCitations(parsed.citations);
              } else if (parsed.type === "error" && parsed.content) {
                onError(parsed.content);
              }
            } catch {
              // Ignore JSON parse errors for keepalive comments
            }
          }
        }
      }
      onDone();
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message || "Stream error");
      }
    });

  return abortCtrl;
}

// ── Flashcards ────────────────────────────────────────────────────────────────

export async function generateFlashcards(
  notebookId: string,
  deckId: string,
  topic: string,
  difficulty: string,
  count: number,
  sourceIds: string[],
): Promise<{ title: string; flashcards: Flashcard[] }> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/flashcards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      deck_id: deckId,
      topic,
      difficulty,
      count,
      source_ids: sourceIds,
    }),
  });
  if (!res.ok) throw new Error("Failed to generate flashcards");
  return res.json();
}

export async function getFlashcards(
  notebookId: string,
): Promise<FlashcardDeck[]> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/flashcards`);
  if (!res.ok) throw new Error("Failed to fetch flashcards");
  const data = await res.json();
  return data.decks || [];
}

export async function deleteFlashcardDeck(
  notebookId: string,
  deckId: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/notebooks/${notebookId}/flashcards/${deckId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error("Failed to delete flashcard deck");
}

// ── Audio Overview ────────────────────────────────────────────────────────────

export async function generateAudioOverview(
  notebookId: string,
  format: string,
  language: string,
  length: string,
  focus: string,
  sourceIds: string[],
): Promise<Blob> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/audio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      format,
      language,
      length,
      focus,
      source_ids: sourceIds,
    }),
  });
  if (!res.ok) throw new Error("Failed to generate audio overview");
  return res.blob();
}

// ── Podcasts ──────────────────────────────────────────────────────────────────

export async function getPodcasts(notebookId: string): Promise<Podcast[]> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/podcasts`);
  if (!res.ok) throw new Error("Failed to fetch podcasts");
  return res.json();
}

export async function savePodcast(
  notebookId: string,
  formData: FormData,
): Promise<Podcast> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/podcasts`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to save podcast");
  return res.json();
}

export async function deletePodcast(
  notebookId: string,
  podcastId: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/notebooks/${notebookId}/podcasts/${podcastId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error("Failed to delete podcast");
}

export function getAudioUrl(fileId: string): string {
  return `${API_BASE}/audio/${fileId}`;
}

// ── Mind Maps ──────────────────────────────────────────────────────────────────

export async function getMindmaps(notebookId: string): Promise<MindMap[]> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/mindmaps`);
  if (!res.ok) throw new Error("Failed to fetch mind maps");
  return res.json();
}

export async function generateMindmap(
  notebookId: string,
  topic: string,
  language: string,
  sourceIds: string[],
): Promise<MindMap> {
  const res = await fetch(`${API_BASE}/notebooks/${notebookId}/mindmaps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, language, source_ids: sourceIds }),
  });
  if (!res.ok) throw new Error("Failed to generate mind map");
  return res.json();
}

export async function deleteMindmap(
  notebookId: string,
  mindmapId: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/notebooks/${notebookId}/mindmaps/${mindmapId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error("Failed to delete mind map");
}
