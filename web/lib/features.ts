export type Feature = {
  num: string;
  titlePrefix: string;
  emWord: string;
  titleSuffix: string;
  body: string;
  meta: string;
};

export const features: Feature[] = [
  {
    num: "01 — STATE",
    titlePrefix: "Durable ",
    emWord: "memory",
    titleSuffix: " across sessions.",
    body: "Every superstep is checkpointed to SQLite via LangGraph. Conversations survive restarts, branch, and replay deterministically — the same primitive used by Claude's own tooling.",
    meta: "SQLChatMessageHistory · LangGraph checkpoints",
  },
  {
    num: "02 — SAFETY",
    titlePrefix: "Code runs ",
    emWord: "sandboxed",
    titleSuffix: " by default.",
    body: "Python execution happens in an isolated Docker REPL with a scoped filesystem. The browser agent runs Chromium in a controlled context — no unbounded shell access ever leaves the box.",
    meta: "Docker · scoped sandbox/ · network policy",
  },
  {
    num: "03 — RECALL",
    titlePrefix: "Your documents, ",
    emWord: "retrievable",
    titleSuffix: ".",
    body: "Drop in PDFs, markdown, CSVs. ApexFlow indexes with ChromaDB and lets the orchestrator reason over the corpus alongside live web evidence — provenance preserved per chunk.",
    meta: "ChromaDB · semantic search · per-chunk citation",
  },
  {
    num: "04 — TIME",
    titlePrefix: "Tasks that ",
    emWord: "run while you sleep",
    titleSuffix: ".",
    body: "Schedule any agent task on cron. ApexFlow re-queues the orchestrator at the right moment, runs the workflow, and pings you on Pushover when something changes.",
    meta: "APScheduler · Pushover notifications",
  },
  {
    num: "05 — TRUST",
    titlePrefix: "Success criteria, ",
    emWord: "verified",
    titleSuffix: ".",
    body: "Every prompt accepts an optional success criterion. The orchestrator checks the result against it and re-plans if it fell short — a cheap, reliable evaluator loop.",
    meta: "self-eval · re-planning · transparent traces",
  },
  {
    num: "06 — REACH",
    titlePrefix: "Real tools, ",
    emWord: "real APIs",
    titleSuffix: ".",
    body: "Google Maps and Places, Adzuna, Serper, YouTube Transcript, arXiv, Wikipedia, Pushover — wired in production-style with secrets management and graceful degradation.",
    meta: "10+ integrated APIs · env-driven config",
  },
];
