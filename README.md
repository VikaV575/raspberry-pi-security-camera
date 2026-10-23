# Sec-Cam

A Raspberry Pi smart security camera platform with a Python device agent, FastAPI backend, React dashboard, WebSocket command delivery, PostgreSQL-backed camera/media/command metadata, command-status tracking, and live streaming through MediaMTX.

## Features

- Raspberry Pi agent with automatic WebSocket reconnection and heartbeats
- Remote snapshot and video recording commands
- Command lifecycle tracking: `Queued`, `Running`, `Completed`, and `Failed`
- Error details displayed in the dashboard when a device command fails
- Media upload and HTTP file serving
- Per-device media gallery for recently uploaded images and videos
- In-browser image preview and video playback controls
- Device registration and online/offline tracking
- Live-stream start/stop control
- RTMP streaming from the Pi to MediaMTX
- Browser playback through WebRTC
- Unit and integration tests for the agent, backend, WebSockets, uploads, activity tracking, and UI

## Architecture

```text
React dashboard
    │ REST commands and periodic activity refresh
    ▼
FastAPI backend ───── stores metadata and serves uploaded media
    │ WebSocket commands, heartbeats and status updates
    ▼
Raspberry Pi agent
    │
    ├── HTTP uploads ───────────────► FastAPI /uploads
    │
    └── RTMP live stream
            ▼
        MediaMTX
            │ WebRTC / HLS
            ▼
        Browser live viewer
```

The FastAPI backend acts as the control plane. It queues remote commands, receives command-status events from the Raspberry Pi, persists camera and activity metadata in PostgreSQL, and exposes recent activity to the React dashboard.

Live video is sent directly from the Raspberry Pi to MediaMTX rather than passing through FastAPI. Snapshots and recorded clips are uploaded to FastAPI and displayed in the device media gallery.

## Command and Media Flow

```text
User sends a command from the dashboard
                │
                ▼
Backend creates a command ID and stores Queued
                │
                ▼
Command is delivered to the Pi through WebSocket
                │
                ▼
Pi reports Started → dashboard shows Running
                │
                ▼
Pi captures and uploads the image or video
                │
                ▼
Backend adds the upload to the device media gallery
                │
                ▼
Pi reports Done or Error
                │
                ▼
Dashboard shows Completed or Failed
```

The backend displays the latest 24 media items and five commands per camera. PostgreSQL retains activity records across backend restarts; the in-memory dictionary is still used for the active WebSocket/UI state.

## Project Structure

```text
backend/        FastAPI server, REST routes, WebSocket handling and storage
frontend/       React dashboard, device controls, media gallery and status UI
pi_agent/       Raspberry Pi camera and communication agent
tests/          Python integration/unit tests and Vitest UI tests
uploads/        Uploaded snapshots and recordings (object storage is a future step)\ndb/             PostgreSQL schema (idempotent setup/migration)
docker-compose.yml
mediamtx.yml
```

## Challenges Solved

Some of the engineering challenges explored in this project include:

- keeping a remote device connected reliably
- distinguishing online and offline device state
- sending commands asynchronously
- correlating asynchronous status events with the correct command
- exposing queued, running, completed, and failed states to the user
- handling media uploads from an edge device
- serving and displaying uploaded images and videos in the browser
- integrating live camera streaming into the browser
- structuring a project across frontend, backend, and device layers

## Main API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/devices` | Create a device |
| `GET` | `/devices` | List devices, connection state, recent media, and command history |
| `DELETE` | `/devices/{device_id}/remove` | Remove a device |
| `POST` | `/devices/{device_id}/command` | Queue a snapshot or recording command |
| `POST` | `/devices/{device_id}/upload` | Upload captured media and add it to device history |
| `WS` | `/devices/{device_id}/ws` | Device commands, heartbeats, and status updates |
| `GET` | `/devices/{device_id}/live` | Get live-stream metadata |
| `POST` | `/devices/{device_id}/live/start` | Queue live-stream startup |
| `POST` | `/devices/{device_id}/live/stop` | Queue live-stream shutdown |

Uploaded files are available under:

```text
/uploads/{filename}
```

## Run Locally

### Docker services and database

If you do not already have a local `.env`, create one from `.env.example` and change the development password. If you already have `.env`, **do not overwrite it**:

```bash
cp .env.example .env
```

On first setup **or after pulling a schema update**, start PostgreSQL and apply the
schema. Reapplying `db/schema.sql` is safe:

```bash
docker compose up -d db
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U camera_app -d camera_db < db/schema.sql
docker compose up -d --build
```

PostgreSQL is available on host `127.0.0.1:5434` for inspection, while the
backend connects to `db:5432` inside the Docker Compose network.

**First startup migration:** existing devices, recent media metadata, and command
records in `devices_db.json` are copied into PostgreSQL once. The source JSON
file and files in `uploads/` remain unchanged. An import marker prevents deleted
devices from being recreated on later restarts. Back up both before migrating.

**Current scope:** PostgreSQL stores metadata only; snapshots and video files
are still served from the mounted `uploads/` directory. A separate object-storage
integration will move file bytes out of that directory. This local setup has
no device authentication or protected media access yet: do not expose it to the
public internet.

If the database schema was not applied, backend startup will fail with a
missing-table error; run the `psql` command above and restart the backend.

- Dashboard: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

Create a device:

```bash
curl -X POST http://localhost:8000/devices \
  -H "Content-Type: application/json" \
  -d '{"name":"Living Room Camera"}'
```

Save the returned `id`; the Raspberry Pi agent uses it as `DEVICE_ID`.

## Run the Raspberry Pi Agent

The Pi requires `rpicam-still`, `rpicam-vid`, and `ffmpeg`.

```bash
cd raspberry-pi-security-camera
python3 -m pip install -r pi_agent/requirements.txt

export SERVER_URL=http://<SERVER_IP>:8000
export DEVICE_ID=<DEVICE_ID>
export RTMP_HOST=<SERVER_IP>

python3 pi_agent/main.py
```

Optional live-stream settings:

```bash
export LIVE_WIDTH=1280
export LIVE_HEIGHT=720
export LIVE_FPS=24
export LIVE_BITRATE=2000k
```

## Commands

Snapshot:

```json
{"type":"snapshot"}
```

Record a clip:

```json
{"type":"record","seconds":10}
```

Each queued command receives a unique ID. The agent includes that ID in its `started`, `done`, or `error` status message so the backend can update the correct command record.

Example command record returned through `GET /devices`:

```json
{
  "id": "command-uuid",
  "type": "snapshot",
  "status": "completed",
  "created_at": "2026-07-18T09:30:00+00:00",
  "updated_at": "2026-07-18T09:30:04+00:00",
  "error": null
}
```

## Dashboard

Each device card provides:

- online/offline state and last-seen time
- snapshot and recording controls
- live-stream controls
- recent command status and failure details
- a media gallery containing uploaded snapshots and recordings
- image previews and playable video elements

The dashboard refreshes device activity periodically, so command and upload changes appear without manually reloading the page.

## Tests

Install Python test dependencies:

```bash
python3 -m pip install -r backend/requirements.txt pytest pytest-asyncio httpx
```

Run all Python tests:

```bash
python3 -m pytest tests -v
```

Run frontend tests:

```bash
npm --prefix frontend install
npm --prefix frontend run test:run
```

Build the frontend:

```bash
npm --prefix frontend run build
```

Run the Python and frontend test suites together:

```bash
python3 -m pytest tests -v && npm --prefix frontend run test:run
```

The tests cover command handling, heartbeats, device lifecycle, offline failures, media uploads, activity-history helpers, REST-to-WebSocket delivery, live controls, and React UI workflows.

## Current Limitations

- Devices are currently registered through the API rather than the dashboard.
- PostgreSQL now stores device, media and command metadata, but the UI currently displays only recent items and there is no pagination.\n- Media file bytes are still stored on the local Docker-mounted `uploads/` directory; object storage has not been implemented yet.\n- In-memory state supports one backend worker; scaling requires removing the process-local command queues and using shared state.\n- Database calls currently use synchronous psycopg connections, including from async routes; use pooling/async operations before production-scale traffic.
- Authentication, cloud deployment, alerts, and computer-vision features are future work.

## Screenshots

<img width="2134" height="1468" alt="Sec-Cam dashboard" src="https://github.com/user-attachments/assets/7799f1f4-f046-402c-873a-e4e9a48758cc" />

<img width="991" height="777" alt="Sec-Cam device view" src="https://github.com/user-attachments/assets/c3a2a0bd-8e73-4b36-b044-47d5256dc265" />
