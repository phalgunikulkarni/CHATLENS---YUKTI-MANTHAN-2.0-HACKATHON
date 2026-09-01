import { describe, it, expect } from "vitest";
import { NotConnectedConnectorService } from "../api/adapters/notConnectedConnectorService";
import { isNotConnected } from "../api/errors";
import { connectorsReducer, initialConnectorsState } from "./connectors.slice";

describe("Connectors: no fake connections by default", () => {
  const svc = new NotConnectedConnectorService();

  it("lists all four sources as not_connected", async () => {
    const list = await svc.list();
    expect(list.map((c) => c.type).sort()).toEqual(
      ["google_drive", "google_photos", "telegram", "whatsapp"]
    );
    expect(list.every((c) => c.status === "not_connected")).toBe(true);
  });

  it("never reports connected data (counts/timestamps) by default", async () => {
    const list = await svc.list();
    expect(list.every((c) => c.indexedCount === undefined && c.lastSyncedAt === undefined)).toBe(true);
  });

  it("connect/sync/disconnect reject with a NotConnectedError", async () => {
    await expect(svc.connect("whatsapp")).rejects.toSatisfy(isNotConnected);
    await expect(svc.sync("telegram")).rejects.toSatisfy(isNotConnected);
    await expect(svc.disconnect("google_drive")).rejects.toSatisfy(isNotConnected);
  });

  it("initial connectors state has all sources not_connected", () => {
    expect(initialConnectorsState.items.every((c) => c.status === "not_connected")).toBe(true);
  });

  it("reducer updates a single connector without inventing others", () => {
    const next = connectorsReducer(initialConnectorsState, {
      type: "CONNECTOR_UPDATED",
      connector: { type: "whatsapp", status: "connected", indexedCount: 5 },
    });
    const wa = next.items.find((c) => c.type === "whatsapp");
    expect(wa?.status).toBe("connected");
    expect(wa?.indexedCount).toBe(5);
    // Others remain not_connected.
    expect(next.items.filter((c) => c.type !== "whatsapp").every((c) => c.status === "not_connected")).toBe(true);
  });
});