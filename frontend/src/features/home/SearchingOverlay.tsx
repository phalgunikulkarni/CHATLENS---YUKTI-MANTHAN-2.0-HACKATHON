import { useEffect, useState } from "react";
import { Icon } from "../../components/Icon";

const STEPS = ["Reading clues", "Matching meaning", "Comparing visuals", "Ranking memories"];

/** AI-style search transition. Purely presentational; the real request runs in
 *  parallel and the parent swaps to results when it resolves. */
export function SearchingOverlay({ query }: { query: string }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 550);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="searching-overlay" role="status" aria-live="polite">
      <div className="searching-orb"><Icon name="sparkles" size={26} /></div>
      <div className="searching-title">Searching your visual memory...</div>
      {query && <div className="searching-query">&ldquo;{query}&rdquo;</div>}
      <ul className="searching-steps">
        {STEPS.map((s, i) => (
          <li key={s} className={i === step ? "active" : i < step ? "done" : ""}>
            <span className="dot">{i < step ? <Icon name="check" size={10} /> : null}</span>{s}
          </li>
        ))}
      </ul>
    </div>
  );
}