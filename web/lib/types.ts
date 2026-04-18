export type SessionInfo = { id: string; name: string; created_at: string };

export type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
  metadata?: { title?: string } | null;
};

export type ScheduledTaskInfo = {
  id: string;
  description: string;
  cron_expr: string;
  created_at: string;
  enabled: boolean;
  last_run: string | null;
  last_result: string | null;
  notify: boolean;
};

export type KnowledgeDoc = { filename: string; chunks: number };
export type KnowledgeOverview = {
  total_chunks: number;
  documents: KnowledgeDoc[];
};
export type KnowledgeOpResult = {
  message: string;
  overview: KnowledgeOverview;
};

export type JobInfo = {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  salary: string | null;
  status: string;
  match_score: number | null;
  match_rationale: string | null;
  apply_url: string | null;
  posted_at: string | null;
  discovered_at: string;
  updated_at: string;
  notes: string | null;
  source: string;
};

export type InterviewSessionInfo = {
  id: string;
  job_id: string | null;
  title: string | null;
  status: string;
  current_index: number;
  overall_score: number | null;
  final_summary: string | null;
  created_at: string;
  updated_at: string;
};

export type InterviewTurnInfo = {
  id: string;
  idx: number;
  question: string;
  category: string | null;
  answer: string | null;
  score: number | null;
  critique: string | null;
};

export type InterviewSessionDetail = {
  session: InterviewSessionInfo;
  turns: InterviewTurnInfo[];
};

export type ChatFrame =
  | { type: "history"; history: HistoryMessage[] }
  | { type: "done" }
  | { type: "error"; error: string };
