"use client";

import { useState } from "react";
import { TasksPanel, KnowledgePanel, JobsPanel, InterviewsPanel } from "./panels";

type Tab = "tasks" | "knowledge" | "jobs" | "interviews";

const TABS: { id: Tab; label: string }[] = [
  { id: "tasks", label: "Tasks" },
  { id: "knowledge", label: "Knowledge" },
  { id: "jobs", label: "Jobs" },
  { id: "interviews", label: "Interviews" },
];

export function RightRail({
  refreshTick,
  onError,
}: {
  refreshTick: number;
  onError: (msg: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("tasks");

  return (
    <aside className="right">
      <div className="tab-bar">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "active" : ""}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "tasks" && <TasksPanel refreshTick={refreshTick} onError={onError} />}
      {tab === "knowledge" && (
        <KnowledgePanel refreshTick={refreshTick} onError={onError} />
      )}
      {tab === "jobs" && <JobsPanel refreshTick={refreshTick} onError={onError} />}
      {tab === "interviews" && (
        <InterviewsPanel refreshTick={refreshTick} onError={onError} />
      )}
    </aside>
  );
}
