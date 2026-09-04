import { useState } from "react";
import { isSendable } from "../../utils/validation";
import { Icon } from "../../components/Icon";

const EXAMPLES = [
  "Find the Python error screenshot I received on WhatsApp",
  "Find the DBMS notes I saved in Google Drive",
  "Find the receipt photo from Telegram",
  "Find my handwritten OSI notes",
];

interface Props {
  onSearch: (q: string) => void;
}

/**
 * Focused home hero: concise heading, the search bar as centerpiece, and
 * example query chips (suggestions only). Clicking a chip fills the search bar
 * - it does NOT search or record history until the user acts.
 */
export function SearchHero({ onSearch }: Props) {
  const [q, setQ] = useState("");
  const submit = (value: string) => {
    if (!isSendable(value)) return;
    onSearch(value.trim());
    setQ("");
  };

  return (
    <section className="hero home-hero">
      <span className="hero-eyebrow"><Icon name="sparkles" size={14} /> ChatLens</span>
      <h1>Search your visual memories</h1>

      <div className="searchbar">
        <Icon name="search" size={22} className="search-icon" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(q); }}
          placeholder='e.g. "Find the screenshot of my Python login error"'
          aria-label="Describe the memory you are looking for"
        />
        <button className="btn btn-primary" onClick={() => submit(q)} disabled={!isSendable(q)}>
          <Icon name="search" size={16} /> Search
        </button>
      </div>

      <div className="try-label">Try asking</div>
      <div className="chips">
        {EXAMPLES.map((ex) => (
          <button
            className="chip"
            key={ex}
            onClick={() => setQ(ex)}
            aria-label={`Use example query: ${ex}`}
          >
            {ex}
          </button>
        ))}
      </div>
    </section>
  );
}