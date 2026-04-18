import type { Metadata } from "next";
import "./app.css";

export const metadata: Metadata = {
  title: "ApexFlow — Workspace",
  description: "Live multi-agent workspace.",
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <div className="app-shell">{children}</div>;
}
