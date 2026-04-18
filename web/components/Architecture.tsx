import { agents } from "@/lib/agents";
import { Icon } from "./Icon";

export function Architecture() {
  return (
    <section className="arch reveal" id="architecture">
      <div className="wrap">
        <div className="sec-head">
          <div>
            <div className="sec-num">§ 01 — System</div>
            <h2>
              A hierarchical <em>orchestrator</em> that thinks before it dispatches.
            </h2>
          </div>
          <p>
            One LLM-driven planner decomposes intent and routes to the right
            specialist. Each agent owns a focused tool set, persists state through
            SQLite checkpoints, and returns evidence — never just opinions.
          </p>
        </div>

        <div className="arch-frame">
          <div className="orch">
            <div className="orch-badge">— Conductor —</div>
            <div className="orch-pill">Orchestrator</div>
            <div className="orch-sub">
              Plans · delegates · evaluates against success criteria · re-plans on
              failure
            </div>
          </div>

          <div className="agent-bus" aria-hidden="true"></div>

          <div className="agent-grid" id="agents">
            {agents.map((a) => (
              <article className="agent" key={a.num}>
                <div className="num">{a.num}</div>
                <div className="icon">
                  <Icon name={a.icon} />
                </div>
                <h3>
                  <em>{a.emPrefix}</em>
                  {a.nameSuffix}
                </h3>
                <p>{a.desc}</p>
                <div className="tools">{a.tools}</div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
