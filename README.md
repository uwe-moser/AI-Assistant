# Sidekick — Your Personal AI Co-Worker

Sidekick is an autonomous AI agent that completes tasks on your behalf. You describe what you want done and define what success looks like — Sidekick figures out how to get there.

It browses the web, writes and executes code, searches for information, reads and writes files, and sends you notifications. A built-in evaluator checks the result against your success criteria and keeps the agent working until the job is done.

---

## What it can do

- **Browse the web** — navigate pages, click links, fill forms, take screenshots
- **Search** — Google (via Serper) and Wikipedia
- **Run code** — execute Python in a sandboxed REPL
- **Manage files** — read, write, edit, and list files in the sandbox directory
- **Send notifications** — push alerts to your phone via Pushover
- **Self-evaluate** — an LLM-powered evaluator checks results against your success criteria and retries until they're met

---

## How it works

Sidekick uses a **worker–evaluator loop** built on [LangGraph](https://github.com/langchain-ai/langgraph):

```
User input (task + success criteria)
        │
    ┌───▼───┐
    │ WORKER │  ◄─────────────────────┐
    └───┬───┘                         │
        │ tool calls?                 │
      yes │           no              │
    ┌─────▼─────┐   ┌──────────┐     │
    │   TOOLS   │   │ EVALUATOR│     │
    └─────┬─────┘   └────┬─────┘     │
          │              │           │
          └──────────────┤           │
                    met? │           │
                  yes /  \ no        │
                  END     └──────────┘
```

1. The **worker** receives your task and available tools, and decides what to do.
2. If it needs to use a tool (browser, search, code execution, etc.), the tool runs and control returns to the worker.
3. Once the worker produces a response, the **evaluator** checks it against your success criteria.
4. If the criteria aren't met, the evaluator sends feedback and the worker tries again.
5. The loop ends when the task is complete or the agent needs your input.

---

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- A Chromium-compatible browser (installed automatically by Playwright)

### Install dependencies

```bash
uv sync
playwright install chromium
```

### Configure API keys

Create a `.env` file in the project root with the following:

```env
# Required — LLM provider
OPENAI_API_KEY=your_openai_api_key

# Web search
SERPER_API_KEY=your_serper_api_key

# Push notifications (optional)
PUSHOVER_USER=your_pushover_user_key
PUSHOVER_TOKEN=your_pushover_app_token

# Email (optional)
RESEND_API_KEY=your_resend_api_key

# Observability (optional)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=sidekick
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

Only `OPENAI_API_KEY` is required to run the core agent. The other keys unlock specific tools.

### Run the app

```bash
uv run app.py
```

The Gradio UI opens in your browser automatically. Stop with `Ctrl+C`.

---

## Usage

1. Open the browser UI (launches at `http://localhost:7860` by default).
2. Type your task in the **message** field.
3. Describe your success criteria — what does "done" look like?
4. Click **Go!** and watch Sidekick work.
5. Use **Reset** to start a fresh session.

---

## Project structure

```
AI_Assistant/
├── app.py               # Gradio web UI and application entry point
├── sidekick.py          # Core agent: worker, evaluator, LangGraph state machine
├── sidekick_tools.py    # Tool integrations (browser, search, files, code, notifications)
├── pyproject.toml       # Project metadata and dependencies
├── .env                 # API keys and configuration (not committed)
└── sandbox/             # Working directory for file operations
```

### Key files

| File | Role |
|---|---|
| [app.py](app.py) | Launches the Gradio interface, wires up user interactions, manages the Sidekick lifecycle |
| [sidekick.py](sidekick.py) | Defines the `Sidekick` class, the LangGraph state machine, and the worker/evaluator nodes |
| [sidekick_tools.py](sidekick_tools.py) | Registers all tools available to the agent (Playwright, file I/O, search, Python REPL, push notifications) |

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM | OpenAI GPT-4o-mini |
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| Browser automation | [Playwright](https://playwright.dev/) |
| UI | [Gradio](https://www.gradio.app/) |
| Search | Google Serper, Wikipedia |
| Observability | LangSmith |
| Package management | [uv](https://github.com/astral-sh/uv) |

---

## License

MIT — see [LICENSE](LICENSE).