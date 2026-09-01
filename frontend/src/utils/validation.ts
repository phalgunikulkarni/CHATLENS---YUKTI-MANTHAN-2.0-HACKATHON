/** True when the string is empty or contains only whitespace (incl. unicode). */
export function isBlank(value: string): boolean {
  return value.replace(/\s/gu, "").length === 0;
}

/** A query is sendable iff it contains at least one non-whitespace character. */
export function isSendable(value: string): boolean {
  return !isBlank(value);
}
