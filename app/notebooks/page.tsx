"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Search,
  Grid3x3,
  List,
  MoreVertical,
  Plus,
  Loader2,
} from "lucide-react";
import {
  fetchNotebooks,
  createNotebook,
  deleteNotebook,
  type Notebook,
} from "@/lib/api";
import { useRouter } from "next/navigation";

// ── Helpers ───────────────────────────────────────────────────────────────────

const CARD_COLORS = [
  "bg-ink-soft",
  "bg-gold-dark",
  "bg-azure-dark",
  "bg-ink-border",
  "bg-azure-dark",
  "bg-azure-dark",
  "bg-gold-dark",
  "bg-azure-dark",
];

const CARD_ICONS = ["📓", "⚖️", "🌐", "⚙️", "🧠", "📚", "🔬", "💡"];

/** Deterministically pick a colour/icon from the notebook id so it never flickers. */
function cardStyle(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return {
    bgColor: CARD_COLORS[hash % CARD_COLORS.length],
    icon: CARD_ICONS[hash % CARD_ICONS.length],
  };
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Notebooks() {
  const router = useRouter();
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);

  useEffect(() => {
    const closeDropdown = () => setOpenDropdownId(null);
    window.addEventListener("click", closeDropdown);
    return () => window.removeEventListener("click", closeDropdown);
  }, []);

  // ── Load ───────────────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchNotebooks();
      setNotebooks(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load notebooks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // ── Create ─────────────────────────────────────────────────────────────────

  const handleCreate = useCallback(async () => {
    if (creating) return;
    setCreating(true);
    try {
      const nb = await createNotebook("Untitled notebook");
      setNotebooks((prev) => [nb, ...prev]);
      router.push(`/notebooks/${nb.id}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not create notebook");
    } finally {
      setCreating(false);
    }
  }, [creating, router]);

  const handleDelete = useCallback(async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this notebook?"))
      return;

    try {
      await deleteNotebook(id);
      setNotebooks((prev) => prev.filter((nb) => nb.id !== id));
      setOpenDropdownId(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not delete notebook");
    }
  }, []);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-ink text-paper">
      {/* Header */}
      <div className="border-b border-ink-border px-6 py-4">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button className="px-4 py-2 rounded-full bg-ink-soft text-paper">
              All
            </button>
            <button className="px-4 py-2 rounded-full bg-azure text-paper">
              My notebooks
            </button>
            <button className="px-4 py-2 rounded-full bg-ink-soft text-paper">
              Featured notebooks
            </button>
          </div>

          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-ink-soft rounded-lg">
              <Search className="w-5 h-5" />
            </button>
            <button
              id="view-grid"
              className={`p-2 rounded-lg ${viewMode === "grid" ? "bg-ink-soft" : "hover:bg-ink-soft"}`}
              onClick={() => setViewMode("grid")}
            >
              <Grid3x3 className="w-5 h-5" />
            </button>
            <button
              id="view-list"
              className={`p-2 rounded-lg ${viewMode === "list" ? "bg-ink-soft" : "hover:bg-ink-soft"}`}
              onClick={() => setViewMode("list")}
            >
              <List className="w-5 h-5" />
            </button>
            <button className="px-4 py-2 text-sm hover:bg-ink-soft rounded-lg flex items-center gap-2">
              Most recent
              <span className="text-xs">▼</span>
            </button>
            <button
              id="create-notebook-btn"
              onClick={handleCreate}
              disabled={creating}
              className="px-4 py-2 bg-paper text-ink rounded-full hover:bg-paper-dark flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed transition-opacity"
            >
              {creating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <span className="text-lg leading-none">+</span>
              )}
              Create new
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-6">
        <h1 className="text-3xl mb-8">My notebooks</h1>

        {/* ── Error state ──────────────────────────────────────────────────── */}
        {error && (
          <div className="mb-6 rounded-xl bg-gold/20 border border-gold-dark text-gold px-5 py-4 flex items-center gap-3">
            <span>⚠️</span>
            <span>{error}</span>
            <button
              onClick={load}
              className="ml-auto text-sm underline hover:text-gold-soft"
            >
              Retry
            </button>
          </div>
        )}

        {/* ── Loading skeleton ─────────────────────────────────────────────── */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="bg-ink-soft rounded-2xl min-h-[240px] animate-pulse"
              />
            ))}
          </div>
        ) : viewMode === "grid" ? (
          /* ── Grid View ──────────────────────────────────────────────────── */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Create new card */}
            <button
              id="create-notebook-card"
              onClick={handleCreate}
              disabled={creating}
              className="bg-ink-soft rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer hover:bg-ink-border transition-colors min-h-[240px] disabled:opacity-60"
            >
              <div className="w-16 h-16 rounded-full bg-azure flex items-center justify-center mb-4">
                {creating ? (
                  <Loader2 className="w-8 h-8 animate-spin" />
                ) : (
                  <Plus className="w-8 h-8" />
                )}
              </div>
              <span className="text-lg">Create new notebook</span>
            </button>

            {/* Notebook cards */}
            {notebooks.map((nb) => {
              const { bgColor, icon } = cardStyle(nb.id);
              return (
                <div
                  key={nb.id}
                  onClick={() => router.push(`/notebooks/${nb.id}`)}
                  className={`${bgColor} rounded-2xl p-6 cursor-pointer hover:opacity-90 transition-opacity min-h-[240px] flex flex-col justify-between relative`}
                >
                  <div className="absolute top-4 right-4">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenDropdownId(
                          openDropdownId === nb.id ? null : nb.id,
                        );
                      }}
                      className="p-1 hover:bg-ink-border/50 rounded"
                    >
                      <MoreVertical className="w-5 h-5" />
                    </button>
                    {openDropdownId === nb.id && (
                      <div className="absolute right-0 mt-2 w-32 bg-ink-soft rounded-lg shadow-lg border border-ink-border z-10 overflow-hidden">
                        <button
                          onClick={(e) => handleDelete(e, nb.id)}
                          className="w-full text-left px-4 py-2 text-sm text-gold-dark hover:bg-ink-border"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex items-start gap-3">
                    <div className="text-4xl">{icon}</div>
                  </div>

                  <div>
                    <h3 className="text-xl mb-2 line-clamp-2">{nb.title}</h3>
                    <p className="text-sm text-paper-dark">
                      {formatDate(nb.updated_at)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* ── List View ──────────────────────────────────────────────────── */
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-ink-border">
                  <th className="text-left py-4 px-4 text-sm font-normal text-paper-dark">
                    Title
                  </th>
                  <th className="text-left py-4 px-4 text-sm font-normal text-paper-dark">
                    Updated
                  </th>
                  <th className="text-left py-4 px-4 text-sm font-normal text-paper-dark">
                    Role
                  </th>
                  <th className="py-4 px-4" />
                </tr>
              </thead>
              <tbody>
                {notebooks.map((nb) => {
                  const { icon } = cardStyle(nb.id);
                  return (
                    <tr
                      key={nb.id}
                      onClick={() => router.push(`/notebooks/${nb.id}`)}
                      className="border-b border-ink-border hover:bg-ink-soft/50 cursor-pointer"
                    >
                      <td className="py-4 px-4">
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">{icon}</span>
                          <span className="line-clamp-1">{nb.title}</span>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-paper-dark">
                        {formatDate(nb.updated_at)}
                      </td>
                      <td className="py-4 px-4 text-paper-dark">Owner</td>
                      <td className="py-4 px-4 relative">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenDropdownId(
                              openDropdownId === nb.id ? null : nb.id,
                            );
                          }}
                          className="p-1 hover:bg-ink-border rounded"
                        >
                          <MoreVertical className="w-5 h-5" />
                        </button>
                        {openDropdownId === nb.id && (
                          <div className="absolute right-4 mt-2 w-32 bg-ink-soft rounded-lg shadow-lg border border-ink-border z-10 overflow-hidden">
                            <button
                              onClick={(e) => handleDelete(e, nb.id)}
                              className="w-full text-left px-4 py-2 text-sm text-gold-dark hover:bg-ink-border"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}

                {notebooks.length === 0 && !loading && (
                  <tr>
                    <td colSpan={4} className="py-16 text-center text-paper-dark">
                      No notebooks yet — create your first one!
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
