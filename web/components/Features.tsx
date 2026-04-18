import { features } from "@/lib/features";

export function Features() {
  return (
    <section className="features reveal">
      <div className="wrap">
        <div className="sec-head">
          <div>
            <div className="sec-num">§ 02 — Capabilities</div>
            <h2>
              Engineered for <em>agency</em>, not just chat.
            </h2>
          </div>
          <p>
            Every design decision optimises for evidence-based answers,
            recoverable failures and observable behaviour. Built the way I&apos;d
            build it for a customer.
          </p>
        </div>

        <div className="feat-grid">
          {features.map((f) => (
            <div className="feat" key={f.num}>
              <div className="num">{f.num}</div>
              <h4>
                {f.titlePrefix}
                <em>{f.emWord}</em>
                {f.titleSuffix}
              </h4>
              <p>{f.body}</p>
              <div className="meta">{f.meta}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
