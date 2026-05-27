# 🧠 AI Notebooks: The Intelligent Study Companion

Welcome to **AI Notebooks**, an advanced, full-stack learning platform designed to transform static documents into interactive, multimodal learning experiences. 

By leveraging **Retrieval-Augmented Generation (RAG)**, large language models, and cutting-edge text-to-speech technologies, this application allows users to upload PDFs and instantly generate conversational chatbots, interactive flashcards, visual mind maps, and studio-quality multilingual podcasts based strictly on the uploaded source material.

---

## 🌟 Comprehensive Feature Set

### 1. Document Ingestion & RAG Chat
- **PDF Parsing**: Upload any PDF document. The backend automatically extracts the text, breaks it down into semantically meaningful chunks, and generates vector embeddings.
- **Vector Search**: Chunks are stored in **Qdrant**. When you ask a question, the system performs a similarity search to find the most relevant context.
- **Cited Responses**: The LLM synthesizes an answer using only the retrieved context and provides inline citations so you can trace facts back to the exact source document.

### 2. Studio-Quality Multilingual Podcasts
- **Dynamic Scripting**: Converts dry academic text into a lively, unscripted back-and-forth podcast script between two AI hosts (Shubh and Shruti). The script includes banter, analogies, and natural interruptions.
- **Language Support**: Translate and synthesize the podcast into various regional languages (Hindi, Kannada, Bengali, Tamil, etc.). 
- **Voice Synthesis**: Integrates directly with **Sarvam AI** to generate high-fidelity MP3 streams. The system automatically handles chunking text to bypass API limits and dynamically assigns male and female voices based on the script's speaker tags.

### 3. Active Recall with AI Flashcards
- **Automated Deck Generation**: Instead of manually creating study materials, the AI analyzes the document context and generates a full deck of Flashcards (Question/Answer pairs).
- **Interactive UI**: A sleek, flippable flashcard UI built in Next.js allows you to test your knowledge dynamically. 

### 4. Visual Learning with Mind Maps
- **Hierarchical Extraction**: The LLM extracts the core topics and subtopics from your document and structures them into a strict hierarchical JSON format.
- **Dynamic Rendering**: The frontend parses the JSON and renders an interactive, draggable mind map using a custom node-graph visualizer, perfect for visual learners.

---

## 🏗️ System Architecture & Tech Stack

The project is split into two heavily decoupled layers: a React-based frontend and a Python-based AI backend.

### Frontend (User Interface)
- **Framework**: **Next.js 16+** (App Router) with React 19.
- **Styling**: **Tailwind CSS** for a fully responsive, modern dark-mode interface.
- **Icons**: **Lucide React** for lightweight, consistent iconography.
- **Markdown Handling**: `react-markdown` and `remark-gfm` to perfectly render LLM outputs (tables, bold text, code blocks, etc.).

### Backend (AI & Data Pipeline)
- **Server**: **Flask** (Python 3.10+) serving a robust RESTful API.
- **Primary Database**: **Supabase (PostgreSQL)** stores user data, notebook metadata, chat histories, flashcard decks, and mind map structures.
- **Object Storage**: **Supabase Storage** securely hosts uploaded PDFs and generated podcast MP3s.
- **Vector Database**: **Qdrant** stores and indexes document embeddings for ultra-fast semantic search.
- **Audio Engine**: **Sarvam AI API** handles the text-to-speech generation.

---

## 🚀 Installation & Local Setup

Follow these steps to run the complete stack on your local machine.

### Prerequisites
1. **Node.js** (v18 or higher)
2. **Python** (v3.10 or higher)
3. A **Supabase** account (Create a new project to get your URL and Anon Key).
4. A **Qdrant** instance (Local docker container or Qdrant Cloud).
5. A **Sarvam AI** API Key (For podcast generation).

### Step 1: Environment Variables
Create a `.env` (or `.env.local`) file in the root of your project. You will need to configure the following keys:

```ini
# --- SUPABASE ---
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key

# --- QDRANT ---
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key

# --- SARVAM AI ---
SARVAM_API_KEY=your_sarvam_api_subscription_key

# --- LLM PROVIDER (OpenAI/Gemini/Anthropic depending on your setup) ---
OPENAI_API_KEY=your_llm_api_key
```

### Step 2: Backend Setup (Python/Flask)
Open a terminal in the root directory of the project:

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
# source venv/bin/activate

# 3. Install the required Python packages
pip install -r requirements.txt

# 4. Start the Flask server (runs on port 5328 by default)
npm run backend
# Alternatively run: python -m flask --app api/index.py run --port 5328 --debug
```

### Step 3: Frontend Setup (Next.js)
Open a *second* terminal window in the root directory:

```bash
# 1. Install Node modules
npm install

# 2. Start the Next.js development server
npm run dev
```

The application will now be running. Open `http://localhost:3000` in your browser to start building your AI Notebooks!

---

## 📂 Codebase Structure Deep Dive

```text
├── api/                        # Python Flask Backend
│   ├── audio/                  # Audio pipeline
│   │   ├── audio_gen.py        # Sarvam API integration & text chunking logic
│   │   ├── prompt.py           # Podcast dialogue generation prompts
│   │   └── script_gen.py       # LLM call to write the podcast script
│   ├── db/                     # Database wrapper clients
│   │   ├── base.py             # Main Supabase DB client class
│   │   ├── flashcards.py       # CRUD operations for Flashcards
│   │   ├── mindmaps.py         # CRUD operations for Mind Maps
│   │   ├── notebooks.py        # CRUD operations for Notebook Workspaces
│   │   └── podcasts.py         # CRUD operations for Audio Overviews
│   ├── ingestion/              # Document processing
│   │   ├── pdf_parser.py       # Extracts text from uploaded PDFs
│   │   └── splitter.py         # Chunks text into semantic blocks for Qdrant
│   ├── mindmap/                # Mind map structure generation via LLM
│   ├── pipeline/               # The core RAG retrieval & QA pipeline
│   └── index.py                # Flask application initialization and REST routes
│
├── app/                        # Next.js Frontend (App Router)
│   ├── notebooks/[id]/         # Dynamic route for individual notebooks
│   │   └── page.tsx            # Main workspace UI (Chat, Sidebar, Modals)
│   ├── layout.tsx              # Global layout and font definitions
│   └── page.tsx                # Landing/Home page
│
├── components/                 # Reusable UI components (Modals, Icons, etc.)
├── lib/                        # Shared frontend utilities (API fetchers, class mergers)
├── public/                     # Static assets (Favicon, images)
├── package.json                # Frontend dependencies and npm scripts
└── requirements.txt            # Backend Python dependencies
```

---

## 🔒 Security & Performance Considerations

- **Secure Deletion**: The system is built with robust hard-delete functionality. Deleting a notebook instantly purges its associated vectors from Qdrant, its PDFs/MP3s from Supabase Storage, and its metadata from the Supabase relational database.
- **Chunked Processing**: To bypass strict character limits imposed by third-party TTS engines (like Sarvam AI's 500-character limit), the backend employs intelligent regex-based text chunking, ensuring seamless audio generation without dropping sentences.
- **Optimized UI**: The Next.js frontend uses lazy loading and optimized React state management to ensure the chat interface and heavily animated components remain smooth even when handling large RAG contexts.
