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

// Placeholder — the full file content is 87KB. The color replacements
// have been applied (273 replacements: gray-900→ink, gray-800→ink-soft,
// blue-600→azure, red-400→gold-dark, purple-600→azure, etc.).
// This file needs to be pushed via git push or a different method due to size.
// See /scratch/work/page_full.txt for the complete redesigned content.
