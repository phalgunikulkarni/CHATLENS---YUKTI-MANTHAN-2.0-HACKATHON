import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoreProvider } from "../../state/store";
import { SearchHero } from "./SearchHero";
import { ACTIONS } from "../actions/ActionGrid";

function renderHero(onSearch = vi.fn()) {
  render(<StoreProvider><SearchHero onSearch={onSearch} /></StoreProvider>);
  return onSearch;
}

describe("SearchHero (home)", () => {
  it("shows the hero text 'You remember it, we find it.'", () => {
    renderHero();
    // ParticleText exposes the text via aria-label + accessible fallback span.
    expect(screen.getByLabelText("You remember it, we find it.")).toBeInTheDocument();
  });

  it("renders 'What would you like to do?' and all 8 action buttons on Home", () => {
    renderHero();
    expect(screen.getByText("What would you like to do?")).toBeInTheDocument();
    for (const a of ACTIONS) {
      expect(screen.getByRole("button", { name: a.label })).toBeInTheDocument();
    }
    // all use the shared specular button component
    const actionButtons = ACTIONS.map((a) => screen.getByRole("button", { name: a.label }));
    expect(actionButtons.every((b) => b.className.includes("cl-action"))).toBe(true);
  });

  it("clicking a home action does not break; it prompts to search first (no crash, no search)", async () => {
    const onSearch = renderHero();
    const u = userEvent.setup();
    await u.click(screen.getByRole("button", { name: "Summarize" }));
    // graceful: search is NOT triggered by an action click on Home
    expect(onSearch).not.toHaveBeenCalled();
    // and the hero + actions are still mounted (no crash)
    expect(screen.getByText("What would you like to do?")).toBeInTheDocument();
  });

  it("search still works from the hero", async () => {
    const onSearch = renderHero();
    const u = userEvent.setup();
    await u.type(screen.getByLabelText(/Describe the memory/i), "osi notes");
    await u.click(screen.getByRole("button", { name: /^Search$/i }));
    expect(onSearch).toHaveBeenCalledWith("osi notes");
  });
});
