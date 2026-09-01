interface Moment {
  emoji: string;
  title: string;
  hint: string;
  query: string;
}

const MOMENTS: Moment[] = [
  { emoji: "🐍", title: "Python Login Error", hint: "That screenshot with the authentication traceback", query: "Find my Python login error" },
  { emoji: "📚", title: "CN / OSI Notes", hint: "Handwritten notes about OSI layers", query: "Find my CN notes about OSI" },
  { emoji: "🧾", title: "Bangalore Receipt", hint: "Receipt from that Bangalore trip", query: "Find the receipt around INR 800" },
  { emoji: "💻", title: "DBMS Normalization", hint: "Notes about database normalization", query: "Find my notes about database normalization" },
];

/** Interactive "memory moments" - clicking one fills + runs the search. */
export function MemoryMoments({ onPick }: { onPick: (query: string) => void }) {
  return (
    <div className="moment-grid">
      {MOMENTS.map((m) => (
        <button className="moment-card" key={m.title} onClick={() => onPick(m.query)} aria-label={`Search: ${m.title}`}>
          <span className="moment-emoji">{m.emoji}</span>
          <span className="moment-title">{m.title}</span>
          <span className="moment-hint">{m.hint}</span>
        </button>
      ))}
    </div>
  );
}