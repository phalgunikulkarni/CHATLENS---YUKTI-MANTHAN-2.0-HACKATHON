import { useEffect, useState } from "react";
import { isSendable } from "../../utils/validation";
import { Icon } from "../../components/Icon";
import { ParticleText } from "../../components/ParticleText";
import { ActionGrid, type ActionId } from "../actions/ActionGrid";
import { useDispatch } from "../../hooks";
import { uid } from "../../utils/format";
import { apiService } from "../../api/client";
import type { SearchResult } from "../../api/types";

interface Props {
  onSearch: (q: string) => void;
}

// Fixed float positions (left/right of the hero) for a depth-layered composition.
const FLOAT_SLOTS = [
  { side: "left", top: "6%", left: "3%", rot: -8, depth: 0 },
  { side: "left", top: "34%", left: "9%", rot: 6, depth: 1 },
  { side: "left", top: "62%", left: "2%", rot: -5, depth: 2 },
  { side: "right", top: "8%", left: "84%", rot: 7, depth: 0 },
  { side: "right", top: "40%", left: "90%", rot: -6, depth: 1 },
  { side: "right", top: "66%", left: "83%", rot: 5, depth: 2 },
] as const;

/**
 * Dark cinematic home hero: particle hero text, a glass search bar, floating
 * REAL memory thumbnails around the hero (best-effort from listLibrary; none
 * shown if unavailable — never fabricated), and the shared 8-action grid.
 */
export function SearchHero({ onSearch }: Props) {
  const [q, setQ] = useState("");
  const [floats, setFloats] = useState<SearchResult[]>([]);
  const dispatch = useDispatch();

  useEffect(() => {
    let cancelled = false;
    // Best-effort: reuse real indexed memory thumbnails for the composition.
    apiService.listLibrary()
      .then((items) => { if (!cancelled) setFloats(items.filter((i) => i.thumbnailUrl).slice(0, FLOAT_SLOTS.length)); })
      .catch(() => { /* no backend / empty — render no floating cards, never fake */ });
    return () => { cancelled = true; };
  }, []);

  const submit = (value: string) => {
    if (!isSendable(value)) return;
    onSearch(value.trim());
    setQ("");
  };

  const onAction = (_id: ActionId) => {
    dispatch({
      type: "TOAST_ADDED",
      toast: { id: uid("t"), message: "Search and select a memory first, then choose an action.", tone: "info" },
    });
  };

  return (
    <section className="cl-home cl-theme">
      <div className="cl-home-glow" aria-hidden="true" />

      {/* Floating real memory thumbnails (depth-layered). */}
      <div className="cl-floats" aria-hidden="true">
        {floats.map((r, i) => {
          const slot = FLOAT_SLOTS[i];
          return (
            <div
              key={r.id}
              className={`cl-float depth-${slot.depth}`}
              style={{ top: slot.top, left: slot.left, transform: `rotate(${slot.rot}deg)` }}
            >
              <img src={r.thumbnailUrl} alt="" loading="lazy" />
            </div>
          );
        })}
      </div>

      <div className="cl-home-inner">
        <span className="hero-eyebrow"><Icon name="sparkles" size={14} /> ChatLens</span>
        <div className="cl-hero-lines" aria-label="You remember it, we find it.">
          <ParticleText text="You remember it," className="cl-hero-line" color="white" height={110} fontScale={1.15} />
          <ParticleText text="we find it." className="cl-hero-line" color="purple" height={110} fontScale={1.15} />
        </div>

        <div className="cl-home-searchbar">
          <Icon name="search" size={20} className="search-icon" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(q); }}
            placeholder="Describe a memory… e.g. my handwritten OSI notes"
            aria-label="Describe the memory you are looking for"
          />
          <button className="cl-search-go" onClick={() => submit(q)} disabled={!isSendable(q)} aria-label="Search">
            <Icon name="arrow" size={18} />
          </button>
        </div>

        <div className="cl-home-actions">
          <ActionGrid heading="What would you like to do?" onAction={onAction} />
        </div>
      </div>
    </section>
  );
}
