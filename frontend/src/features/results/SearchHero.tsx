import { useMemo, useRef, useState } from "react";
import { isSendable } from "../../utils/validation";
import { Icon } from "../../components/Icon";
import { SearchModes } from "../home/SearchModes";
import { MemoryMoments } from "../home/MemoryMoments";
import { MemoryCanvas } from "../home/MemoryCanvas";

interface Props {
  onSearch: (q: string) => void;
  onUpload: () => void;
}

/** Static suggestion pool (NOT user history) used for contextual hints as the
 *  user types. Clearly example content, never presented as real activity. */
const SUGGESTIONS = [
  "Find my Python login error",
  "Find my Python code screenshots",
  "Find my Python notes",
  "Find my CN notes about OSI",
  "Find my handwritten OSI notes",
  "Find my notes about database normalization",
  "Find the receipt around INR 800",
  "Find my project architecture diagram",
  "Find my lecture slides",
  "Find that confused guy meme",
];

/**
 * Search-first home experience: AI badge, strong heading, an expanding search
 * bar with live contextual suggestions, multimodal mode indicators, interactive
 * memory moments, and a subtle floating memory canvas.
 */
export function SearchHero({ onSearch, onUpload }: Props) {
  const [q, setQ] = useState("");
  const [focused, setFocused] = useState(false);
  const blurTimer = useRef<number | null>(null);

  const submit = (value: string) => {
    if (!isSendable(value)) return;
    onSearch(value.trim());
    setQ("");
  };

  const suggestions = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return [];
    return SUGGESTIONS.filter((s) => s.toLowerCase().includes(term)).slice(0, 5);
  }, [q]);

  const showSuggest = focused && suggestions.length > 0;

  return (
    <section className="hero-search">
      <MemoryCanvas onPick={submit} />

      <div className="hero-search-inner">
        <span className="ai-badge"><Icon name="sparkles" size={13} /> AI VISUAL MEMORY</span>
        <h1 className="hero-search-title">Search what you remember.</h1>
        <p className="hero-search-sub">Describe the image, not the filename.</p>

        <div className={`searchbar-xl ${focused ? "focused" : ""}`}>
          <Icon name="search" size={22} className="search-icon" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onFocus={() => { if (blurTimer.current) window.clearTimeout(blurTimer.current); setFocused(true); }}
            onBlur={() => { blurTimer.current = window.setTimeout(() => setFocused(false), 120); }}
            onKeyDown={(e) => { if (e.key === "Enter") submit(q); }}
            placeholder="Try: Find the handwritten CN notes about OSI..."
            aria-label="Describe what you remember"
            aria-autocomplete="list"
          />
          <button className="btn btn-primary" onClick={() => submit(q)} disabled={!isSendable(q)}>
            <Icon name="search" size={16} /> Search
          </button>

          {showSuggest && (
            <div className="suggest-pop" role="listbox">
              {suggestions.map((s) => (
                <button
                  key={s}
                  role="option"
                  aria-selected={false}
                  className="suggest-item"
                  onMouseDown={(e) => { e.preventDefault(); setQ(s); submit(s); }}
                >
                  <Icon name="search" size={14} /> {s}
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

        <div className="moment-label">Or start from a memory moment</div>
        <MemoryMoments onPick={submit} />
      </div>
    </section>
  );
}