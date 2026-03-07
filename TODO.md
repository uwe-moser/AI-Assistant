# ApexFlow — Open Tasks

This file tracks the next planned improvements for the ApexFlow agent. Tasks are listed in rough priority order within each section.

---

## In Progress

_Nothing currently in progress._

---

## Planned

### 1. Code Refactoring

**Goal:** Improve code quality, separation of concerns, and maintainability across the codebase.

- [ ] Extract tool registration into individual, self-contained modules (one file per tool category)
- [ ] Consolidate async cleanup logic in `sidekick.py` into a single reliable teardown path
- [ ] Standardise error handling and return types across all tool functions in `sidekick_tools.py`
- [ ] Remove redundant imports and tighten module boundaries
- [ ] Add type annotations to public functions in `session_manager.py` and `user_profile.py`

**Files affected:** [sidekick.py](sidekick.py), [sidekick_tools.py](sidekick_tools.py), [app.py](app.py)

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

## Completed

- Initial Gradio UI with worker-evaluator loop
- Session management with SQLite persistence
- User profile with automatic fact extraction
- Tool integrations: Playwright, Serper, Wikipedia, arXiv, YouTube transcripts, PDF read/write, Python REPL, Pushover
