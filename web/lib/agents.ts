export type AgentIcon =
  | "search"
  | "browser"
  | "document"
  | "knowledge"
  | "pin"
  | "calendar"
  | "briefcase"
  | "chat";

export type Agent = {
  num: string;
  emPrefix: string;
  nameSuffix: string;
  desc: string;
  tools: string;
  icon: AgentIcon;
};

export const agents: Agent[] = [
  {
    num: "01 / Specialist",
    emPrefix: "Research",
    nameSuffix: " Agent",
    desc: "Web, Wikipedia, arXiv and YouTube transcripts — synthesised with citations.",
    tools: "Google · Wikipedia · arXiv · YouTube",
    icon: "search",
  },
  {
    num: "02 / Specialist",
    emPrefix: "Browser",
    nameSuffix: " Agent",
    desc: "Drives a real Chromium session — clicks, fills forms, extracts and screenshots.",
    tools: "Playwright · DOM extraction · vision",
    icon: "browser",
  },
  {
    num: "03 / Specialist",
    emPrefix: "Documents",
    nameSuffix: " Agent",
    desc: "Reads, writes and charts — PDFs, spreadsheets, matplotlib, file ops.",
    tools: "PDF · CSV · XLSX · matplotlib",
    icon: "document",
  },
  {
    num: "04 / Specialist",
    emPrefix: "Knowledge",
    nameSuffix: " Agent",
    desc: "Semantic search over your private corpus, with chunk-level provenance.",
    tools: "ChromaDB · embeddings · re-rank",
    icon: "knowledge",
  },
  {
    num: "05 / Specialist",
    emPrefix: "Location",
    nameSuffix: " Agent",
    desc: "Address analysis, nearby amenities, commute times, apartment scoring.",
    tools: "Google Places · Maps · geocoding",
    icon: "pin",
  },
  {
    num: "06 / Specialist",
    emPrefix: "System",
    nameSuffix: " Agent",
    desc: "Cron-style scheduling, push notifications, sandboxed Python execution.",
    tools: "APScheduler · Pushover · REPL",
    icon: "calendar",
  },
  {
    num: "07 / Specialist",
    emPrefix: "Job Search",
    nameSuffix: " Agent",
    desc: "Discovers roles, ranks fit, and tailors CVs and cover letters per posting.",
    tools: "Adzuna · Serper · ranking",
    icon: "briefcase",
  },
  {
    num: "08 / Specialist",
    emPrefix: "Interview",
    nameSuffix: " Coach",
    desc: "Job-specific mock interviews with per-answer scoring and a final summary.",
    tools: "planning · scoring · summary",
    icon: "chat",
  },
];
