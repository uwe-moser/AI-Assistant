# ApexFlow — Open Tasks

This file tracks the next planned improvements for the ApexFlow agent. Tasks are listed in rough priority order within each section.

---

## In Progress

_Nothing currently in progress._

---

## Planned

### 1. Code Refactoring

**Goal:** Improve code quality, separation of concerns, and maintainability across the codebase.

#### 1.1 Configuration & Constants — eliminate duplication

- [ ] **Centralise configuration** — the DB path `"sidekick_chat_history.db"` is hardcoded in 3 files ([sidekick.py:61](sidekick.py), [app.py:20](app.py), [session_manager.py:9](session_manager.py)), and `"sidekick_checkpoints.db"` in [sidekick.py:69](sidekick.py). Create a single `config.py` with `DB_PATH`, `CHECKPOINTS_DB_PATH`, `SANDBOX_DIR`, `DEFAULT_MODEL`, etc.
- [ ] **Single `load_dotenv()` call** — currently called in both [sidekick.py:5](sidekick.py) and [sidekick_tools.py:20](sidekick_tools.py). Call it once at startup in `app.py` and remove from other modules.
- [ ] **Remove module-level side effects in `sidekick_tools.py`** — `serper`, `pushover_token`, `pushover_user` are instantiated/read at import time (lines 21–24). Move into factory functions or a lazy initialiser so missing env vars don't crash unrelated imports.

#### 1.2 `sidekick_tools.py` — restructure and harden

- [ ] **`other_tools()` is needlessly `async`** — nothing inside is awaited. Make it a plain `def` (or remove it and inline the list).
- [ ] **`create_pdf` accepts a raw JSON string** instead of typed parameters — fragile and error-prone. Convert to proper keyword arguments and let LangChain handle serialisation, or at minimum parse with a Pydantic model.
- [ ] **Hardcoded macOS font path** — `"/Library/Fonts/Arial Unicode.ttf"` ([sidekick_tools.py:106](sidekick_tools.py)) will fail on Linux/Windows. Search common font dirs or bundle a fallback TTF.
- [ ] **`import json` inside function body** ([sidekick_tools.py:85](sidekick_tools.py)) — move to module-level imports.
- [ ] **`push()` silently swallows HTTP errors** — no status-code check, no exception handling. Add basic error reporting.
- [ ] **YouTube URL parsing is brittle** — the prefix-stripping loop doesn't handle `&` parameters in the middle of URLs correctly. Use `urllib.parse.urlparse` + `parse_qs` instead.
- [ ] **Extract tool registration into grouped modules** (optional, for larger scale) — e.g. `tools/browser.py`, `tools/documents.py`, `tools/research.py`, `tools/notifications.py`. Each exports a `get_tools() -> list[Tool]` function.

#### 1.3 `sidekick.py` — agent core cleanup

- [ ] **Dead attribute `self.llm_with_tools`** ([sidekick.py:55](sidekick.py)) — initialised to `None`, never assigned or read. Remove it.
- [ ] **Worker mutates message objects in-place** — the loop at lines 155–160 overwrites `SystemMessage.content` on existing state messages. This is a hidden side effect that can corrupt checkpoint history. Instead, always prepend a fresh `SystemMessage` and filter out old ones.
- [ ] **System prompt is a 25-line f-string rebuilt every call** — extract into a `_build_worker_prompt(state) -> str` helper or a prompt template file. The tool-description block is static and can be a constant.
- [ ] **`evaluator()` return type annotation says `-> State` but returns a plain `dict`** ([sidekick.py:191](sidekick.py)) — fix the annotation to `-> dict[str, Any]`.
- [ ] **`_extract_and_update_profile` creates a new `ChatOpenAI` instance on every call** ([sidekick.py:100](sidekick.py)) — instantiate once during `setup()` and reuse.
- [ ] **`format_conversation` is only used by the evaluator** — inline it or make it a module-level helper; it doesn't need `self`.
- [ ] **Fragile `cleanup()` with dual async paths** ([sidekick.py:337–353](sidekick.py)) — the `try/except RuntimeError` pattern for detecting a running loop is brittle. Use `asyncio.get_event_loop().is_running()` or provide both a sync and async cleanup method. Better yet, use `async with` context-manager protocol on `Sidekick`.
- [ ] **`build_graph` doesn't need to be `async`** — nothing inside is awaited. Make it a plain `def`.

#### 1.4 `app.py` — UI and startup

- [ ] **Inline HTML/CSS is ~80 lines of raw strings** — extract into a separate `templates/` or `ui_components.py` file, or at minimum into module-level constants, so `app.py` focuses on event wiring.
- [ ] **Logo loading crashes if `ApexFlow.png` is missing** ([app.py:10–11](app.py)) — wrap in `try/except` with a graceful fallback.
- [ ] **`get_history_for_session` creates a new `SQLChatMessageHistory` per call** ([app.py:19](app.py)) — reuse the connection or cache the object.
- [ ] **Duplicate Sidekick lifecycle pattern** — `switch_session`, `create_new_session`, and `reset` all repeat the same `free_resources → Sidekick → setup` sequence. Extract a `_new_sidekick(session_id)` helper.

#### 1.5 General code quality

- [ ] **No logging** — the only output is `print("Cleaning up")` ([app.py:93](app.py)). Replace with Python `logging` module with configurable levels.
- [ ] **Unused dependencies in `pyproject.toml`** — `anthropic`, `langchain-anthropic`, `semantic-kernel`, `autogen-agentchat`, `autogen-ext`, `polygon-api-client`, `sendgrid`, `speedtest-cli`, `smithery`, `mcp-server-fetch`, `mcp[cli]`, `openai-agents` appear unused in any source file. Audit and remove to shrink install time and avoid conflicts.
- [ ] **`readdb.py` uses hardcoded DB paths** — should import from the proposed `config.py`.
- [ ] **No `__main__` guard in `app.py`** — `ui.launch()` runs on import. Wrap in `if __name__ == "__main__":`.

#### 1.6 Weakness summary

| Weakness | Impact | Where |
|---|---|---|
| Hardcoded config values duplicated across files | Change one, forget another → silent bugs | 3+ files |
| Worker mutates state messages in-place | Corrupts checkpoint history, non-deterministic replays | `sidekick.py:155–160` |
| Module-level side effects in tools | Import crashes if env vars missing, hard to test | `sidekick_tools.py:20–24` |
| `cleanup()` dual-path async heuristic | Unreliable resource release, potential leaks | `sidekick.py:337–353` |
| 80 lines of inline HTML/CSS | `app.py` is hard to read and maintain | `app.py:102–180` |
| ~12 unused dependencies | Bloated install, potential version conflicts | `pyproject.toml` |
| No logging, no error handling on tools | Silent failures, hard to debug in production | All files |
| `other_tools()` is async but awaits nothing | Misleading API, unnecessary overhead | `sidekick_tools.py:152` |
| New LLM instance per profile extraction call | Wasted resources, slower responses | `sidekick.py:100` |

**Files affected:** [sidekick.py](sidekick.py), [sidekick_tools.py](sidekick_tools.py), [app.py](app.py), [session_manager.py](session_manager.py), [user_profile.py](user_profile.py), [readdb.py](readdb.py), [pyproject.toml](pyproject.toml)

---

### 2. Rewrite README

**Goal:** Replace the placeholder README with accurate documentation that reflects the actual capabilities of the app.

- [x] Document all current tools (PDF, YouTube, arXiv, session management, user profile)
- [x] Add accurate project structure table including `session_manager.py` and `user_profile.py`
- [x] Document session management and persistent memory behaviour
- [x] Update tech stack table

**Files affected:** [README.MD](README.MD)

---

### 3. Add Perplexity Search Tool (via LangChain)

**Goal:** Integrate Perplexity AI as an additional search tool, giving the agent access to AI-synthesised, citation-backed answers for complex research queries.

- [ ] Add `PERPLEXITY_API_KEY` to `.env` and document it in the README
- [ ] Implement a `perplexity_search` tool in `sidekick_tools.py` using the LangChain Perplexity integration or direct API call
- [ ] Register the tool in `other_tools()` and expose it in the worker system prompt
- [ ] Add the "Perplexity Search" chip to the Capabilities section in `app.py`
- [ ] Test with queries that benefit from cited, synthesised answers vs. raw Google results

**Files affected:** [sidekick_tools.py](sidekick_tools.py), [app.py](app.py), [README.MD](README.MD), `.env`

---

### 4. Add Google Maps POI Distance Search

**Goal:** Allow the agent to look up points of interest (POIs) near a given address and return their distances, travel times, and basic details.

- [ ] Add `GOOGLE_MAPS_API_KEY` to `.env` and document it in the README
- [ ] Implement a `get_poi_distances` tool using the Google Maps Distance Matrix API and/or Places API
  - Input: a reference address and a POI type or list of place names
  - Output: sorted list of POIs with distance, travel time, and address
- [ ] Register the tool in `other_tools()` and add it to the worker system prompt description
- [ ] Add a "Maps & Distances" chip to the Capabilities section in `app.py`
- [ ] Handle API errors and quota limits gracefully

**Files affected:** [sidekick_tools.py](sidekick_tools.py), [app.py](app.py), [README.MD](README.MD), `.env`

---

### 5. Fix UI Bugs

**Goal:** Resolve known small issues in the Gradio interface.

- [ ] **Session dropdown not refreshing** after a new session is created in certain edge cases — ensure `gr.Dropdown` choices always reflect the current session list
- [ ] **Reset button** clears the chat but does not always reset the `success_criteria` field — verify the output wiring in `app.py`
- [ ] **Tool call messages** in the chat can overflow on narrow screens — constrain the metadata title width in CSS
- [ ] **Session name input** retains the old name after switching sessions — ensure `session_name_input` is updated on every `switch_session` call
- [ ] Review and test the Gradio dark-mode styles for the capabilities chips

**Files affected:** [app.py](app.py)

---

### 6. Structured Data & Spreadsheet Support

**Goal:** Let the agent work with CSV, Excel, and JSON data natively — analyse, transform, chart, and export.

- [x] Implement `read_spreadsheet` tool (CSV + Excel via `openpyxl`) that returns data as a table summary
- [x] Implement `write_spreadsheet` tool (create CSV/Excel files in sandbox)
- [x] Implement `chart_data` tool that generates PNG charts via `matplotlib` and saves to sandbox
- [x] The Python REPL can already do this, but dedicated tools give the LLM clearer affordances and reduce prompt engineering

**Files affected:** [sidekick_tools.py](sidekick_tools.py), [pyproject.toml](pyproject.toml)

---

### 8. Task Scheduling & Background Jobs

**Goal:** Let the agent run tasks on a schedule or in the background — e.g. "check the news every morning" or "monitor this webpage for changes".

- [x] Implement a `schedule_task` tool that persists a task + cron expression to SQLite
- [x] Add a lightweight scheduler (e.g. `APScheduler`) that runs persisted tasks and stores results
- [x] Combine with push notifications to alert on results
- [x] Add a UI panel to view/cancel scheduled tasks

**Files affected:** [sidekick_tools.py](sidekick_tools.py), [app.py](app.py), new [scheduler.py](scheduler.py)

---

### 9. Knowledge Base / RAG over Local Documents

**Goal:** Let the agent index and search your own documents (PDFs, notes, markdown) so it can answer questions grounded in your personal data.

- [ ] Add a `sandbox/knowledge/` directory for user-uploaded documents
- [ ] Implement document chunking + embedding (OpenAI embeddings or local via `sentence-transformers`)
- [ ] Store embeddings in a vector DB (ChromaDB or FAISS — lightweight, file-based)
- [ ] Implement a `search_knowledge_base(query)` tool that retrieves relevant chunks
- [ ] Re-index on file changes (or on-demand via a UI button)

**Files affected:** [sidekick_tools.py](sidekick_tools.py), [app.py](app.py), new `knowledge.py`, [pyproject.toml](pyproject.toml)

---

### 10. Image Generation & Vision

**Goal:** Let the agent create images (diagrams, illustrations) and analyse images the user provides.

- [ ] Implement `generate_image` tool via OpenAI DALL-E or Stability AI — saves result to sandbox
- [ ] Implement `analyse_image` tool that sends an image to a vision model (GPT-5.2 supports vision) and returns a description
- [ ] Allow the user to upload images via the Gradio chat interface
- [ ] Useful for: creating diagrams for reports, analysing screenshots, describing photos

**Files affected:** [sidekick_tools.py](sidekick_tools.py), [app.py](app.py)

---

## Completed

- Initial Gradio UI with worker-evaluator loop
- Session management with SQLite persistence
- User profile with automatic fact extraction
- Tool integrations: Playwright, Serper, Wikipedia, arXiv, YouTube transcripts, PDF read/write, Python REPL, Pushover
