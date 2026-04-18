import type {
  HistoryMessage,
  InterviewSessionDetail,
  InterviewSessionInfo,
  JobInfo,
  KnowledgeOpResult,
  KnowledgeOverview,
  ScheduledTaskInfo,
  SessionInfo,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const wsBase = () =>
  API.replace(/^http/, "ws");

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  base: API,
  wsBase,

  // sessions
  listSessions: () => http<SessionInfo[]>("/api/sessions"),
  latestSession: () => http<SessionInfo>("/api/sessions/latest"),
  createSession: (name?: string) =>
    http<SessionInfo>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  renameSession: (id: string, name: string) =>
    http<SessionInfo>(`/api/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteSession: (id: string) =>
    http<{ deleted: boolean }>(`/api/sessions/${id}`, { method: "DELETE" }),
  getHistory: (id: string) =>
    http<HistoryMessage[]>(`/api/sessions/${id}/history`),

  // tasks
  listTasks: () => http<ScheduledTaskInfo[]>("/api/tasks"),
  cancelTask: (id: string) =>
    http<{ cancelled: boolean }>(`/api/tasks/${id}`, { method: "DELETE" }),

  // knowledge
  knowledge: () => http<KnowledgeOverview>("/api/knowledge"),
  uploadKnowledge: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return http<KnowledgeOpResult>("/api/knowledge/upload", {
      method: "POST",
      body: fd,
    });
  },
  reindexKnowledge: () =>
    http<KnowledgeOpResult>("/api/knowledge/reindex", { method: "POST" }),
  deleteKnowledge: (filename: string) =>
    http<KnowledgeOpResult>(
      `/api/knowledge/${encodeURIComponent(filename)}`,
      { method: "DELETE" }
    ),

  // jobs
  jobStatuses: () => http<string[]>("/api/jobs/statuses"),
  listJobs: (status?: string) =>
    http<JobInfo[]>(
      `/api/jobs${status ? `?status=${encodeURIComponent(status)}` : ""}`
    ),

  // interviews
  listInterviews: () => http<InterviewSessionInfo[]>("/api/interviews"),
  getInterview: (id: string) =>
    http<InterviewSessionDetail>(`/api/interviews/${id}`),
};
