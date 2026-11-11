import { useEffect, useState } from "react";
import { refreshDevices } from "./utils/api.js";
import { isOnline } from "./utils/time.js";
import DeviceCard from "./components/DeviceCard.jsx";
import "./app.css";

export default function App() {
  const [devices, setDevices] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [, setTick] = useState(0);

  async function handleRefreshDevices() {
    setRefreshing(true);
    try {
      const data = await refreshDevices();
      setDevices(data);
    } catch (error) {
      console.error("Failed to refresh devices", error);
    } finally {
      setTimeout(() => setRefreshing(false), 400);
    }
  }

  useEffect(() => {
    handleRefreshDevices();
    const t = setInterval(handleRefreshDevices, 3000);
    const tick = setInterval(() => setTick((n) => n + 1), 5000);
    return () => {
      clearInterval(t);
      clearInterval(tick);
    };
  }, []);

  const online = devices.filter((d) => isOnline(d.last_seen)).length;

  return (
    <div className="app">
      <div className="header">
        <div>
          <div className="logo">
            <div className="logo-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M3 9a9 9 0 0 1 9-6 9 9 0 0 1 9 6" />
                <path d="M3 15a9 9 0 0 0 9 6 9 9 0 0 0 9-6" />
              </svg>
            </div>
            <span className="logo-text">Sec<span>Cam</span></span>
          </div>
          <button className={`refresh-btn${refreshing ? " spinning" : ""}`} onClick={handleRefreshDevices}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
              <path d="M21 3v5h-5" />
              <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
              <path d="M3 21v-5h5" />
            </svg>
            Refresh
          </button>
        </div>
        <div className="header-meta">
          <div>{devices.length} device{devices.length !== 1 ? "s" : ""} registered</div>
          <div style={{ color: "#4ade80" }}>{online} online</div>
        </div>
      </div>

      <div className="grid">
        {devices.length === 0 ? (
          <div className="empty">
            <div className="empty-title">No devices found</div>
            <div>Waiting for cameras to connect…</div>
          </div>
        ) : (
          devices.map((device) => (
            <DeviceCard
              key={device.id}
              device={device}
              onActivityChange={handleRefreshDevices}
            />
          ))
        )}
      </div>
    </div>
  );
}
