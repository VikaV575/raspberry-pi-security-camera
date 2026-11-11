import { API } from "../../../../frontend/src/constants.js";
import {
  record,
  refreshDevices,
  startLive,
  stopLive,
} from "../../../../frontend/src/utils/api.js";

describe("api utils", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("refreshDevices requests and parses the device list", async () => {
    const payload = [{ id: "cam-1" }];
    fetch.mockResolvedValue({
      ok: true,
      json: async () => payload,
    });

    await expect(refreshDevices()).resolves.toEqual(payload);
    expect(fetch).toHaveBeenCalledWith(`${API}/devices`);
  });

  it("record sends a typed command with the requested duration", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });

    await record("cam-22", 12);

    expect(fetch).toHaveBeenCalledWith(`${API}/devices/cam-22/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "record", seconds: 12 }),
    });
  });

  it("startLive exposes the backend error message", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: "Device is offline" }),
    });

    await expect(startLive("cam-err")).rejects.toThrow("Device is offline");
  });

  it("stopLive returns parsed backend response on success", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });

    await expect(stopLive("cam-3")).resolves.toEqual({ ok: true });
  });

  it("does not treat an HTTP error as a successful refresh", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: "Service unavailable" }),
    });

    await expect(refreshDevices()).rejects.toThrow("Service unavailable");
  });
});
