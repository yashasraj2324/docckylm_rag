# 🧠 AI Notebooks: The Intelligent Study Companion

Welcome to **AI Notebooks**, an advanced, full-stack learning platform designed to transform static documents into interactive, multimodal learning experiences. 

By leveraging **Retrieval-Augmented Generation (RAG)**, large language models, and cutting-edge text-to-speech technologies, this application allows users to upload PDFs and instantly generate conversational chatbots, interactive flashcards, visual mind maps, and studio-quality multilingual podcasts based strictly on the uploaded source material.

---

## 📸 Showcase

**1. Main Chat Interface & Interactive Flashcards**
![Main Interface with Flashcards](./public/screenshots/flashcards.png)

**2. RAG Source Selection & Podcasts**
![Document Chat & Audio Podcasts](./public/screenshots/podcast_gen.png)

**3. Hierarchical Mind Map Generation**
![Mind Map Generation](./public/screenshots/mindmap.png)

**4. Document Upload Overlay**
![Document Upload Overlay](./public/screenshots/add_source.png)

**5. Clean Notebook View**
![Notebook View](./public/screenshots/notebook.png)


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
- **Styling**: **Tailwind CSS** with a focused 4-color palette (white, black, yellow, blue) for a clean, intentional design.
- **Icons**: **Lucide React** for lightweight, consistent iconography.
- **Markdown Handling**: `react-markdown` and `remark-gfm` to perfectly render LLM outputs (tables, bold text, code blocks, etc.).

### Backend (AI & Data Pipeline)
- **Server**: **FastAPI** (Python 3.10+, async) serving a robust RESTful API with automatic OpenAPI docs.
- **AI Models**: **NVIDIA API** powers the Large Language Models (LLMs), Text Embeddings, and semantic Document Reranking.
- **Primary Database**: **MongoDB** stores notebook metadata, chat histories, flashcard decks, and mind map structures as BSON documents.
- **Object Storage**: **GridFS** stores uploaded PDFs and generated podcast MP3s in chunked collections.
- **Cache & Queue**: **Redis** provides response caching for RAG queries and cache invalidation on source changes.
- **Vector Database**: **Qdrant** stores and indexes document embeddings for ultra-fast semantic search.
- **Audio Engine**: **Sarvam AI API** handles the text-to-speech generation.

---

## 🚀 Installation & Local Setup

Follow these steps to run the complete stack on your local machine.

### Prerequisites
1. **Node.js** (v18 or higher)
2. **Python** (v3.10 or higher)
3. A **MongoDB** instance (MongoDB Atlas free M0 tier or local Docker).
4. A **Redis** instance (local Docker or Upstash free tier).
5. A **Qdrant** instance (Local docker container or Qdrant Cloud).
6. A **Sarvam AI** API Key (For podcast generation).

### Step 1: Environment Variables
Create a `.env` (or `.env.local`) file in the root of your project. You will need to configure the following keys:

```ini
# --- MONGODB ---
# Connection string for MongoDB Atlas or local instance
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/docckylm
MONGODB_DB=docckylm

# --- REDIS ---
REDIS_URL=redis://localhost:6379/0

# --- SINGLE-USER DEMO ---
# A fixed UUID for the single-user demo. Generate one with:
#   python -c "import uuid; print(uuid.uuid4())"
DEMO_USER_ID=your_fixed_demo_user_uuid

# --- QDRANT ---
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key

# --- SARVAM AI ---
SARVAM_API_KEY=your_sarvam_api_subscription_key

# --- NVIDIA API (LLM, Embeddings, Reranker) ---
NVIDIA_API_KEY=your_nvidia_api_key
```

### Step 2: Backend Setup (Python/FastAPI)
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

# 4. Start the FastAPI server (runs on port 5328 by default)
npm run backend
# Alternatively run: uvicorn api.index:app --host 0.0.0.0 --port 5328 --reload
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
├── api/                        # Python FastAPI Backend
│   ├── audio/                  # Audio pipeline
│   │   ├── audio_gen.py        # Sarvam API integration & text chunking logic
│   │   ├── prompt.py           # Podcast dialogue generation prompts
│   │   └── script_gen.py       # LLM call to write the podcast script
│   ├── cache/                  # Redis client for caching and rate limiting
│   │   └── redis_client.py    # Response cache, embedding cache, rate limiter
│   ├── db/                     # Database wrapper clients
│   │   ├── base.py             # Main Database class (MongoDB + GridFS)
│   │   ├── mongo_client.py     # MongoDB connection builder with auto-indexes
│   │   ├── gridfs_client.py    # GridFS upload/download/delete helpers
│   │   ├── flashcards.py       # CRUD operations for Flashcards
│   │   ├── mindmaps.py         # CRUD operations for Mind Maps
│   │   ├── notebooks.py        # CRUD operations for Notebook Workspaces
│   │   └── podcasts.py         # CRUD operations for Audio Overviews
│   ├── ingestion/              # Document processing
│   │   ├── pdf_parser.py       # Extracts text from uploaded PDFs
│   │   └── splitter.py         # Chunks text into semantic blocks for Qdrant
│   ├── mindmap/                # Mind map structure generation via LLM
│   ├── pipeline/               # The core RAG retrieval & QA pipeline
│   └── index.py                # FastAPI application initialization and REST routes
│
├── app/                        # Next.js Frontend (App Router)
│   ├── notebooks/[id]/         # Dynamic route for individual notebooks
│   │   └── page.tsx            # Main workspace UI (Chat, Sidebar, Modals)
│   ├── layout.tsx              # Global layout and font definitions
│   └── page.tsx                # Landing/Home page
│
├── package.json                # Frontend dependencies and npm scripts
└── requirements.txt            # Backend Python dependencies
```

---

## 🔒 Security & Performance Considerations

- **Secure Deletion**: The system is built with robust hard-delete functionality. Deleting a notebook instantly purges its associated vectors from Qdrant, its PDFs/MP3s from GridFS, and its metadata from MongoDB.
- **Chunked Processing**: To bypass strict character limits imposed by third-party TTS engines (like Sarvam AI's 500-character limit), the backend employs intelligent regex-based text chunking, ensuring seamless audio generation without dropping sentences.
- **Optimized UI**: The Next.js frontend uses lazy loading and optimized React state management to ensure the chat interface and heavily animated components remain smooth even when handling large RAG contexts.
- **Redis Caching**: RAG responses are cached in Redis (1h TTL) and automatically invalidated when sources are added or deleted, reducing redundant LLM calls for repeated questions.
