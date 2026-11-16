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
- **AI Models**: **Azure OpenAI** powers chat generation and text embeddings. NVIDIA API powers visual captions and semantic document reranking.
- **Primary Database**: **MongoDB** stores notebook metadata, chat histories, flashcard decks, and mind map structures as BSON documents.
- **Object Storage**: **GridFS** stores uploaded PDFs and generated podcast MP3s in chunked collections.
- **Cache & Queue**: **Redis** provides response caching for RAG queries and cache invalidation on source changes.
- **Vector Database**: **Qdrant** stores and indexes document embeddings for ultra-fast semantic search.
- **Visual Retrieval**: Set `ENABLE_VISUAL_RETRIEVAL=false` to disable image-vector search, or configure `OPENROUTER_EMBEDDING_TIMEOUT` (default `10` seconds) to bound its query-time API wait.
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

# --- AZURE OPENAI (Chat and Text Embeddings) ---
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_CHAT_DEPLOYMENT=your_chat_deployment
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=your_embedding_deployment

# --- NVIDIA API (Vision Captions and Reranker) ---
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

# 4. Start the FastAPI server (runs on port 8001 by default)
npm run backend
# Alternatively run: uvicorn api.index:app --host 0.0.0.0 --port 8001 --reload
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

## 📊 Evaluation

The RAG pipeline is evaluated with a [`pydantic_evals`](https://ai.pydantic.dev/evals/) suite in `api/evals/`: 34 cases over two reference papers (19 answerable across factual, summarization, multi-hop and visual questions, plus 15 adversarial questions the sources cannot answer). It measures Recall@5 and MRR over reranked documents, citation accuracy, LLM-judged faithfulness and answer relevance (judge model must differ from the answer model), and refusal behavior (adversarial refusal rate and false-refusal rate reported separately). Each evaluation runs 3 times and reports mean and spread with sample sizes; results are saved to `api/evals/results/`.

```bash
cd api
python -m evals.fetch_reference_pdfs
python -m evals.bootstrap_notebook
EVAL_JUDGE_MODEL=azure:<other-deployment> python -m evals.run_evals
```

**Results** — 3 runs of 34 cases (19 answerable, 15 adversarial) on two arXiv papers; answer model `gpt-4.1`, judge `o4-mini` (a different model); the code revision is recorded in the file's `git_commit` field. Mean ± std over runs; `n` is cases scored per run. Raw data: `api/evals/results/20261111T164809Z.json`.

| Metric | Mean ± std | n per run |
|---|---|---|
| Adversarial refusal rate | 1.000 ± 0.000 | 15 |
| False-refusal rate (answerable cases refused) | 0.071 ± 0.030 | 19 / 19 / 18 |
| Refusal correctness | 0.960 ± 0.017 | 34 / 34 / 33 |
| Faithfulness (LLM judge) | 0.965 ± 0.011 | 18 / 17 / 17 |
| Answer relevance (LLM judge) | 0.893 ± 0.053 | 19 / 19 / 18 |
| Citation accuracy | 0.968 ± 0.001 | 19 / 19 / 18 |
| Recall@5 | 0.487 ± 0.015 | 19 / 19 / 18 |
| MRR | 0.324 ± 0.005 | 19 / 19 / 18 |

Caveats: one of 102 pipeline calls failed (a DNS error reaching Qdrant, run 3), so run 3 has 33 cases; no judge calls failed. Faithfulness excludes adversarial and refused cases (counted in the JSON as not applicable). Recall@5 is strict, counting the fraction of expected (file, page) pairs in the top 5, and is lowest on multi-hop questions (0.235 in the baseline, 0.217 in the post-fix run). In this baseline the visual index was empty (image embedding requests were being rejected by the provider and visual search raised on every query, both since fixed), so the visual category was answered from text retrieval only; `visual-resnet-figure1` was refused in all 3 runs. The sample is small (34 cases, 2 papers), so treat these as a regression baseline, not a general accuracy claim. See `api/evals/README.md` for details.

**Visual-path fixes: before vs after.** After fixing the visual path (image media type, data-URI format, embedding request shape, `query_points`, payload indexes), the suite was rerun against a fully populated visual index (3 images). It is a **single run** (`api/evals/results/20261112T084022Z.json`; code revision in its `git_commit` field plus indexing-only timeout changes), because the free-tier embedding quota (50 requests/day) does not allow three; compare against the 3-run baseline with that in mind. From the run log (not stored in the results file): 14 of 34 queries skipped visual retrieval on the 10 s query-embedding timeout.

| Metric | Before (3-run mean) | After (1 run) | n (after) |
|---|---|---|---|
| Recall@5 | 0.487 | 0.425 | 19 |
| MRR | 0.324 | 0.300 | 19 |
| Citation accuracy | 0.968 | 0.937 | 19 |
| Faithfulness | 0.965 | 0.952 | 18 |
| Answer relevance | 0.893 | 0.895 | 19 |
| Adversarial refusal rate | 1.000 | 1.000 | 15 |
| False-refusal rate | 0.071 | 0.053 | 19 |
| Visual-category Recall@5 | 0.400 | 0.200 | 5 |

No improvement is demonstrated: image chunks now reach the answers (an image-asset citation appears in 22 of 34 cases versus about 5 per run before), but retrieval metrics are flat to slightly lower, and the visual category's drop comes from a single case (`visual-transformer-figure2`) in one run, which is within run-to-run noise. Do not read this as a visual-retrieval gain or loss; a fair comparison needs 3 runs with a paid embedding tier and a longer query timeout.

---

## 🔒 Security & Performance Considerations

- **Secure Deletion**: The system is built with robust hard-delete functionality. Deleting a notebook instantly purges its associated vectors from Qdrant, its PDFs/MP3s from GridFS, and its metadata from MongoDB.
- **Chunked Processing**: To bypass strict character limits imposed by third-party TTS engines (like Sarvam AI's 500-character limit), the backend employs intelligent regex-based text chunking, ensuring seamless audio generation without dropping sentences.
- **Optimized UI**: The Next.js frontend uses lazy loading and optimized React state management to ensure the chat interface and heavily animated components remain smooth even when handling large RAG contexts.
- **Redis Caching**: RAG responses are cached in Redis (1h TTL) and automatically invalidated when sources are added or deleted, reducing redundant LLM calls for repeated questions.
