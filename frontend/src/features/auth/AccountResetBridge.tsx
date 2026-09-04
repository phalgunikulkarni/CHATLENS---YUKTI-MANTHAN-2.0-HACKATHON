import { useEffect, useRef, type ReactNode } from "react";
import { useAuth } from "./useAuth";
import { useDispatch } from "../../hooks/useStore";

/**
 * Bridges the auth lifecycle to the store reset.
 *
 * AuthContext lives ABOVE the StoreProvider in the tree (AuthProvider wraps
 * AuthGate wraps StoreProvider), so `AuthContext.logout` cannot dispatch a
 * store action directly. This component is rendered INSIDE StoreProvider, so it
 * can. It watches the signed-in account id (`useAuth().user?.id`) and, whenever
 * that id changes (login as a different account, or logout -> null), dispatches
 * `ACCOUNT_CHANGED` to reset the account-specific slices
 * (conversation / conversations / results / actions). This guarantees switching
 * A -> B or logging out never leaves the prior account's chat/results visible.
 *
 * It renders its children unchanged (a transparent wrapper) so it can sit at
 * the top of the StoreProvider subtree without altering layout.
 */
export function AccountResetBridge({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const dispatch = useDispatch();
  const prevId = useRef<string | null | undefined>(user?.id ?? null);

  useEffect(() => {
    const current = user?.id ?? null;
    if (prevId.current !== current) {
      // Account changed (switch or logout): clear prior-account UI state.
      dispatch({ type: "ACCOUNT_CHANGED" });
      prevId.current = current;
    }
  }, [user?.id, dispatch]);

  return <>{children}</>;
}
