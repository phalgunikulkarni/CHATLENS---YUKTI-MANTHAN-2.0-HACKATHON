import "@testing-library/jest-dom";

/**
 * Test-only Web Storage polyfill.
 *
 * Newer Node/jsdom builds only expose `localStorage`/`sessionStorage` when the
 * runner is launched with `--localstorage-file`, so in this project's vitest
 * (jsdom) environment the globals are `undefined` and any test whose setup
 * calls `localStorage.clear()` throws. This installs a minimal in-memory
 * implementation ONLY when the global is missing. It affects the TEST harness
 * only — no application code is changed, and real browsers/production are
 * unaffected.
 *
 * Stored keys are exposed as enumerable own properties (like the real DOM
 * Storage) so patterns such as `{ ...localStorage }` work in tests.
 */
function createStorage(): Storage {
  const store = new Map<string, string>();
  const api: Record<string, unknown> = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key) : null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(String(key), String(value));
    },
  };
  const RESERVED = new Set(["length", "clear", "getItem", "key", "removeItem", "setItem"]);
  return new Proxy(api, {
    get(target, prop: string) {
      if (prop in target) return (target as Record<string, unknown>)[prop];
      const v = store.get(prop);
      return v === undefined ? undefined : v;
    },
    set(_target, prop: string, value) {
      if (RESERVED.has(prop)) return false;
      store.set(prop, String(value));
      return true;
    },
    has(target, prop: string) {
      return prop in target || store.has(prop);
    },
    deleteProperty(_target, prop: string) {
      store.delete(prop);
      return true;
    },
    ownKeys() {
      return Array.from(store.keys());
    },
    getOwnPropertyDescriptor(_target, prop: string) {
      if (store.has(prop)) {
        return { enumerable: true, configurable: true, writable: true, value: store.get(prop) };
      }
      return undefined;
    },
  }) as unknown as Storage;
}

function ensureStorage(name: "localStorage" | "sessionStorage"): void {
  try {
    if ((globalThis as unknown as Record<string, unknown>)[name]) return;
  } catch {
    // fall through to install
  }
  Object.defineProperty(globalThis, name, {
    value: createStorage(),
    configurable: true,
    writable: true,
  });
}

ensureStorage("localStorage");
ensureStorage("sessionStorage");

/**
 * jsdom does not implement Element.prototype.scrollIntoView. Components that
 * auto-scroll (e.g. the append-only execution workspace) call it in an effect,
 * which would throw in tests. Install a no-op ONLY when missing. Test harness
 * only — application/production behavior is unchanged.
 */
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() { /* no-op in jsdom */ };
}
