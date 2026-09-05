import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { createElement } from "react";
import { StoreProvider } from "../state/store";
import { useBrowserHistorySync } from "./useBrowserHistorySync";
import { useDispatch, useUi } from "./index";

/**
 * Browser Back navigation for ChatLens's state-driven views.
 *
 * Verifies the history bridge: ordinary navigation pushes browser history
 * entries, the initial state is seeded (replaced, not pushed), and popstate
 * (Back/Forward) restores the ChatLens view rather than leaving the app.
 */

function wrapper({ children }: { children: ReactNode }) {
  return createElement(StoreProvider, null, children);
}

function useHarness() {
  useBrowserHistorySync();
  return { ui: useUi(), dispatch: useDispatch() };
}

describe("useBrowserHistorySync (browser Back navigation)", () => {
  let pushSpy: ReturnType<typeof vi.spyOn>;
  let replaceSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    pushSpy = vi.spyOn(window.history, "pushState");
    replaceSpy = vi.spyOn(window.history, "replaceState");
  });
  afterEach(() => {
    pushSpy.mockRestore();
    replaceSpy.mockRestore();
  });

  it("seeds the initial state with replaceState and does not push on mount", () => {
    renderHook(() => useHarness(), { wrapper });
    expect(replaceSpy).toHaveBeenCalledTimes(1);
    const seeded = replaceSpy.mock.calls[0][0] as { chatlens?: boolean; view?: string };
    expect(seeded.chatlens).toBe(true);
    expect(seeded.view).toBe("search");
    expect(pushSpy).not.toHaveBeenCalled();
  });

  it("pushes a new history entry on forward navigation", () => {
    const { result } = renderHook(() => useHarness(), { wrapper });
    act(() => result.current.dispatch({ type: "VIEW_CHANGED", view: "library" }));
    expect(pushSpy).toHaveBeenCalledTimes(1);
    const pushed = pushSpy.mock.calls[0][0] as { chatlens?: boolean; view?: string };
    expect(pushed.chatlens).toBe(true);
    expect(pushed.view).toBe("library");

    act(() => result.current.dispatch({ type: "VIEW_CHANGED", view: "connectors" }));
    expect(pushSpy).toHaveBeenCalledTimes(2);
  });

  it("does not push a duplicate entry when the state is unchanged", () => {
    const { result } = renderHook(() => useHarness(), { wrapper });
    act(() => result.current.dispatch({ type: "VIEW_CHANGED", view: "library" }));
    act(() => result.current.dispatch({ type: "VIEW_CHANGED", view: "library" }));
    expect(pushSpy).toHaveBeenCalledTimes(1);
  });

  it("restores the ChatLens view on popstate (Back) without pushing", () => {
    const { result } = renderHook(() => useHarness(), { wrapper });
    act(() => result.current.dispatch({ type: "VIEW_CHANGED", view: "library" }));
    expect(result.current.ui.view).toBe("library");
    pushSpy.mockClear();

    // Simulate the browser Back button returning to the seeded "search" entry.
    act(() => {
      window.dispatchEvent(
        new PopStateEvent("popstate", { state: { chatlens: true, view: "search", drawerOpenForId: null } })
      );
    });
    expect(result.current.ui.view).toBe("search");
    expect(pushSpy).not.toHaveBeenCalled();
  });

  it("ignores popstate entries that are not ChatLens entries", () => {
    const { result } = renderHook(() => useHarness(), { wrapper });
    act(() => result.current.dispatch({ type: "VIEW_CHANGED", view: "connectors" }));
    act(() => {
      window.dispatchEvent(new PopStateEvent("popstate", { state: null }));
    });
    // View is unchanged (bridge does not fabricate an internal entry).
    expect(result.current.ui.view).toBe("connectors");
  });
});