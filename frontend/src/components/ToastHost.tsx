import { useEffect } from "react";
import { useDispatch, useUi } from "../hooks";
import { Icon } from "./Icon";

/** Renders active toasts and auto-dismisses each after a delay. */
export function ToastHost() {
  const { toasts } = useUi();
  const dispatch = useDispatch();

  useEffect(() => {
    if (toasts.length === 0) return;
    const timers = toasts.map((t) =>
      setTimeout(() => dispatch({ type: "TOAST_DISMISSED", id: t.id }), 3200)
    );
    return () => timers.forEach(clearTimeout);
  }, [toasts, dispatch]);

  if (toasts.length === 0) return null;
  return (
    <div className="toast-stack" aria-live="polite" role="status">
      {toasts.map((t) => (
        <div className={`toast ${t.tone}`} key={t.id}>
          <Icon name={t.tone === "error" ? "close" : t.tone === "success" ? "check" : "sparkles"} size={18} />
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}
