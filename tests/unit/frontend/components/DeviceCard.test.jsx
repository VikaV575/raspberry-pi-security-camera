import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import DeviceCard from "../../../../frontend/src/components/DeviceCard.jsx";
import {
  record,
  snapshot,
  startLive,
  stopLive,
} from "../../../../frontend/src/utils/api.js";
import { API } from "../../../../frontend/src/constants.js";

vi.mock("../../../../frontend/src/utils/api.js", () => ({
  snapshot: vi.fn(),
  record: vi.fn(),
  startLive: vi.fn(),
  stopLive: vi.fn(),
  deleteMedia: vi.fn(),
}));

function onlineDevice(overrides = {}) {
  return {
    id: "dev-1",
    name: "Front Camera",
    last_seen: new Date().toISOString(),
    ...overrides,
  };
}

describe("DeviceCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends snapshot and record actions", async () => {
    snapshot.mockResolvedValue({ ok: true });
    record.mockResolvedValue({ ok: true });
    render(<DeviceCard device={onlineDevice()} />);

    fireEvent.click(screen.getByRole("button", { name: /snapshot/i }));
    await waitFor(() => expect(snapshot).toHaveBeenCalledWith("dev-1"));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /record/i })).not.toBeDisabled()
    );

    fireEvent.change(screen.getByRole("spinbutton"), {
      target: { value: "14" },
    });
    fireEvent.click(screen.getByRole("button", { name: /record/i }));
    await waitFor(() => expect(record).toHaveBeenCalledWith("dev-1", 14));
  });

  it("disables controls when device is offline", () => {
    render(<DeviceCard device={onlineDevice({ last_seen: null })} />);
    expect(screen.getByRole("button", { name: /snapshot/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /record/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /live/i })).toBeDisabled();
  });

  it("starts and stops live mode and renders the live viewer", async () => {
    startLive.mockResolvedValue({ ok: true });
    stopLive.mockResolvedValue({ ok: true });
    render(<DeviceCard device={onlineDevice()} />);

    fireEvent.click(screen.getByRole("button", { name: /live/i }));
    await waitFor(() => expect(startLive).toHaveBeenCalledWith("dev-1"));
    expect(screen.getByTitle("Live stream dev-1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    await waitFor(() => expect(stopLive).toHaveBeenCalledWith("dev-1"));
  });

  it("renders a link for existing uploaded media", () => {
    const media = [{
      id: "media-1",
      filename: "snapshot.jpg",
      url: "/uploads/snapshot.jpg",
      media_type: "image",
      uploaded_at: new Date().toISOString(),
    }];

    render(<DeviceCard device={onlineDevice({ media })} />);

    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      `${API}/uploads/snapshot.jpg`
    );
  });

  it("displays a failed command request instead of silently ignoring it", async () => {
    snapshot.mockRejectedValue(new Error("Network unavailable"));
    render(<DeviceCard device={onlineDevice()} />);

    fireEvent.click(screen.getByRole("button", { name: /snapshot/i }));
    expect(await screen.findByText("Network unavailable")).toBeInTheDocument();
  });
});
