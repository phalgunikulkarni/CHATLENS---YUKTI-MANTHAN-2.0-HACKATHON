/**
 * Thrown by the API layer when no backend is configured. The UI catches this
 * to show a clear "backend not connected" integration state rather than a
 * generic error or any fabricated result.
 */
export class NotConnectedError extends Error {
  readonly notConnected = true;
  constructor(message = "ChatLens backend is not connected yet.") {
    super(message);
    this.name = "NotConnectedError";
  }
}

export function isNotConnected(err: unknown): err is NotConnectedError {
  return err instanceof NotConnectedError || (typeof err === "object" && err !== null && "notConnected" in err);
}