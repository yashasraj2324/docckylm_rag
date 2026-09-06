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
  addWebsiteSource,
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
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [rightSidebarView, setRightSidebarView] = useState<
    "main" | "flashcards"
  >("main");
  const [showAddSourcesModal, setShowAddSourcesModal] = useState(false);
  const [showFlashcardsModal, setShowFlashcardsModal] = useState(false);

  // Audio Modal State
  const [showAudioModal, setShowAudioModal] = useState(false);
  const [audioFormat, setAudioFormat] = useState("Deep Dive");
  const [audioLanguage, setAudioLanguage] = useState("English");
  const [audioLength, setAudioLength] = useState("Default");
  const [audioFocus, setAudioFocus] = useState("");
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [podcasts, setPodcasts] = useState<Podcast[]>([]);

  // Mind Map State
  const [mindmaps, setMindmaps] = useState<MindMap[]>([]);
  const [showMindmapModal, setShowMindmapModal] = useState(false);
  const [mindmapTopic, setMindmapTopic] = useState("");
  const [mindmapLanguage, setMindmapLanguage] = useState("English");
  const [isGeneratingMindmap, setIsGeneratingMindmap] = useState(false);
  const [activeMindmap, setActiveMindmap] = useState<MindMap | null>(null);

  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(
    new Set(),
  );
  const [loadingSources, setLoadingSources] = useState(true);
  const [openSourceDropdown, setOpenSourceDropdown] = useState<string | null>(
    null,
  );
  const [openArtifactDropdown, setOpenArtifactDropdown] = useState<string | null>(
    null,
  );
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const handleGenerateAudio = async () => {
    setShowAudioModal(false);
    setIsGeneratingAudio(true);
    try {
      const audioBlob = await generateAudioOverview(
        id,
        audioFormat,
        audioLanguage,
        audioLength,
        audioFocus,
        Array.from(selectedSources),
      );

      const formData = new FormData();
      formData.append("audio", audioBlob, "podcast.mp3");
      formData.append("format", audioFormat);
      formData.append("language", audioLanguage);

      await savePodcast(id, formData);
      await loadPodcasts();
    } catch (err) {
      console.error("Failed to generate audio overview:", err);
      alert("Failed to generate audio overview. Please try again.");
    } finally {
      setIsGeneratingAudio(false);
    }
  };

  const handleGenerateMindmap = async () => {
    setShowMindmapModal(false);
    setIsGeneratingMindmap(true);
    try {
      await generateMindmap(
        id,
        mindmapTopic || "General Overview",
        mindmapLanguage,
        Array.from(selectedSources)
      );
      await loadMindmaps();
    } catch (err) {
      console.error("Failed to generate mind map:", err);
      alert("Failed to generate mind map. Please try again.");
    } finally {
      setIsGeneratingMindmap(false);
    }
  };

  const handleDeleteMindmap = async (mindmapId: string) => {
    try {
      await deleteMindmap(id, mindmapId);
      if (activeMindmap?.id === mindmapId) {
        setActiveMindmap(null);
      }
      await loadMindmaps();
    } catch (err) {
      console.error("Failed to delete mind map:", err);
    }
  };

  // ── Flashcards state ───────────────────────────────────────────────────────────
  const [savedDecks, setSavedDecks] = useState<FlashcardDeck[]>([]);
  const [activeDeckId, setActiveDeckId] = useState<string | null>(null);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [correctScore, setCorrectScore] = useState(0);
  const [wrongScore, setWrongScore] = useState(0);
  const [isDeckFinished, setIsDeckFinished] = useState(false);

  useEffect(() => {
    setCorrectScore(0);
    setWrongScore(0);
    setIsDeckFinished(false);
  }, [activeDeckId]);

  // Flashcards modal state
  const [flashcardTopic, setFlashcardTopic] = useState("");
  const [flashcardCount, setFlashcardCount] = useState("10");
  const [flashcardDifficulty, setFlashcardDifficulty] = useState("Medium");
  const [searchQuery, setSearchQuery] = useState("");
  const [showWebsiteModal, setShowWebsiteModal] = useState(false);
  const [websiteUrls, setWebsiteUrls] = useState("");

  const activeDeck = savedDecks.find((d) => d.id === activeDeckId) || null;

  const handleGenerateFlashcards = async (
    overrideTopic?: string,
    overrideCount?: string,
    overrideDifficulty?: string,
  ) => {
    setShowFlashcardsModal(false);

    const topic = overrideTopic !== undefined ? overrideTopic : flashcardTopic;
    const count = overrideCount !== undefined ? overrideCount : flashcardCount;
    const difficulty =
      overrideDifficulty !== undefined
        ? overrideDifficulty
        : flashcardDifficulty;

    const deckId = Date.now().toString();
    const newDeck: FlashcardDeck = {
      id: deckId,
      topic: topic || "General Study",
      difficulty: difficulty,
      cards: [],
      isGenerating: true,
      createdAt: Date.now(),
    };

    setSavedDecks((prev) => [newDeck, ...prev]);

    try {
      const res = await generateFlashcards(
        id,
        deckId,
        topic,
        difficulty,
        parseInt(count, 10) || 10,
        Array.from(selectedSources),
      );

      setSavedDecks((prev) =>
        prev.map((deck) =>
          deck.id === deckId
            ? {
                ...deck,
                cards: res.flashcards,
                topic: res.title,
                isGenerating: false,
              }
            : deck,
        ),
      );
    } catch (err) {
      console.error(err);
      setSavedDecks((prev) =>
        prev.map((deck) =>
          deck.id === deckId ? { ...deck, isGenerating: false } : deck,
        ),
      );
    }
  };

  // Keyboard navigation for Flashcards
  useEffect(() => {
    if (
      rightSidebarView !== "flashcards" ||
      !activeDeck ||
      activeDeck.isGenerating ||
      activeDeck.cards.length === 0
    )
      return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input or textarea
      if (["INPUT", "TEXTAREA"].includes((e.target as HTMLElement).tagName))
        return;

      if (e.code === "Space") {
        e.preventDefault();
        setIsFlipped((prev) => !prev);
      } else if (e.code === "ArrowLeft") {
        e.preventDefault();
        setIsFlipped(false);
        setCurrentCardIndex((prev) => Math.max(0, prev - 1));
      } else if (e.code === "ArrowRight") {
        e.preventDefault();
        setCurrentCardIndex((prev) =>
          Math.min(activeDeck.cards.length - 1, prev + 1),
        );
        setIsFlipped(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [rightSidebarView, activeDeck]);

  // ── Chat state ───────────────────────────────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<string[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortCtrlRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  const handleDownloadPdf = async () => {
    if (!chatContainerRef.current) return;
    setIsDownloadingPdf(true);
    try {
      const html2canvas = (await import("html2canvas")).default;
      const { jsPDF } = await import("jspdf");

      const canvas = await html2canvas(chatContainerRef.current, {
        scale: 2,
        backgroundColor: "#111827", // Match dark theme (bg-ink equivalent)
        useCORS: true,
      });

      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "px",
        format: [canvas.width, canvas.height],
      });

      pdf.addImage(imgData, "PNG", 0, 0, canvas.width, canvas.height);
      pdf.save("chat.pdf");
    } catch (err) {
      console.error("Failed to generate PDF:", err);
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  useEffect(() => {
    const closeDropdown = () => {
      setOpenSourceDropdown(null);
      setOpenArtifactDropdown(null);
    };
    window.addEventListener("click", closeDropdown);
    return () => window.removeEventListener("click", closeDropdown);
  }, []);

  const loadSources = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getSources(id);
      setSources(data);
      // Select all by default
      setSelectedSources(new Set(data.map((s) => s.id)));
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSources(false);
    }
  }, [id]);

  const loadFlashcards = useCallback(async () => {
    if (!id) return;
    try {
      const decks = await getFlashcards(id);
      if (decks && decks.length > 0) {
        setSavedDecks(decks);
      }
    } catch (e) {
      console.error("Failed to load flashcards:", e);
    }
  }, [id]);

  const loadPodcasts = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getPodcasts(id);
      setPodcasts(data);
    } catch (e) {
      console.error("Failed to load podcasts:", e);
    }
  }, [id]);

  const loadMindmaps = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getMindmaps(id);
      setMindmaps(data);
    } catch (e) {
      console.error("Failed to load mind maps:", e);
    }
  }, [id]);

  useEffect(() => {
    loadSources();
    loadFlashcards();
    loadPodcasts();
    loadMindmaps();
  }, [loadSources, loadFlashcards, loadPodcasts, loadMindmaps]);

  const toggleSourceSelection = (sourceId: string) => {
    setSelectedSources((prev) => {
      const next = new Set(prev);
      if (next.has(sourceId)) {
        next.delete(sourceId);
      } else {
        next.add(sourceId);
      }
      return next;
    });
  };

  const handleDeleteSource = async (e: React.MouseEvent, sourceId: string) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this source?")) return;

    try {
      await deleteSource(id, sourceId);
      setSources((prev) => prev.filter((s) => s.id !== sourceId));
      setSelectedSources((prev) => {
        const next = new Set(prev);
        next.delete(sourceId);
        return next;
      });
      setOpenSourceDropdown(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not delete source");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    if (
      !file.type.includes("pdf") &&
      !file.name.endsWith(".pdf") &&
      !file.name.endsWith(".doc") &&
      !file.name.endsWith(".docx") &&
      !file.name.endsWith(".pptx")
    ) {
      alert(
        "Only PDF, Word documents, and PowerPoint presentations (.pptx) are supported right now.",
      );
      return;
    }

    setUploading(true);
    try {
      const newSource = await uploadSource(id, file);
      setSources((prev) => [newSource, ...prev]);
      setSelectedSources((prev) => {
        const next = new Set(prev);
        next.add(newSource.id);
        return next;
      });
      setShowAddSourcesModal(false);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
      if (e.target) e.target.value = "";
    }
  };

  const handleWebsiteUpload = () => {
    setShowWebsiteModal(true);
  };