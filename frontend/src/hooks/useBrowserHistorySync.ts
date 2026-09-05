import { useEffect, useRef } from "react";
import { useDispatch, useUi } from "./index";
import type { ViewName } from "../state/types";

/**
 * Browser history bridge for ChatLens's state-driven navigation.
 *
 * ChatLens has no URL router: which page shows is driven by ui.view, and the
 * image-detail drawer by ui.drawerOpenForId. Without integrating the History API
 * the browser back stack only ever holds the initial entry, so pressing Back
 * immediately leaves the app. This hook makes Back/Forward walk the ChatLens
 * navigation history like a normal SPA:
 *
 *   - Each meaningful navigation state (view + open drawer) is pushed as a
 *     history entry via history.pushState (ordinary navigation -> new entry).
 *   - popstate (Back/Forward) restores the ChatLens state carried in that entry
 *     by dispatching the store actions - no full-page navigation.
 *   - The FIRST state is seeded with replaceState (not pushed), so a directly
 *     opened URL or a refresh does not fabricate a fake internal back entry.
 *
 * Search results/state are not stored here; they live in the results slice and
 * are unaffected by Back, so returning to the "search" view preserves them.
 */

interface NavState {
  chatlens: true;
  view: ViewName;
  drawerOpenForId: string | null;
}

function currentKey(view: ViewName, drawerOpenForId: string | null): string {
  return `${view}|${drawerOpenForId ?? ""}`;
}

export function useBrowserHistorySync(): void {
  const { view, drawerOpenForId } = useUi();
  const dispatch = useDispatch();

  // Track the last navigation state we reflected into history, and whether the
  // current state change originated from a popstate (so we don't re-push it).
  const lastKey = useRef<string | null>(null);
  const fromPopstate = useRef(false);
  const seeded = useRef(false);

  // Restore ChatLens state when the user presses Back/Forward.
  useEffect(() => {
    const onPopState = (e: PopStateEvent) => {
      const s = e.state as Partial<NavState> | null;
      if (!s || s.chatlens !== true) {
        // No ChatLens entry (e.g. exhausted our history) - let the browser do
        // its normal thing; do not fabricate an internal entry.
        return;
      }
      fromPopstate.current = true;
      const targetView = (s.view ?? "search") as ViewName;
      const targetDrawer = s.drawerOpenForId ?? null;
      dispatch({ type: "VIEW_CHANGED", view: targetView });
      if (targetDrawer) dispatch({ type: "DRAWER_OPENED", id: targetDrawer });
      else dispatch({ type: "DRAWER_CLOSED" });
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [dispatch]);

  // Reflect navigation state changes into the browser history stack.
  useEffect(() => {
    const key = currentKey(view, drawerOpenForId);
    const navState: NavState = { chatlens: true, view, drawerOpenForId };

    if (!seeded.current) {
      // Seed the initial entry in place so refresh / deep-open has no fake back.
      window.history.replaceState(navState, "");
      seeded.current = true;
      lastKey.current = key;
      return;
    }

    if (fromPopstate.current) {
      // This change came from Back/Forward; the entry already exists.
      fromPopstate.current = false;
      lastKey.current = key;
      return;
    }

    if (key === lastKey.current) return; // no real navigation change

    // Ordinary forward navigation -> a new browser history entry.
    window.history.pushState(navState, "");
    lastKey.current = key;
  }, [view, drawerOpenForId]);
}