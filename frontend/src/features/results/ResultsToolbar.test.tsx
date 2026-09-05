import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultsToolbar } from "./ResultsToolbar";
import type { SearchResult } from "../../api/types";

const RESULTS = [
  { id: "1", thumbnailUrl: "/a.png", title: "Receipt A", category: "Reciepts" } as unknown as SearchResult,
  { id: "2", thumbnailUrl: "/b.png", title: "Note B", category: "handwritten notes" } as unknown as SearchResult,
  { id: "3", thumbnailUrl: "/c.png", title: "Slide C", category: "lecture_slides" } as unknown as SearchResult,
];

function setup(over: Partial<React.ComponentProps<typeof ResultsToolbar>> = {}) {
  const props = {
    query: "osi notes", count: 3, results: RESULTS, category: "all" as const, sort: "relevance" as const,
    onSearch: vi.fn(), onCategory: vi.fn(), onSort: vi.fn(), ...over,
  };
  render(<ResultsToolbar {...props} />);
  return props;
}

describe("ResultsToolbar", () => {
  it("keeps the query visible and searches on submit", async () => {
    const p = setup();
    const input = screen.getByLabelText("Search your memories") as HTMLInputElement;
    expect(input.value).toBe("osi notes");
    await userEvent.click(screen.getByRole("button", { name: /search/i }));
    expect(p.onSearch).toHaveBeenCalledWith("osi notes");
  });

  it("renders 'All' plus real category pills derived from results (no fabrication)", () => {
    setup();
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Receipts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Documents" })).toBeInTheDocument();
    // Videos/Photos not present in data -> no such pill
    expect(screen.queryByRole("button", { name: "Videos" })).not.toBeInTheDocument();
  });

  it("clicking a pill selects that category", async () => {
    const p = setup();
    await userEvent.click(screen.getByRole("button", { name: "Receipts" }));
    expect(p.onCategory).toHaveBeenCalledWith("Receipts");
  });

  it("shows the result count for the query", () => {
    setup();
    expect(screen.getByText(/Found/)).toBeInTheDocument();
    expect(screen.getByText("osi notes")).toBeInTheDocument();
  });

  it("changing sort calls onSort", async () => {
    const p = setup();
    await userEvent.selectOptions(screen.getByLabelText("Sort results"), "recent");
    expect(p.onSort).toHaveBeenCalledWith("recent");
  });
});
