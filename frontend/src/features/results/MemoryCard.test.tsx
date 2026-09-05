import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryCard } from "./MemoryCard";
import type { SearchResult } from "../../api/types";

const result: SearchResult = {
  id: "mem-1",
  thumbnailUrl: "mock://thumb",
  title: "A memory",
  explanation: [
    { type: "ocr", label: "OCR matched", icon: "text" },
    { type: "semantic", label: "Semantic match", icon: "brain" },
  ],
};

const noop = () => {};

function renderCard(showRetrievalExplanation?: boolean) {
  return render(
    <MemoryCard
      result={result}
      selected={false}
      view="grid"
      onToggleSelect={noop}
      onOpen={noop}
      onWhy={noop}
      showRetrievalExplanation={showRetrievalExplanation}
    />
  );
}

describe("MemoryCard retrieval explanation visibility", () => {
  it("Memory/Library card (default) hides 'Why this result?' and signal chips", () => {
    const { container } = renderCard(); // defaults to false
    expect(screen.queryByText(/why this result\?/i)).toBeNull();
    // Retrieval signal chips use the .sig-tag class; none should render.
    expect(container.querySelector(".sig-tag")).toBeNull();
    expect(container.querySelector(".signal-mini")).toBeNull();
  });

  it("Search-result card shows 'Why this result?' and signal chips", () => {
    const { container } = renderCard(true);
    expect(screen.getByText(/why this result\?/i)).toBeInTheDocument();
    expect(container.querySelector(".sig-tag")).not.toBeNull();
  });
});