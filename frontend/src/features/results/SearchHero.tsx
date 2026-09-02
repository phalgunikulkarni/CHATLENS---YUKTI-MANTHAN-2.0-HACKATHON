import { useRef, useState } from "react";
import { isSendable } from "../../utils/validation";
import { Icon } from "../../components/Icon";
import { SearchModes } from "../home/SearchModes";
import { MemoryCanvas } from "../home/MemoryCanvas";

interface Props {
  onSearch: (q: string) => void;
  onUpload: () => void;
}

/**
 * Generic UI-guidance prompts. These are NOT example queries or user data - they
 * only guide how to phrase a memory. They never pre-populate or run a search.
 */
const GUIDANCE = [
  "Describe an image you remember...",
  "Search by text that was inside an image...",
  "Search by what was happening in the image...",
];

/**
 * Search-first home experience. Intentionally generic: no hardcoded sample
 * memories, example queries, or fabricated personal content. The search box is
 * never pre-populated. Actual memories/results come only from user uploads or
 * the backend.
 */
export function SearchHero({ onSearch, onUpload }: Props) {
  const [q, setQ] = useState("");
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const blurTimer = useRef<number | null>(null);

  const submit = (value: string) => {
    if (!isSendable(value)) return;
    onSearch(value.trim());
    setQ("");
  };

  // Guidance is shown on focus while empty. It is help text only - selecting one
  // focuses the input for the user to type; it never runs a search itself.
  const showGuidance = focused && q.trim().length === 0;

  return (
    <section className="hero-search">
      <MemoryCanvas />

      <div className="hero-search-inner">
        <span className="ai-badge"><Icon name="sparkles" size={13} /> AI VISUAL MEMORY</span>
        <h1 className="hero-search-title">Search what you remember.</h1>
        <p className="hero-search-sub">Describe the image, not the filename.</p>

        <div className={`searchbar-xl ${focused ? "focused" : ""}`}>
          <Icon name="search" size={22} className="search-icon" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onFocus={() => { if (blurTimer.current) window.clearTimeout(blurTimer.current); setFocused(true); }}
            onBlur={() => { blurTimer.current = window.setTimeout(() => setFocused(false), 120); }}
            onKeyDown={(e) => { if (e.key === "Enter") submit(q); }}
            placeholder="Describe what you remember..."
            aria-label="Describe what you remember"
          />
          <button className="btn btn-primary" onClick={() => submit(q)} disabled={!isSendable(q)}>
            <Icon name="search" size={16} /> Search
          </button>

          {showGuidance && (
            <div className="suggest-pop" role="list" aria-label="How to search">
              {GUIDANCE.map((g) => (
                <button
                  key={g}
                  role="listitem"
                  className="suggest-item guidance"
                  onMouseDown={(e) => { e.preventDefault(); inputRef.current?.focus(); }}
                >
                  <Icon name="sparkles" size={14} /> {g}
                </button>
              ))}
            </div>
          )}
        </div>

        <SearchModes />

        <div className="hero-actions">
          <button className="btn btn-ghost" onClick={onUpload}>
            <Icon name="upload" size={16} /> Upload images
          </button>
        </div>
      </div>
    </section>
  );
}