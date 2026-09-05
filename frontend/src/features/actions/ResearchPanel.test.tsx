import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreProvider } from "../../state/store";
import { ResearchPanel } from "./ResearchPanel";
import { apiService } from "../../api/client";
import type { ResearchResponse } from "../../api/types";

const OK_RESULT: ResearchResponse = {
  ok: true,
  query: "transformers",
  research_answer: "Transformers are attention-based models [1].",
  key_findings: ["Attention replaces recurrence.", "Scales well."],
  sources: [
    {
      title: "Attention Is All You Need", url: "https://doi.org/10.5555/attn",
      provider: "OpenAlex", source_type: "scholarly", authors: ["A. Vaswani", "N. Shazeer"],
      publication_date: "2017-06-12", year: 2017, doi: "10.5555/attn",
      identifier: "W1", abstract: "We propose the Transformer.", snippet: null, relevance_score: 0.95,
    },
  ],
  limitations: [],
  providers_used: ["openalex"], providers_failed: [],
};

function renderPanel() {
  return render(
    <StoreProvider>
      <ResearchPanel />
    </StoreProvider>,
  );
}

describe("ResearchPanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("submits a query and renders answer, key findings, and a clickable source", async () => {
    const spy = vi.spyOn(apiService, "research").mockResolvedValue(OK_RESULT);
    renderPanel();
    await userEvent.type(screen.getByLabelText("Research query"), "transformers");
    await userEvent.click(screen.getByRole("button", { name: /research/i }));

    await waitFor(() => expect(spy).toHaveBeenCalledWith({ query: "transformers" }));
    // answer + findings
    expect(await screen.findByText(/attention-based models/i)).toBeInTheDocument();
    expect(screen.getByText("Attention replaces recurrence.")).toBeInTheDocument();
    // source metadata
    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    expect(screen.getByText("OpenAlex")).toBeInTheDocument();
    expect(screen.getByText(/DOI: 10.5555\/attn/)).toBeInTheDocument();
    // clickable link with safe external behavior + backend-provided URL
    const link = screen.getByRole("link", { name: /open source/i });
    expect(link).toHaveAttribute("href", "https://doi.org/10.5555/attn");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows a controlled error state when the backend reports no evidence", async () => {
    vi.spyOn(apiService, "research").mockResolvedValue({
      ok: false, query: "obscure", research_answer: null, key_findings: [],
      sources: [], limitations: ["No reliable evidence could be retrieved for this query."],
      providers_used: [], providers_failed: [],
    });
    renderPanel();
    await userEvent.type(screen.getByLabelText("Research query"), "obscure");
    await userEvent.click(screen.getByRole("button", { name: /research/i }));
    expect(await screen.findByText(/Couldn’t complete research/i)).toBeInTheDocument();
    expect(screen.getByText(/No reliable evidence/i)).toBeInTheDocument();
  });

  it("shows an error state when the request throws", async () => {
    vi.spyOn(apiService, "research").mockRejectedValue(new Error("network"));
    renderPanel();
    await userEvent.type(screen.getByLabelText("Research query"), "x");
    await userEvent.click(screen.getByRole("button", { name: /research/i }));
    expect(await screen.findByText(/Couldn’t complete research/i)).toBeInTheDocument();
  });
});
