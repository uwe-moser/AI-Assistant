type Stat = { value: string; emPart?: string; emPosition?: "before" | "after"; label: string };

const stats: Stat[] = [
  { value: "8", emPart: "8", emPosition: "before", label: "Specialist agents" },
  { value: "30+", emPart: "+", emPosition: "after", label: "Integrated tools" },
  { value: "100%", emPart: "%", emPosition: "after", label: "Local-first execution" },
  { value: "0.", emPart: ".", emPosition: "after", label: "Vendor lock-in" },
];

function StatValue({ stat }: { stat: Stat }) {
  if (stat.emPosition === "before") {
    return (
      <>
        <em>{stat.emPart}</em>
      </>
    );
  }
  // emPosition === "after"
  const prefix = stat.value.replace(stat.emPart ?? "", "");
  return (
    <>
      {prefix}
      <em>{stat.emPart}</em>
    </>
  );
}

export function Numbers() {
  return (
    <section className="numbers reveal">
      <div className="wrap">
        <div className="sec-head">
          <div>
            <div className="sec-num">§ 04 — At a glance</div>
            <h2>
              Built to <em>show what&apos;s possible</em>.
            </h2>
          </div>
          <p>
            Numbers that matter to a serious customer evaluating multi-agent
            systems for production work.
          </p>
        </div>

        <div className="num-grid">
          {stats.map((s) => (
            <div className="nblock" key={s.label}>
              <div className="v">
                <StatValue stat={s} />
              </div>
              <div className="l">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
