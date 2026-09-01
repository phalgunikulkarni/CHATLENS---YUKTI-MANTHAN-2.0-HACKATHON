/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Live backend base URL. When set, the HTTP adapter is used. */
  readonly VITE_API_BASE_URL?: string;
  /** Set to "true" to explicitly opt into the isolated dev/demo mock adapter. */
  readonly VITE_USE_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}