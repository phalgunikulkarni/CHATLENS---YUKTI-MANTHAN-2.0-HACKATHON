import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ActionGrid, ACTIONS } from "./ActionGrid";

describe("ActionGrid — unified 8-action set", () => {
  it("renders exactly 8 actions with identical component class", () => {
    render(<ActionGrid heading="What would you like to do with these results?" onAction={() => {}} />);
    expect(ACTIONS).toHaveLength(8);
    for (const a of ACTIONS) {
      expect(screen.getByRole("button", { name: a.label })).toBeInTheDocument();
    }
    // every button uses the SAME shared component class (no bespoke styles)
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(8);
    expect(buttons.every((b) => b.className.includes("cl-action"))).toBe(true);
  });

  it("clicking each action invokes onAction with its id", async () => {
    const onAction = vi.fn();
    const u = userEvent.setup();
    render(<ActionGrid heading="h" onAction={onAction} />);
    for (const a of ACTIONS) {
      await u.click(screen.getByRole("button", { name: a.label }));
    }
    expect(onAction.mock.calls.map((c) => c[0]).sort()).toEqual(ACTIONS.map((a) => a.id).sort());
  });

  it("shows the heading", () => {
    render(<ActionGrid heading="What would you like to do with these results?" onAction={() => {}} />);
    expect(screen.getByText("What would you like to do with these results?")).toBeInTheDocument();
  });

  it("renders all 8 actions using the shared SpecularButton component", () => {
    render(<ActionGrid heading="h" onAction={() => {}} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(8);
    // Every action button is a SpecularButton (same unified visual component).
    expect(buttons.every((b) => b.className.includes("specular-button"))).toBe(true);
    // Icon + label still present and accessible for each action.
    for (const a of ACTIONS) {
      const btn = screen.getByRole("button", { name: a.label });
      expect(btn.className).toContain("specular-button");
      expect(btn.getAttribute("aria-label")).toBe(a.label);
    }
  });

});
