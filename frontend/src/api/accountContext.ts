/**
 * Account Identity Bridge (frontend holder).
 *
 * A non-React, module-level place to store the active account id so the HTTP
 * adapter (which is not a React component) can read it when injecting the
 * `X-Account-Id` header. The auth lifecycle (AuthContext) is the sole writer:
 * it calls `setAccountId` on login / session restore and `clearAccountId` on
 * logout. Everyone else only reads via `getAccountId`.
 *
 * The id is the existing `stableAccountId(email)` value (`acct-<hex>`); no new
 * identifier is generated here.
 */

let accountId: string | null = null;

/** Set the active account id (the signed-in user's stableAccountId). */
export function setAccountId(id: string): void {
  accountId = id;
}

/** Clear the active account id (on logout) so no header is sent afterward. */
export function clearAccountId(): void {
  accountId = null;
}

/** Read the active account id, or null when signed out. */
export function getAccountId(): string | null {
  return accountId;
}
