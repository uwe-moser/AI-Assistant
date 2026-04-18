const items = [
  "LangGraph",
  "Playwright",
  "ChromaDB",
  "Claude · GPT-4 · Local",
  "SQLite checkpoints",
  "APScheduler",
  "Docker sandbox",
  "Pushover",
  "Adzuna · Serper",
  "Google Maps",
];

export function Marquee() {
  // Duplicate the list so the CSS marquee loops seamlessly.
  const all = [...items, ...items];
  return (
    <div className="strip" aria-hidden="true">
      <div className="strip-track">
        {all.map((label, i) => (
          <span key={`${label}-${i}`}>
            <i className="dot"></i> {label}
          </span>
        ))}
      </div>
    </div>
  );
}
