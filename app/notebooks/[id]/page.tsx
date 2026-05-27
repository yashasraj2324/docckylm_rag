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
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 bg-gray-800/50 hover:bg-gray-800 rounded-lg transition-colors border border-gray-700/50"
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
        <div className="mt-2 space-y-1.5 p-2 bg-gray-800/30 rounded-lg border border-gray-700/50">
          {citations.map((src, si) => (
            <div
              key={si}
              className="flex items-start gap-2 text-xs text-gray-400"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
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
        backgroundColor: "#111827", // Match dark theme (bg-gray-900 equivalent)
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

  const handleWebsiteSubmit = async () => {
    if (!id || !websiteUrls.trim()) return;

    // Split by whitespace or newlines and filter out empty strings
    const urls = websiteUrls.split(/\s+/).filter((u) => u.trim() !== "");
    if (urls.length === 0) return;

    setUploading(true);
    try {
      // Upload sequentially for now
      for (const url of urls) {
        const newSource = await addWebsiteSource(id, url);
        setSources((prev) => [newSource, ...prev]);
        setSelectedSources((prev) => {
          const next = new Set(prev);
          next.add(newSource.id);
          return next;
        });
      }
      setShowWebsiteModal(false);
      setShowAddSourcesModal(false);
      setWebsiteUrls("");
    } catch (e) {
      alert(
        e instanceof Error ? e.message : "Upload failed for one or more URLs",
      );
    } finally {
      setUploading(false);
    }
  };

  const handleWebSearch = async () => {
    if (!id || !searchQuery.trim()) return;

    setUploading(true);
    try {
      const newSources = await addSearchSource(id, searchQuery);
      setSources((prev) => [...newSources, ...prev]);
      setSelectedSources((prev) => {
        const next = new Set(prev);
        newSources.forEach((s) => next.add(s.id));
        return next;
      });
      setShowAddSourcesModal(false);
      setSearchQuery("");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Search failed");
    } finally {
      setUploading(false);
    }
  };

  // ── Chat handlers ─────────────────────────────────────────────────────────

  // Load message history
  useEffect(() => {
    if (!id) return;
    getMessages(id).then(setMessages).catch(console.error);
  }, [id]);

  // Auto-scroll to bottom whenever messages/streaming content changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = useCallback(() => {
    if (!inputValue.trim() || isStreaming || !id) return;
    const query = inputValue.trim();
    setInputValue("");
    setIsStreaming(true);
    setStreamingContent("");
    setStreamingCitations([]);

    // Optimistically add user bubble
    setMessages((prev) => [...prev, { role: "user", content: query }]);

    abortCtrlRef.current = streamChat(
      id,
      query,
      (chunk) => setStreamingContent((prev) => prev + chunk),
      (citations) => setStreamingCitations(citations),
      () => {
        // On done: commit the streamed message into history
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: streamingContent + "",
            sources: streamingCitations,
          },
        ]);
        // Use a ref-captured version instead (pattern fix below)
        setIsStreaming(false);
      },
      (err) => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `⚠️ ${err}` },
        ]);
        setIsStreaming(false);
      },
    );
  }, [inputValue, isStreaming, id]);

  // A stable onDone that captures the latest streamed state
  const streamingContentRef = useRef("");
  const streamingCitationsRef = useRef<string[]>([]);
  useEffect(() => {
    streamingContentRef.current = streamingContent;
  }, [streamingContent]);
  useEffect(() => {
    streamingCitationsRef.current = streamingCitations;
  }, [streamingCitations]);

  const handleSendStable = useCallback(() => {
    if (!inputValue.trim() || isStreaming || !id) return;
    const query = inputValue.trim();
    setInputValue("");
    setIsStreaming(true);
    setStreamingContent("");
    setStreamingCitations([]);
    streamingContentRef.current = "";
    streamingCitationsRef.current = [];

    setMessages((prev) => [...prev, { role: "user", content: query }]);

    abortCtrlRef.current = streamChat(
      id,
      query,
      (chunk) => {
        streamingContentRef.current += chunk;
        setStreamingContent((prev) => prev + chunk);
      },
      (citations) => {
        streamingCitationsRef.current = citations;
        setStreamingCitations(citations);
      },
      () => {
        const finalContent = streamingContentRef.current;
        const finalCitations = streamingCitationsRef.current;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: finalContent, sources: finalCitations },
        ]);
        setStreamingContent("");
        setStreamingCitations([]);
        setIsStreaming(false);
      },
      (err) => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `⚠️ ${err}` },
        ]);
        setStreamingContent("");
        setIsStreaming(false);
      },
    );
  }, [inputValue, isStreaming, id]);

  return (
    <div className="h-screen bg-gray-900 text-white flex overflow-hidden">
      {/* Left Sidebar - Sources */}
      {leftSidebarOpen && (
        <div className="w-80 border-r border-gray-800 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-gray-800">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-medium">Sources</h2>
              <button className="p-1 hover:bg-gray-800 rounded">
                <MoreHorizontal className="w-4 h-4" />
              </button>
            </div>
            <button
              className="w-full px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm flex items-center gap-2"
              onClick={() => setShowAddSourcesModal(true)}
            >
              <Plus className="w-4 h-4" />
              Add sources
            </button>
          </div>

          <div className="p-4 border-b border-gray-800">
            <div className="text-xs text-gray-500 mb-2">
              Search the web for new sources
            </div>
            <div className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2">
              <Search className="w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder=""
                className="bg-transparent border-none outline-none flex-1 text-sm"
              />
            </div>
          </div>

          {loadingSources ? (
            <div className="flex-1 flex items-center justify-center p-8 text-gray-500">
              Loading sources...
            </div>
          ) : sources.length === 0 ? (
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="text-center text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                <p className="text-sm">Saved sources will appear here</p>
                <p className="text-xs mt-2">
                  Click Add Sources above to add PDFs, links, or other files. Or
                  simply paste a link to any YouTube video or website to quickly
                  save them to your sources.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex-1 min-h-0 overflow-y-auto">
              {sources.map((source) => (
                <div
                  key={source.id}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-gray-800/50 group border-b border-gray-800/50 cursor-pointer"
                  onClick={() => toggleSourceSelection(source.id)}
                >
                  {/* Checkbox */}
                  <div
                    className={`w-4 h-4 rounded flex items-center justify-center shrink-0 transition-colors ${selectedSources.has(source.id) ? "bg-blue-600 border border-blue-600" : "border border-gray-500"}`}
                  >
                    {selectedSources.has(source.id) && (
                      <Check className="w-3 h-3 text-white" />
                    )}
                  </div>

                  {/* Icon & Name */}
                  <div className="w-8 h-8 rounded bg-gray-800 flex items-center justify-center shrink-0">
                    <FileText className="w-4 h-4 text-gray-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate" title={source.file_name}>
                      {source.file_name}
                    </p>
                    <p className="text-xs text-gray-500 capitalize">
                      {source.status}
                    </p>
                  </div>

                  {/* More options */}
                  <div className="relative shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenSourceDropdown(
                          openSourceDropdown === source.id ? null : source.id,
                        );
                      }}
                      className="p-1.5 hover:bg-gray-700 rounded opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                    >
                      <MoreVertical className="w-4 h-4" />
                    </button>
                    {openSourceDropdown === source.id && (
                      <div className="absolute right-0 top-full mt-1 w-32 bg-gray-800 rounded-lg shadow-lg border border-gray-700 z-50 overflow-hidden">
                        <button
                          onClick={(e) => handleDeleteSource(e, source.id)}
                          className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-gray-700"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="p-4 border-t border-gray-800">
            <div className="flex items-center gap-2">
              <button className="flex-1 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm">
                Sources
              </button>
              <button className="flex-1 px-3 py-2 hover:bg-gray-800 rounded-lg text-sm">
                Chat
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <div className="border-b border-gray-800 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              className="p-1 hover:bg-gray-800 rounded"
              onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>

          </div>

          <div className="flex items-center gap-2">

            <button
              className="flex items-center gap-1.5 px-2 py-1 hover:bg-gray-800 rounded text-xs text-gray-400 disabled:opacity-50"
              onClick={handleDownloadPdf}
              disabled={isDownloadingPdf || messages.length === 0}
              title="Download Chat as PDF"
            >
              {isDownloadingPdf ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              <span className="hidden sm:inline">PDF</span>
            </button>
            <button
              className="p-1 hover:bg-gray-800 rounded"
              onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            >
              <PanelRightClose className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div ref={chatContainerRef} className="space-y-6 pb-4">
              {messages.length === 0 && !isStreaming && (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="text-6xl mb-6">👋</div>
                  <h1 className="text-3xl mb-4">
                    Let's start your notebook...
                  </h1>
                  <p className="text-gray-400 max-w-md">
                    Ask a question about your sources. Upload PDFs in the left
                    sidebar to get started.
                  </p>
                </div>
              )}

              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "assistant" && (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center text-sm shrink-0 mt-1">
                      AI
                    </div>
                  )}
                  <div
                    className={`max-w-[75%] ${msg.role === "user" ? "order-first" : ""}`}
                  >
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm ${
                        msg.role === "user"
                          ? "bg-blue-600 text-white rounded-br-sm ml-auto leading-relaxed"
                          : "bg-gray-800 text-gray-100 rounded-bl-sm ai-prose"
                      }`}
                    >
                      {msg.role === "user" ? (
                        msg.content
                      ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      )}
                    </div>
                    {msg.role === "assistant" &&
                      msg.sources &&
                      msg.sources.length > 0 && (
                        <MessageCitations citations={msg.sources} />
                      )}
                  </div>
                  {msg.role === "user" && (
                    <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm shrink-0 mt-1">
                      U
                    </div>
                  )}
                </div>
              ))}

              {/* Streaming bubble */}
              {isStreaming && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center text-sm shrink-0 mt-1">
                    AI
                  </div>
                  <div className="max-w-[75%]">
                    <div className="bg-gray-800 text-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 text-sm ai-prose">
                      {streamingContent ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {streamingContent}
                        </ReactMarkdown>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400">
                          <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                          <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                          <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
                        </span>
                      )}
                    </div>
                    {streamingCitations.length > 0 && (
                      <MessageCitations citations={streamingCitations} />
                    )}
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>
          </div>

          {/* Input Bar */}
          <div className="border-t border-gray-800 p-4">
            <div className="max-w-3xl mx-auto relative">
              <textarea
                ref={inputRef}
                rows={1}
                value={inputValue}
                onChange={(e) => {
                  setInputValue(e.target.value);
                  // Auto-grow
                  e.target.style.height = "auto";
                  e.target.style.height =
                    Math.min(e.target.scrollHeight, 160) + "px";
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendStable();
                  }
                }}
                placeholder="Ask a question about your sources…"
                disabled={isStreaming}
                className="w-full bg-gray-800 rounded-2xl px-4 py-3 pr-14 text-sm outline-none resize-none placeholder-gray-500 disabled:opacity-60 leading-relaxed"
                style={{ minHeight: "48px", maxHeight: "160px" }}
              />
              <button
                onClick={handleSendStable}
                disabled={!inputValue.trim() || isStreaming}
                className="absolute right-3 bottom-3 w-8 h-8 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl flex items-center justify-center transition-colors"
              >
                {isStreaming ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
            <p className="text-center text-xs text-gray-600 mt-2">
              Press Enter to send · Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>

      {/* Right Sidebar */}
      {rightSidebarOpen && (
        <div className="w-80 border-l border-gray-800 flex flex-col overflow-hidden bg-gray-900">
          {rightSidebarView === "main" ? (
            <>
              <div className="p-4 border-b border-gray-800 flex items-center justify-between">
                <h2 className="text-lg font-medium">Studio</h2>
                <button className="p-2 hover:bg-gray-800 rounded-lg border border-gray-700">
                  <Square className="w-4 h-4" />
                </button>
              </div>

              <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
                {/* Audio Overview Card */}
                <div className="bg-gradient-to-br from-blue-900 via-green-900 to-green-800 rounded-xl p-4 cursor-pointer hover:opacity-90 transition-opacity">
                  <h3 className="text-sm font-medium">
                    Create an Audio Overview in: हिन्दी, বাংলা, ગુજરાતી, ಕನ್ನಡ,
                    മലയാളം, मराठी, ਪੰਜਾਬੀ, தமிழ், తెలుగు
                  </h3>
                </div>

                {/* Two Column Grid */}
                <div className="grid grid-cols-2 gap-3">
                  {/* Audio */}
                  <div
                    className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-4 cursor-pointer hover:opacity-90 transition-opacity flex flex-col justify-between min-h-[100px]"
                    onClick={() => setShowAudioModal(true)}
                  >
                    <AudioWaveform className="w-6 h-6 text-blue-300" />
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Audio...</span>
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>



                  {/* Flashcards */}
                  <div
                    onClick={() => {
                      handleGenerateFlashcards("", "10", "Medium");
                    }}
                    className="bg-gradient-to-br from-orange-900 to-orange-950 rounded-xl p-4 cursor-pointer hover:opacity-90 transition-opacity flex flex-col justify-between min-h-[100px] group"
                  >
                    <CreditCard className="w-6 h-6 text-orange-300" />
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-sm font-medium">Flashcards</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowFlashcardsModal(true);
                        }}
                        className="p-1 -mr-1 hover:bg-orange-800/50 rounded-lg transition-colors"
                      >
                        <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-white transition-colors" />
                      </button>
                    </div>
                  </div>


                  {/* Mind Map */}
                  <div 
                    className="bg-gradient-to-br from-pink-900 to-pink-950 rounded-xl p-4 cursor-pointer hover:opacity-90 transition-opacity flex flex-col justify-between min-h-[100px] group"
                    onClick={() => setShowMindmapModal(true)}
                  >
                    <BrainCircuit className="w-6 h-6 text-pink-300" />
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Mind Map</span>
                      <button className="p-1 -mr-1 hover:bg-pink-800/50 rounded-lg transition-colors">
                        <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-white transition-colors" />
                      </button>
                    </div>
                  </div>
                </div>


                {/* Generated Artifacts List */}
                {(savedDecks.length > 0 ||
                  podcasts.length > 0 ||
                  mindmaps.length > 0 ||
                  isGeneratingAudio ||
                  isGeneratingMindmap) && (
                  <div className="mt-6 space-y-1">
                    {/* Generating Mindmap State */}
                    {isGeneratingMindmap && (
                      <div className="flex items-center gap-4 p-3 opacity-80">
                        <div className="w-8 h-8 flex items-center justify-center shrink-0">
                          <RefreshCw className="w-5 h-5 text-gray-300 animate-spin" />
                        </div>
                        <div>
                          <p className="text-[15px] font-medium text-gray-100">
                            Generating Mind Map...
                          </p>
                          <p className="text-[13px] text-gray-400 mt-0.5">
                            based on your sources
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Generating Audio State */}
                    {isGeneratingAudio && (
                      <div className="flex items-center gap-4 p-3 opacity-80">
                        <div className="w-8 h-8 flex items-center justify-center shrink-0">
                          <RefreshCw className="w-5 h-5 text-gray-300 animate-spin" />
                        </div>
                        <div>
                          <p className="text-[15px] font-medium text-gray-100">
                            Generating Podcast...
                          </p>
                          <p className="text-[13px] text-gray-400 mt-0.5">
                            based on your sources
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Saved Podcasts */}
                    {podcasts.map((podcast) => (
                      <div
                        key={podcast.id}
                        className="flex flex-col p-3 hover:bg-gray-800/50 rounded-2xl transition-colors group"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="w-8 h-8 flex items-center justify-center shrink-0">
                              <AudioWaveform className="w-6 h-6 text-purple-400" />
                            </div>
                            <div>
                              <p className="text-[15px] font-medium text-gray-100">
                                {podcast.format}
                              </p>
                              <p className="text-[13px] text-gray-400 mt-0.5">
                                {podcast.language} · Just now
                              </p>
                            </div>
                          </div>
                          <div className="relative">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenArtifactDropdown(openArtifactDropdown === podcast.id ? null : podcast.id);
                              }}
                              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-700/50 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <MoreVertical className="w-5 h-5 text-gray-400" />
                            </button>
                            {openArtifactDropdown === podcast.id && (
                              <div className="absolute right-0 top-full mt-1 w-32 bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden z-50">
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (confirm("Delete podcast?")) {
                                      await deletePodcast(id, podcast.id);
                                      loadPodcasts();
                                      setOpenArtifactDropdown(null);
                                    }
                                  }}
                                  className="w-full text-left px-3 py-2 text-sm text-red-400 hover:bg-gray-700/50 flex items-center gap-2"
                                >
                                  <Trash2 className="w-4 h-4" /> Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="mt-3 pl-12 pr-4">
                          <audio
                            controls
                            src={podcast.audio_url}
                            className="w-full h-10"
                          />
                        </div>
                      </div>
                    ))}

                    {/* Saved Flashcards */}
                    {savedDecks.map((deck) => {
                      if (deck.isGenerating) {
                        return (
                          <div
                            key={deck.id}
                            className="flex items-center gap-4 p-3 opacity-80"
                          >
                            <div className="w-8 h-8 flex items-center justify-center shrink-0">
                              <RefreshCw className="w-5 h-5 text-gray-300 animate-spin" />
                            </div>
                            <div>
                              <p className="text-[15px] font-medium text-gray-100">
                                Generating Flashcards...
                              </p>
                              <p className="text-[13px] text-gray-400 mt-0.5">
                                based on your sources
                              </p>
                            </div>
                          </div>
                        );
                      }

                      return (
                        <div
                          key={deck.id}
                          onClick={() => {
                            setActiveDeckId(deck.id);
                            setRightSidebarView("flashcards");
                            setCurrentCardIndex(0);
                            setIsFlipped(false);
                          }}
                          className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-800/50 rounded-2xl transition-colors group"
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-8 h-8 flex items-center justify-center shrink-0">
                              <CreditCard className="w-6 h-6 text-blue-200" />
                            </div>
                            <div>
                              <p className="text-[15px] font-medium text-gray-100">
                                {deck.topic}
                              </p>
                              <p className="text-[13px] text-gray-400 mt-0.5">
                                {sources.length} source
                                {sources.length !== 1 ? "s" : ""} · Just now
                              </p>
                            </div>
                          </div>
                          <div className="relative">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenArtifactDropdown(openArtifactDropdown === deck.id ? null : deck.id);
                              }}
                              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-700/50 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <MoreVertical className="w-5 h-5 text-gray-400" />
                            </button>
                            {openArtifactDropdown === deck.id && (
                              <div className="absolute right-0 top-full mt-1 w-32 bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden z-50">
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (confirm("Delete flashcard deck?")) {
                                      await deleteFlashcardDeck(id, deck.id);
                                      setSavedDecks((prev) => prev.filter((d) => d.id !== deck.id));
                                      if (activeDeckId === deck.id) {
                                        setActiveDeckId(null);
                                        setRightSidebarView("main");
                                      }
                                      setOpenArtifactDropdown(null);
                                    }
                                  }}
                                  className="w-full text-left px-3 py-2 text-sm text-red-400 hover:bg-gray-700/50 flex items-center gap-2"
                                >
                                  <Trash2 className="w-4 h-4" /> Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}

                    {/* Saved Mind Maps */}
                    {mindmaps.map((mindmap) => (
                      <div
                        key={mindmap.id}
                        className="flex flex-col p-3 hover:bg-gray-800/50 rounded-2xl transition-colors group cursor-pointer"
                        onClick={() => setActiveMindmap(mindmap)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="w-8 h-8 flex items-center justify-center shrink-0">
                              <BrainCircuit className="w-6 h-6 text-pink-400" />
                            </div>
                            <div>
                              <p className="text-[15px] font-medium text-gray-100">
                                {mindmap.topic}
                              </p>
                              <p className="text-[13px] text-gray-400 mt-0.5">
                                Interactive Map · Just now
                              </p>
                            </div>
                          </div>
                          <div className="relative">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenArtifactDropdown(openArtifactDropdown === mindmap.id ? null : mindmap.id);
                              }}
                              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-700/50 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <MoreVertical className="w-5 h-5 text-gray-400" />
                            </button>
                            {openArtifactDropdown === mindmap.id && (
                              <div className="absolute right-0 top-full mt-1 w-32 bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden z-50">
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    if (confirm("Delete mind map?")) {
                                      await handleDeleteMindmap(mindmap.id);
                                      setOpenArtifactDropdown(null);
                                    }
                                  }}
                                  className="w-full text-left px-3 py-2 text-sm text-red-400 hover:bg-gray-700/50 flex items-center gap-2"
                                >
                                  <Trash2 className="w-4 h-4" /> Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>


            </>
          ) : (
            <div className="flex flex-col h-full bg-[#1e1e1e]">
              {/* Top breadcrumb */}
              <div className="p-4 flex items-center justify-between text-sm text-gray-300">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setRightSidebarView("main")}
                    className="hover:text-white transition-colors"
                  >
                    Studio
                  </button>
                  <ChevronRight className="w-3.5 h-3.5" />
                  <span className="text-white">App</span>
                </div>
                <button className="p-1 hover:bg-gray-800 rounded transition-colors">
                  <PanelRightClose className="w-4 h-4" />
                </button>
              </div>

              {/* Title Area */}
              <div className="px-4 pb-4 border-b border-gray-800 flex items-start justify-between">
                <div>
                  <h2 className="text-xl text-white mb-1">
                    {activeDeck?.topic || "Flashcards"}
                  </h2>
                  <p className="text-xs text-gray-400 font-medium">
                    {activeDeck?.isGenerating
                      ? "Generating..."
                      : `Based on ${sources.length} source${sources.length !== 1 ? "s" : ""} · ${activeDeck?.difficulty}`}
                  </p>
                </div>
                <button className="p-1.5 hover:bg-gray-800 rounded transition-colors mt-1">
                  <Square className="w-4 h-4 text-gray-400" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-4 flex flex-col items-center">
                <p className="text-xs text-gray-500 mb-4">
                  Press "Space" to flip, "← / →" to navigate
                </p>

                {/* Flashcard Component */}
                <div
                  className={`w-full bg-[#2d2d2d] rounded-3xl p-6 flex flex-col min-h-[280px] shadow-lg relative ${!isDeckFinished ? "cursor-pointer" : ""}`}
                  onClick={() => {
                    if (!isDeckFinished) setIsFlipped(!isFlipped);
                  }}
                >
                  {!isDeckFinished ? (
                    <>
                      <div className="flex items-center justify-between text-gray-400 mb-6">
                        <span className="text-sm">
                          {activeDeck && activeDeck.cards.length > 0
                            ? `${currentCardIndex + 1} / ${activeDeck.cards.length}`
                            : "0 / 0"}
                        </span>
                        <button
                          className="p-1 hover:bg-gray-700 rounded-full transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="flex-1 flex items-center justify-center text-center">
                        {!activeDeck || activeDeck.isGenerating ? (
                          <div className="flex flex-col items-center gap-3">
                            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                            <p className="text-gray-400">
                              Generating flashcards...
                            </p>
                          </div>
                        ) : activeDeck.cards.length > 0 ? (
                          <p className="text-lg text-white leading-snug">
                            {isFlipped
                              ? activeDeck.cards[currentCardIndex].answer
                              : activeDeck.cards[currentCardIndex].question}
                          </p>
                        ) : (
                          <p className="text-gray-500">
                            No flashcards available. Click Generate to create
                            some.
                          </p>
                        )}
                      </div>

                      <div className="text-center mt-6 h-6">
                        {activeDeck &&
                          activeDeck.cards.length > 0 &&
                          !activeDeck.isGenerating && (
                            <span className="text-sm text-gray-500">
                              {isFlipped ? "See question" : "See answer"}
                            </span>
                          )}
                      </div>
                    </>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-center space-y-8 cursor-default">
                      <h3 className="text-2xl font-semibold text-white">
                        Deck Complete!
                      </h3>
                      <div className="flex gap-12">
                        <div className="text-center">
                          <p className="text-4xl text-green-500 font-bold mb-2">
                            {correctScore}
                          </p>
                          <p className="text-sm text-gray-400 font-medium">
                            Correct
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-4xl text-red-500 font-bold mb-2">
                            {wrongScore}
                          </p>
                          <p className="text-sm text-gray-400 font-medium">
                            Wrong
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setIsDeckFinished(false);
                          setCurrentCardIndex(0);
                          setCorrectScore(0);
                          setWrongScore(0);
                          setIsFlipped(false);
                        }}
                        className="px-6 py-2.5 bg-[#4f46e5] hover:bg-[#4338ca] text-white rounded-full transition-colors text-sm font-medium mt-2"
                      >
                        Restart Deck
                      </button>
                    </div>
                  )}
                </div>

                {/* Navigation Controls */}
                {!isDeckFinished && (
                  <div className="flex items-center justify-between w-full mt-6 px-2">
                    <button
                      onClick={() => {
                        setIsFlipped(false);
                        setCurrentCardIndex((prev) => Math.max(0, prev - 1));
                      }}
                      disabled={
                        currentCardIndex === 0 ||
                        !activeDeck ||
                        activeDeck.isGenerating ||
                        activeDeck.cards.length === 0
                      }
                      className="w-12 h-12 rounded-full border border-gray-700 flex items-center justify-center hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span className="text-gray-500 text-lg">←</span>
                    </button>

                    <div className="flex items-center gap-4">
                      <button
                        onClick={() => {
                          setWrongScore((s) => s + 1);
                          if (
                            activeDeck &&
                            currentCardIndex < activeDeck.cards.length - 1
                          ) {
                            setCurrentCardIndex((c) => c + 1);
                            setIsFlipped(false);
                          } else {
                            setIsDeckFinished(true);
                          }
                        }}
                        disabled={
                          !activeDeck ||
                          activeDeck.isGenerating ||
                          activeDeck.cards.length === 0
                        }
                        className="h-10 px-5 rounded-full border border-gray-700 flex items-center gap-2 hover:bg-gray-800 transition-colors disabled:opacity-50"
                      >
                        <X className="w-4 h-4 text-red-500" />
                        <span className="text-gray-400 text-sm">
                          {wrongScore}
                        </span>
                      </button>
                      <button
                        onClick={() => {
                          setCorrectScore((s) => s + 1);
                          if (
                            activeDeck &&
                            currentCardIndex < activeDeck.cards.length - 1
                          ) {
                            setCurrentCardIndex((c) => c + 1);
                            setIsFlipped(false);
                          } else {
                            setIsDeckFinished(true);
                          }
                        }}
                        disabled={
                          !activeDeck ||
                          activeDeck.isGenerating ||
                          activeDeck.cards.length === 0
                        }
                        className="h-10 px-5 rounded-full border border-gray-700 flex items-center gap-2 hover:bg-gray-800 transition-colors disabled:opacity-50"
                      >
                        <span className="text-gray-400 text-sm">
                          {correctScore}
                        </span>
                        <Check className="w-4 h-4 text-green-500" />
                      </button>
                    </div>

                    <button
                      onClick={() => {
                        setIsFlipped(false);
                        setCurrentCardIndex((prev) =>
                          Math.min(
                            (activeDeck?.cards.length || 1) - 1,
                            prev + 1,
                          ),
                        );
                      }}
                      disabled={
                        !activeDeck ||
                        currentCardIndex === activeDeck.cards.length - 1 ||
                        activeDeck.isGenerating ||
                        activeDeck.cards.length === 0
                      }
                      className="w-12 h-12 rounded-full border border-gray-700 flex items-center justify-center hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span className="text-blue-500 text-lg">→</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Footer feedback */}
              <div className="p-4 border-t border-gray-800 flex gap-3">
                <button className="flex-1 h-10 rounded-full border border-gray-700 flex items-center justify-center gap-2 text-sm text-white hover:bg-gray-800 transition-colors">
                  <span className="text-lg leading-none mb-1">👍</span>
                  Good content
                </button>
                <button className="flex-1 h-10 rounded-full border border-gray-700 flex items-center justify-center gap-2 text-sm text-white hover:bg-gray-800 transition-colors">
                  <span className="text-lg leading-none mb-1 scale-x-[-1]">
                    👎
                  </span>
                  Bad content
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Audio Customize Modal */}
      {showAudioModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1e1f23] rounded-2xl w-full max-w-4xl relative shadow-2xl border border-gray-800 flex flex-col overflow-hidden">
            {/* Header */}
            <div className="p-5 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AudioWaveform className="w-5 h-5 text-gray-300" />
                <h2 className="text-lg font-medium text-white">
                  Customize Audio Overview
                </h2>
              </div>
              <button
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
                onClick={() => setShowAudioModal(false)}
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 space-y-8 overflow-y-auto max-h-[80vh]">
              {/* Format Section */}
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-4">
                  Format
                </h3>
                <div className="grid grid-cols-4 gap-4">
                  {[
                    {
                      title: "Deep Dive",
                      desc: "A lively conversation between two hosts, unpacking and connecting topics in your sources",
                    },
                    {
                      title: "Brief",
                      desc: "A bite-sized overview to help you grasp the core ideas from your sources quickly",
                    },
                    {
                      title: "Critique",
                      desc: "An expert review of your sources, offering constructive feedback to help you improve your material",
                    },
                    {
                      title: "Debate",
                      desc: "A thoughtful debate between two hosts, illuminating different perspectives on your sources",
                    },
                  ].map((fmt) => (
                    <div
                      key={fmt.title}
                      onClick={() => setAudioFormat(fmt.title)}
                      className={`p-4 rounded-xl cursor-pointer border transition-colors ${
                        audioFormat === fmt.title
                          ? "bg-[#3b4252] border-gray-500"
                          : "bg-[#2e3440] border-transparent hover:border-gray-600"
                      }`}
                    >
                      <div className="flex justify-between items-start mb-3">
                        <span className="font-medium text-white">
                          {fmt.title}
                        </span>
                        {audioFormat === fmt.title && (
                          <Check className="w-4 h-4 text-white" />
                        )}
                      </div>
                      <p className="text-sm text-gray-300 leading-relaxed">
                        {fmt.desc}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Language & Length Settings */}
              <div className="flex gap-12">
                <div className="flex-1">
                  <h3 className="text-sm font-medium text-gray-300 mb-3">
                    Choose language
                  </h3>
                  <div className="relative">
                    <select
                      value={audioLanguage}
                      onChange={(e) => setAudioLanguage(e.target.value)}
                      className="w-full bg-[#1e1f23] border border-gray-700 text-white rounded-lg px-4 py-2.5 appearance-none focus:outline-none focus:border-blue-500"
                    >
                      <option value="English">English</option>
                      <option value="Hindi">Hindi (हिन्दी)</option>
                      <option value="Kannada">Kannada (ಕನ್ನಡ)</option>
                      <option value="Telugu">Telugu (తెలుగు)</option>
                      <option value="Tamil">Tamil (தமிழ்)</option>
                      <option value="Odia">Odia (ଓଡ଼ିଆ)</option>
                    </select>
                    <ChevronDown className="absolute right-4 top-3 w-4 h-4 text-gray-400 pointer-events-none" />
                  </div>
                </div>

                <div className="flex-1">
                  <h3 className="text-sm font-medium text-gray-300 mb-3">
                    Length
                  </h3>
                  <div className="flex items-center rounded-full border border-gray-700 overflow-hidden w-fit">
                    {["Short", "Default", "Long"].map((len) => (
                      <button
                        key={len}
                        onClick={() => setAudioLength(len)}
                        className={`px-5 py-2 text-sm font-medium flex items-center gap-2 transition-colors ${
                          audioLength === len
                            ? "bg-[#3b4252] text-white"
                            : "text-gray-400 hover:text-gray-200"
                        }`}
                      >
                        {audioLength === len && <Check className="w-4 h-4" />}
                        {len}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Instructions */}
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-3">
                  What should the AI hosts focus on in this episode?
                </h3>
                <div className="relative">
                  <textarea
                    value={audioFocus}
                    onChange={(e) => setAudioFocus(e.target.value)}
                    placeholder="Focus on when to choose one over the other for modern enterprise development..."
                    className="w-full h-28 bg-[#1e1f23] border border-blue-500/50 rounded-lg p-4 text-white placeholder-gray-500 resize-none focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  {!audioFocus && (
                    <div className="absolute right-4 top-4 px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300 pointer-events-none">
                      Tab →
                    </div>
                  )}
                </div>

                {/* Suggestions */}
                <div className="flex flex-wrap gap-3 mt-4">
                  {[
                    "+ Beginner Overview",
                    "+ Technical Comparison",
                    "+ Practical Architect",
                  ].map((pill) => (
                    <button
                      key={pill}
                      onClick={() =>
                        setAudioFocus(
                          (prev) =>
                            prev + (prev ? " " : "") + pill.replace("+ ", ""),
                        )
                      }
                      className="px-4 py-1.5 rounded-full border border-gray-700 text-sm text-gray-300 hover:bg-gray-800 transition-colors"
                    >
                      {pill}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-5 border-t border-gray-800 flex justify-end">
              <button
                onClick={handleGenerateAudio}
                disabled={isGeneratingAudio}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-full transition-colors flex items-center gap-2"
              >
                {isGeneratingAudio ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : null}
                {isGeneratingAudio ? "Generating..." : "Generate"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mind Map Customize Modal */}
      {showMindmapModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1e1f23] rounded-2xl w-full max-w-md relative shadow-2xl border border-gray-800 flex flex-col overflow-hidden">
            <div className="p-5 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <BrainCircuit className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-medium text-white">
                  Generate Mind Map
                </h2>
              </div>
              <button
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
                onClick={() => setShowMindmapModal(false)}
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="p-6 space-y-6">
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-3">Topic / Focus</h3>
                <input
                  type="text"
                  value={mindmapTopic}
                  onChange={(e) => setMindmapTopic(e.target.value)}
                  placeholder="e.g. Core Concepts, Architecture"
                  className="w-full bg-[#1e1f23] border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-3">Language</h3>
                <div className="relative">
                  <select
                    value={mindmapLanguage}
                    onChange={(e) => setMindmapLanguage(e.target.value)}
                    className="w-full bg-[#1e1f23] border border-gray-700 text-white rounded-lg px-4 py-2.5 appearance-none focus:outline-none focus:border-purple-500"
                  >
                    <option value="English">English</option>
                    <option value="Hindi">Hindi (हिन्दी)</option>
                    <option value="Kannada">Kannada (ಕನ್ನಡ)</option>
                    <option value="Telugu">Telugu (తెలుగు)</option>
                    <option value="Tamil">Tamil (தமிழ்)</option>
                    <option value="Odia">Odia (ଓଡ଼ିଆ)</option>
                  </select>
                  <ChevronDown className="absolute right-4 top-3 w-4 h-4 text-gray-400 pointer-events-none" />
                </div>
              </div>
            </div>
            <div className="p-5 border-t border-gray-800 flex justify-end">
              <button
                onClick={handleGenerateMindmap}
                disabled={isGeneratingMindmap}
                className="px-6 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-medium rounded-full transition-colors flex items-center gap-2"
              >
                {isGeneratingMindmap ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {isGeneratingMindmap ? "Generating..." : "Generate"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mind Map Viewer Fullscreen Modal */}
      {activeMindmap && (
        <div className="fixed inset-0 bg-[#111827] z-50 flex flex-col">
          <div className="p-4 border-b border-gray-800 flex items-center justify-between shrink-0">
            <div>
              <h2 className="text-lg font-medium text-white">
                {activeMindmap.topic || "Mind Map"}
              </h2>
              <p className="text-xs text-gray-400 mt-1">Based on selected sources</p>
            </div>
            <button
              onClick={() => setActiveMindmap(null)}
              className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-gray-300 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex-1 relative">
            <MindMapViewer data={activeMindmap.data} />
          </div>
        </div>
      )}

      {/* Add Sources Modal */}
      {showAddSourcesModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-2xl w-full max-w-4xl relative">
            {/* Close Button */}
            <button
              className="absolute top-6 right-6 p-2 hover:bg-gray-800 rounded-lg transition-colors"
              onClick={() => setShowAddSourcesModal(false)}
            >
              <X className="w-6 h-6" />
            </button>

            <div className="p-8">
              {/* Title */}
              <h2 className="text-3xl font-normal mb-8 text-center">
                Create Audio and Video Overviews from
              </h2>

              {/* Search Bar */}
              <div className="mb-8 border-2 border-blue-600 rounded-2xl p-4 bg-gray-800/50">
                <div className="text-sm text-gray-400 mb-3">
                  Search the web for new sources
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleWebSearch()}
                      placeholder="What do you want to learn about?"
                      className="w-full bg-transparent outline-none text-gray-200 placeholder-gray-500"
                    />
                  </div>
                  <button
                    onClick={handleWebSearch}
                    disabled={!searchQuery.trim() || uploading}
                    className="p-2 hover:bg-gray-700 rounded-lg disabled:opacity-50"
                  >
                    {uploading ? (
                      <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                    ) : (
                      <Search className="w-5 h-5 text-blue-500" />
                    )}
                  </button>
                </div>
              </div>

              {/* Drop Zone */}
              <div className="border-2 border-dashed border-gray-700 rounded-2xl p-12 mb-6">
                <div className="text-center">
                  <h3 className="text-2xl mb-3">or drop your files</h3>
                  <p className="text-gray-400">
                    pdf, images, docs, audio,{" "}
                    <span className="underline">and more</span>
                  </p>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-center gap-4 mt-12">
                  <input
                    type="file"
                    accept="application/pdf,.doc,.docx,.pptx"
                    className="hidden"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                  />
                  <button
                    className="flex items-center gap-2 px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-full transition-colors disabled:opacity-50"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                  >
                    {uploading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Upload className="w-5 h-5" />
                    )}
                    <span>{uploading ? "Uploading..." : "Upload files"}</span>
                  </button>
                  <button
                    onClick={handleWebsiteUpload}
                    disabled={uploading}
                    className="flex items-center gap-2 px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-full transition-colors disabled:opacity-50"
                  >
                    <LinkIcon className="w-5 h-5" />
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 bg-red-600 rounded-full"></span>
                      Websites
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Flashcards Modal */}
      {showFlashcardsModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1a1a1a] rounded-2xl w-full max-w-3xl relative overflow-hidden border border-gray-800 shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-800">
              <div className="flex items-center gap-3">
                <div className="relative flex items-center justify-center">
                  <CreditCard className="w-6 h-6 text-gray-200" />
                  <div className="absolute -top-1 -right-1">
                    <span className="text-[10px]">★</span>
                  </div>
                </div>
                <h2 className="text-2xl font-medium text-gray-100">
                  Customize Flashcards
                </h2>
              </div>
              <button
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors text-gray-400 hover:text-white"
                onClick={() => setShowFlashcardsModal(false)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 pb-24">
              <div className="flex flex-col md:flex-row gap-8 mb-8">
                {/* Number of Cards */}
                <div className="flex-1">
                  <p className="text-sm text-gray-300 mb-3">Number of Cards</p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setFlashcardCount("5")}
                      className={`px-5 py-2.5 rounded-full border text-sm transition-colors ${flashcardCount === "5" ? "border-[#2d3748] bg-[#2d3748] text-gray-100" : "border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800"}`}
                    >
                      {flashcardCount === "5" && (
                        <Check className="w-4 h-4 inline mr-2" />
                      )}
                      Fewer
                    </button>
                    <button
                      onClick={() => setFlashcardCount("10")}
                      className={`px-5 py-2.5 rounded-full border text-sm transition-colors ${flashcardCount === "10" ? "border-[#2d3748] bg-[#2d3748] text-gray-100" : "border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800"}`}
                    >
                      {flashcardCount === "10" && (
                        <Check className="w-4 h-4 inline mr-2" />
                      )}
                      Standard (Default)
                    </button>
                    <button
                      onClick={() => setFlashcardCount("20")}
                      className={`px-5 py-2.5 rounded-full border text-sm transition-colors ${flashcardCount === "20" ? "border-[#2d3748] bg-[#2d3748] text-gray-100" : "border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800"}`}
                    >
                      {flashcardCount === "20" && (
                        <Check className="w-4 h-4 inline mr-2" />
                      )}
                      More
                    </button>
                  </div>
                </div>

                {/* Level of Difficulty */}
                <div className="flex-1">
                  <p className="text-sm text-gray-300 mb-3">
                    Level of Difficulty
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setFlashcardDifficulty("Easy")}
                      className={`px-5 py-2.5 rounded-full border text-sm transition-colors ${flashcardDifficulty === "Easy" ? "border-[#2d3748] bg-[#2d3748] text-gray-100" : "border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800"}`}
                    >
                      {flashcardDifficulty === "Easy" && (
                        <Check className="w-4 h-4 inline mr-2" />
                      )}
                      Easy
                    </button>
                    <button
                      onClick={() => setFlashcardDifficulty("Medium")}
                      className={`px-5 py-2.5 rounded-full border text-sm transition-colors ${flashcardDifficulty === "Medium" ? "border-[#2d3748] bg-[#2d3748] text-gray-100" : "border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800"}`}
                    >
                      {flashcardDifficulty === "Medium" && (
                        <Check className="w-4 h-4 inline mr-2" />
                      )}
                      Medium (Default)
                    </button>
                    <button
                      onClick={() => setFlashcardDifficulty("Hard")}
                      className={`px-5 py-2.5 rounded-full border text-sm transition-colors ${flashcardDifficulty === "Hard" ? "border-[#2d3748] bg-[#2d3748] text-gray-100" : "border-gray-700 bg-transparent text-gray-300 hover:bg-gray-800"}`}
                    >
                      {flashcardDifficulty === "Hard" && (
                        <Check className="w-4 h-4 inline mr-2" />
                      )}
                      Hard
                    </button>
                  </div>
                </div>
              </div>

              {/* Topic */}
              <div>
                <p className="text-sm text-gray-300 mb-3">
                  What should the topic be?
                </p>
                <div className="w-full h-40 border border-[#3b82f6] rounded-lg bg-transparent p-4 text-sm text-gray-400 focus-within:ring-1 focus-within:ring-[#3b82f6] relative cursor-text">
                  <div className="absolute inset-0 p-4 pointer-events-none">
                    <div className="flex">
                      <div className="w-px h-5 bg-gray-400 animate-pulse mr-1"></div>
                      <p>Things to try</p>
                    </div>
                    <ul className="list-disc ml-6 mt-2 space-y-1.5 text-gray-400">
                      <li>
                        The flashcards must be restricted to a specific source
                        (e.g. "the article about Italy")
                      </li>
                      <li>
                        The flashcards must focus on a specific topic like
                        "Newton's second law"
                      </li>
                      <li>
                        The card fronts must be short (1-5 words) for
                        memorization
                      </li>
                    </ul>
                  </div>
                  <textarea
                    value={flashcardTopic}
                    onChange={(e) => setFlashcardTopic(e.target.value)}
                    className="w-full h-full bg-transparent resize-none outline-none text-gray-200 z-10 relative focus:bg-[#1a1a1a]"
                    placeholder="Things to try..."
                  />
                </div>
              </div>
            </div>

            {/* Footer with Generate button */}
            <div className="absolute bottom-0 left-0 right-0 p-6 flex justify-end bg-gradient-to-t from-[#1a1a1a] to-transparent">
              <button
                onClick={() => handleGenerateFlashcards()}
                className="bg-[#4f46e5] hover:bg-[#4338ca] text-white px-6 py-2.5 rounded-full text-sm font-medium transition-colors"
              >
                Generate
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Website URLs Modal */}
      {showWebsiteModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1a1a1a] rounded-2xl w-full max-w-2xl relative overflow-hidden border border-gray-800 shadow-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-medium text-gray-100 flex items-center gap-2">
                <LinkIcon className="w-5 h-5" />
                Website URLs
              </h2>
              <button
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors text-gray-400 hover:text-white"
                onClick={() => setShowWebsiteModal(false)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-gray-400 mb-4">
              Paste in Website URLs below to upload as a source.
            </p>

            <div className="border border-blue-500/50 rounded-xl overflow-hidden mb-4">
              <textarea
                value={websiteUrls}
                onChange={(e) => setWebsiteUrls(e.target.value)}
                placeholder="Paste any links"
                className="w-full h-40 bg-transparent text-gray-200 p-4 outline-none resize-none placeholder-gray-500"
              />
            </div>

            <div className="text-xs text-gray-400 mb-6 space-y-1">
              <p>• To add multiple URLs, separate with a space or new line.</p>
              <p>
                • Only the visible text on the website will be imported at this
                time.
              </p>
              <p>• Paid articles are not supported.</p>
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleWebsiteSubmit}
                disabled={!websiteUrls.trim() || uploading}
                className="px-6 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white rounded-full transition-colors flex items-center gap-2"
              >
                {uploading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : null}
                Insert
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
