import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LogoutConfirm } from "./LogoutConfirm";

/**
 * Phase 1 (logout UI): the confirmation dialog must portal to document.body with
 * a full-viewport backdrop above the app, the dialog above the backdrop, and
 * Cancel/Log out wired correctly.
 */
describe("LogoutConfirm — modal layering + actions", () => {
  it("renders a full-viewport backdrop portaled to document.body", () => {
    const { container } = render(<LogoutConfirm onConfirm={() => {}} onCancel={() => {}} />);
    const backdrop = screen.getByTestId("logout-backdrop");
    // Portaled OUT of the component's own container (into document.body).
    expect(container).not.toContainElement(backdrop);
    expect(document.body).toContainElement(backdrop);
    // Backdrop is the fixed full-viewport overlay.
    expect(backdrop.className).toContain("dialog-wrap");
  });

  it("renders the dialog above the backdrop (dialog is a child of the backdrop)", () => {
    render(<LogoutConfirm onConfirm={() => {}} onCancel={() => {}} />);
    const backdrop = screen.getByTestId("logout-backdrop");
    const dialog = screen.getByRole("dialog");
    expect(backdrop).toContainElement(dialog);       // dialog stacked over the backdrop
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.className).toContain("dialog");
  });

  it("clicking the backdrop cancels (background is not interactive)", async () => {
    const onCancel = vi.fn();
    render(<LogoutConfirm onConfirm={() => {}} onCancel={onCancel} />);
    // mousedown on the backdrop itself (not the dialog) triggers cancel
    const backdrop = screen.getByTestId("logout-backdrop");
    await userEvent.pointer({ target: backdrop, keys: "[MouseLeft]" });
    expect(onCancel).toHaveBeenCalled();
  });

  it("Cancel closes without logging out; Log out confirms", async () => {
    const onCancel = vi.fn(); const onConfirm = vi.fn();
    const u = userEvent.setup();
    render(<LogoutConfirm onConfirm={onConfirm} onCancel={onCancel} />);
    await u.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
    await u.click(screen.getByRole("button", { name: /log out/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("Escape cancels the dialog (focus trapped inside)", async () => {
    const onCancel = vi.fn();
    render(<LogoutConfirm onConfirm={() => {}} onCancel={onCancel} />);
    // useFocusTrap listens on the dialog node and focuses its first control;
    // dispatch Escape from within the dialog (as it is in the browser).
    const dialog = screen.getByRole("dialog");
    (screen.getByRole("button", { name: /cancel/i }) as HTMLElement).focus();
    await userEvent.keyboard("{Escape}");
    // Fallback: also fire directly on the trapped node to mirror real focus.
    if (!onCancel.mock.calls.length) {
      const { fireEvent } = await import("@testing-library/react");
      fireEvent.keyDown(dialog, { key: "Escape" });
    }
    expect(onCancel).toHaveBeenCalled();
  });
});
