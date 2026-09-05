"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import {
  Share2,
  Download,
  Settings as SettingsIcon,
  MoreHorizontal,
  MoreVertical,
  Plus,
  Search,
  FileText,
  AudioWaveform,
  Upload,
  LinkIcon,
  X,
  ChevronRight,
  PanelLeftClose,
  PanelRightClose,
  Check,
  Loader2,
  Square,
  Send,
  ChevronDown,
  CreditCard,
  StickyNote,
  RefreshCw,
  BrainCircuit,
  Trash2,
  HardDrive,
  ClipboardList,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useParams, useRouter } from "next/navigation";
import {
  getSources,
  deleteSource,
  uploadSource,
  addWehsiteSource,
  addSearchSource,
  getMessages,
  streamChat,
  generateFlashcards,
  getFlashcards,
  deleteFlashcardDeck,
  generateAudioOverview,
  getPodcasts,
  savePodcast,
  deletePodcast,
  MindMap,
  getMindmaps,
  generateMindmap,
  deleteMindmap,
  type Source,
  type Message,
  type Flashcard,
  type FlashcardDeck,
  type Podcast,
} from "@/lib/api";
import MindMapViewer from "@/app/components/mindmap/MindMapViewer";

type RightSidebarView = "none" | "flashcards" | "sources";

function MessageCitations({ citations }: { citations: string[] }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-paper-dark bg-ink-soft/50 hover:bg-ink-soft rounded-lg transition-colors border border-ink-border/50"
      >
        <FileText className="w-3.5 h-3.5" />
        <span>
          {citations.length} Source{citations.length === 1 ? "" : "s"}
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {isOpen && (
        <div className="mt-2 space-y-1.5 p-2 bg-ink-soft/30 rounded-lg border border-ink-border/50">
          {citations.map((src, si) => (
            <div
              key={si}
              className="flex items-start gap-2 text-xs text-paper-dark"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-azure-light mt-1.5 shrink-0" />
              <span className="leading-relaxed">{src}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface FlashcardDeck {
  id: string;
  topic: string;
  difficulty: string;
  cards: Flashcard[];
  isGenerating: boolean;
  createdAt: number;
}

export default function NotebookDetail() {
  const { id } = useParams() as { id: string };
  const router = useRouter();
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const`