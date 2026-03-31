# ApexFlow — Multi-Agent AI Assistant

ApexFlow is an autonomous AI assistant built on a **hierarchical multi-agent architecture**. An orchestrator delegates tasks to six specialist agents — Research, Browser, Documents, Knowledge, Location, and System — each with its own focused tool set. Optionally define success criteria and an evaluator loop ensures the job is done right.

It maintains persistent memory across sessions: it remembers facts about you and can resume previous conversations where you left off.

---

![Screenshot of the application](assets/ApexFlowScreenShot.png)

---

## Architecture

ApexFlow uses a **hierarchical orchestrator pattern** built on [LangGraph](https://github.com/langchain-ai/langgraph):

```
User input (task + optional success criteria)
        │
   ┌────┴─────┐
   │ ORCHESTR.│  ◄──────────────────────────┐
   └────┬─────┘                             │
        │ delegates to agent?               │
      yes │           no                    │
   ┌─────┴──────┐   ┌───────────┐          │
   │ SUB-AGENTS │   │ EVALUATOR │          │
   │  (as tools)│   │ (optional)│          │
   └─────┬──────┘   └─────┬─────┘          │
         │                │                │
         └────────────────┘                │
                     met? │                │
                   yes /   \ no            │
                   END       └─────────────┘
```

1. The **orchestrator** (GPT-5.2) receives your task, user profile context, and a set of specialist agents exposed as callable tools.
2. It delegates sub-tasks to the right agent with a clear instruction. Each agent has its own set of tools.
3. When the orchestrator produces a response, the **evaluator** (GPT-5.2) checks it against your success criteria using structured output — but only if you provided explicit criteria. Without criteria, the evaluator is skipped entirely.
4. If the criteria are not met, the evaluator feeds back and the orchestrator tries again.
5. The loop ends when the task is complete or user input is needed.

### Specialist Agents

| Agent | Capabilities | Tools |
|---|---|---|
| **Research** | Web search, Wikipedia, arXiv papers, YouTube transcripts | Google Serper, Wikipedia API, arXiv API, YouTube Transcript API |
| **Browser** | Navigate websites, click links, fill forms, extract content | Playwright (Chromium), screenshots, page extraction |
| **Documents** | File management, PDFs, spreadsheets, charts | File I/O, PDF read/create, CSV/Excel, matplotlib charts |
| **Knowledge** | Search and manage personal document collection | ChromaDB semantic search, document indexing |
| **Location** | Address analysis, nearby amenities, commute times | Google Places, Maps, apartment search |
| **System** | Task scheduling, notifications, Python execution | APScheduler, Pushover, Docker-sandboxed Python REPL |

### Persistent memory

- **Session history** — each conversation is stored in SQLite and can be resumed at any time.
- **User profile** — facts learned about you (name, location, occupation, interests, preferred language, output format, technical level, etc.) are extracted automatically via LLM and injected into future sessions so ApexFlow always has context.
- **Checkpoints** — LangGraph state is checkpointed to SQLite, enabling mid-conversation recovery.

---

## What it can do

### Web & Internet
- **Web navigation** — browse URLs, click links, fill forms, take screenshots via a real Chromium browser (Playwright)
- **Web search** — query Google in real-time via Serper for up-to-date results
- **Data extraction** — pull text and hyperlinks from any web page

### Research
- **Wikipedia** — look up general knowledge topics
- **arXiv** — search and retrieve academic papers by topic, author, or keyword
- **YouTube transcripts** — fetch and analyse transcripts from any YouTube video

### Files & Documents
- **File management** — read, write, move, copy, delete, and list files inside the sandbox directory
- **PDF reader** — extract and analyse text from PDF files (page-by-page extraction)
- **PDF creator** — generate properly formatted PDF files with Unicode font support

### Structured Data
- **Spreadsheet reader** — read CSV and Excel (.xlsx) files from the sandbox; returns column names, row count, and a data preview
- **Spreadsheet writer** — create CSV or Excel files in the sandbox from structured data (headers + rows)
- **Chart generator** — produce PNG bar, line, pie, or scatter charts from any dataset via matplotlib

### Knowledge Base (RAG)
- **Semantic search** — search your own indexed documents (PDFs, text files, markdown, CSV) using natural language queries
- **Document indexing** — upload or drop files into `sandbox/knowledge/` and index them with one click; documents are chunked and embedded via OpenAI
- **Index management** — add, remove, and re-index documents; unchanged files are skipped automatically
- **Grounded answers** — the agent retrieves relevant chunks from your documents to answer questions with source citations

### Location & Apartment Search
- **Family-friendly address analysis** — pass any address and get a comprehensive suitability report for families
- **Nearby amenities** — automatically finds the nearest Grundschule, Kita, Supermarket, Cafe, Playground, and Restaurant with exact walking times and distances (via Google Distance Matrix API)
- **Commute calculation** — calculates driving and public transport times to predefined work addresses
- **Interactive map** — generates a Leaflet/OpenStreetMap HTML map with color-coded markers for home, amenities, and work locations

### Code & Computation
- **Python execution** — run Python code in a Docker-sandboxed container for calculations, data processing, or scripting. Each execution spins up an ephemeral container with network disabled, memory limits, and CPU caps — the host machine is never exposed to arbitrary code.

### Task Scheduling
- **Schedule tasks** — set up recurring background jobs with cron expressions (e.g. "check the news every morning at 8 AM")
- **List & cancel tasks** — view all scheduled tasks with their status and last results, or cancel them by ID
- **Push notification integration** — optionally get notified via Pushover when a scheduled task produces results

---

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- [Docker](https://docs.docker.com/get-docker/) (required for the sandboxed Python REPL)
- A Chromium-compatible browser (installed automatically by Playwright)

### Install dependencies

```bash
uv sync
playwright install chromium
```

### Build the Python sandbox image

The sandboxed Python REPL runs code inside an ephemeral Docker container. Build the image once:

```bash
docker build -f Dockerfile.python-sandbox -t apexflow-python-sandbox .
```

The image is also auto-built on first REPL invocation if it doesn't exist, but pre-building avoids the initial delay.

### Configure API keys

Create a `.env` file in the project root:

```env
# Required — LLM provider
OPENAI_API_KEY=your_openai_api_key

# Web search (required for Google search tool)
SERPER_API_KEY=your_serper_api_key

# Google Maps APIs (required for apartment search + Google Places tool)
# Needs Places API, Geocoding API, and Distance Matrix API enabled
GPLACES_API_KEY=your_google_maps_api_key

# Push notifications (optional)
PUSHOVER_USER=your_pushover_user_key
PUSHOVER_TOKEN=your_pushover_app_token

# Observability (optional)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=apexflow
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

Only `OPENAI_API_KEY` is required to run the core agent. Other keys unlock specific tools.

### Run the app

```bash
uv run app.py
```

The Gradio UI opens in your browser automatically. Stop with `Ctrl+C`.

---

## Testing

### Install test dependencies

Test dependencies are part of the `dev` group and are included with:

```bash
uv sync --dev
```

### Run the tests

```bash
# Run all tests
uv run pytest

# Verbose output with short tracebacks
uv run pytest -v --tb=short

# Run a specific test class
uv run pytest tests/test_tools_unit.py::TestCreatePdf -v

# Run a specific test
uv run pytest tests/test_tools_unit.py::TestGetYoutubeTranscript::test_joins_transcript_lines -v
```

### Coverage report

```bash
# Terminal summary (shows uncovered lines)
uv run pytest --cov --cov-report=term-missing

# HTML report (open htmlcov/index.html in a browser)
uv run pytest --cov --cov-report=html
```

---

## Usage

1. Open the browser UI (launches at `http://localhost:7860` by default).
2. Select an existing session from the dropdown or create a new one with **+ New Session**.
3. Optionally rename the session to something meaningful.
4. Type your task in the **message** field.
5. Optionally describe your **success criteria** — what does "done" look like? When provided, an evaluator checks the response and loops the orchestrator if criteria are not met.
6. Click **Go!** and watch ApexFlow work, including live tool call feedback in the chat.
7. Use **Reset** to clear the current session's in-progress context.

---

## Project structure

```
AI-Assistant/
├── app.py               # Gradio web UI and application entry point
├── sidekick.py          # Orchestrator: multi-agent LangGraph state machine
├── config.py            # Centralized configuration and constants
├── agents/              # Specialist sub-agents (one per domain)
│   ├── base.py          # BaseAgent: create_react_agent wrapper with run()
│   ├── research.py      # ResearchAgent
│   ├── browser.py       # BrowserAgent (async lifecycle management)
│   ├── documents.py     # DocumentsAgent
│   ├── knowledge.py     # KnowledgeAgent
│   ├── location.py      # LocationAgent
│   └── system.py        # SystemAgent
├── tools/               # Tool modules grouped by domain
│   ├── research.py      # Web search, Wikipedia, arXiv, YouTube transcripts
│   ├── browser.py       # Playwright browser automation factory
│   ├── documents.py     # File I/O, PDF read/create, spreadsheets, charts
│   ├── docker_repl.py   # Docker-sandboxed Python REPL (BaseTool)
│   ├── knowledge_tools.py  # Knowledge base search, indexing, management
│   ├── location.py      # Google Places, apartment search (conditional)
│   └── system.py        # Push notifications, Python REPL, task scheduling
├── Dockerfile.python-sandbox  # Docker image for sandboxed Python execution
├── apartment_search.py  # Apartment analysis: amenities, commute, map
├── knowledge.py         # Knowledge base: chunking, embedding, ChromaDB
├── scheduler.py         # Task scheduling: SQLite + APScheduler
├── session_manager.py   # SQLite-backed session management
├── user_profile.py      # Persistent key-value store for user facts
├── pyproject.toml       # Project metadata and dependencies
├── .env                 # API keys and configuration (not committed)
├── sandbox/             # Working directory for agent file operations
│   └── knowledge/       # Drop documents here for knowledge base indexing
└── tests/
    ├── conftest.py            # Shared fixtures
    ├── test_tools_unit.py     # Unit tests for tools/ modules
    ├── test_knowledge.py      # Unit tests for knowledge base
    ├── test_scheduler.py      # Unit tests for task scheduler
    └── test_apartment_search.py  # Unit tests for apartment search
```

### Key files

| File | Role |
|---|---|
| [app.py](app.py) | Launches the Gradio interface, wires UI events, manages the agent lifecycle |
| [sidekick.py](sidekick.py) | Orchestrator: wraps sub-agents as tools, builds LangGraph state machine, optional evaluator loop |
| [config.py](config.py) | Centralizes all constants (DB paths, model name, sandbox dir) and loads `.env` |
| [agents/base.py](agents/base.py) | `BaseAgent` class using `create_react_agent` with async `run()` method |
| [tools/](tools/) | Domain-specific tool modules, each with a `get_tools()` function |
| [tools/docker_repl.py](tools/docker_repl.py) | `DockerPythonREPL`: executes Python in ephemeral Docker containers with resource limits |
| [Dockerfile.python-sandbox](Dockerfile.python-sandbox) | Lightweight Python 3.12 image used by the sandboxed REPL |
| [apartment_search.py](apartment_search.py) | Finds nearby family amenities with walking times, calculates commute, generates interactive map |
| [knowledge.py](knowledge.py) | Document chunking, OpenAI embedding, ChromaDB vector storage, semantic search |
| [scheduler.py](scheduler.py) | SQLite-backed task scheduling with cron expressions; persists tasks, validates cron, tracks results |
| [session_manager.py](session_manager.py) | Creates, lists, and renames named sessions backed by SQLite |
| [user_profile.py](user_profile.py) | Stores and retrieves persistent facts about the user across sessions |

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM | OpenAI GPT-5.2 (orchestrator + evaluator) |
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) with hierarchical multi-agent pattern and SQLite checkpointing |
| Sub-agents | `create_react_agent` from LangGraph prebuilt, wrapped as LangChain `Tool` objects |
| Browser automation | [Playwright](https://playwright.dev/) via LangChain toolkit |
| UI | [Gradio](https://www.gradio.app/) |
| Search | Google Serper, Wikipedia, arXiv, Google Places / Maps APIs |
| Mapping | [Leaflet](https://leafletjs.com/) + OpenStreetMap (interactive HTML maps) |
| Document processing | pypdf (reading), fpdf2 (creation) |
| Structured data | openpyxl (Excel), csv (CSV), matplotlib (charts) |
| Knowledge base / RAG | [ChromaDB](https://www.trychroma.com/) (vector store), OpenAI embeddings, langchain-text-splitters |
| Media | youtube-transcript-api |
| Task scheduling | [APScheduler](https://apscheduler.readthedocs.io/) with SQLite persistence |
| Notifications | [Pushover](https://pushover.net/) |
| Persistence | SQLite (sessions, chat history, user profile, checkpoints) |
| Code execution | Docker-sandboxed Python REPL (ephemeral containers, network-disabled, resource-limited) |
| Observability | LangSmith |
| Package management | [uv](https://github.com/astral-sh/uv) |

---

## License

MIT — see [LICENSE](LICENSE).
