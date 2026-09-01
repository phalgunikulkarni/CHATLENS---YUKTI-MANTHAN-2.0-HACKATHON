import type { SearchResult } from "../api/types";
import { hasText } from "./guards";

/** Fixed, non-fabricated fallback used when no Backend text is available. */
export const ALT_FALLBACK = "Stored image, no text available";

/**
 * Derive image alt text from Backend-provided title/OCR/metadata when present,
 * otherwise a fixed meaningful fallback. Never invents image content.
 */
export function deriveAltText(result: Pick<SearchResult, "title" | "ocrSnippet" | "sourceTag">): string {
  if (hasText(result.title)) return result.title;
  if (hasText(result.ocrSnippet)) return `Image containing text: ${result.ocrSnippet}`;
  if (hasText(result.sourceTag)) return `${result.sourceTag} image`;
  return ALT_FALLBACK;
}
