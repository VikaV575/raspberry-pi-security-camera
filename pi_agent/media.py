import asyncio
from pathlib import Path
import aiohttp

try:
    from .config import UPLOAD_URL, WORK_DIR
    from .utils import ts
except ImportError:
    from config import UPLOAD_URL, WORK_DIR
    from utils import ts


def make_snapshot_path() -> Path:
    return WORK_DIR / f"snapshot_{ts()}.jpg"


def make_video_path() -> Path:
    return WORK_DIR / f"video_{ts()}.mp4"


async def run_cmd(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    stdout_text = stdout.decode(errors="ignore")
    stderr_text = stderr.decode(errors="ignore")

    if stdout_text.strip():
        print(f"[cmd stdout] {stdout_text}")
    if stderr_text.strip():
        print(f"[cmd stderr] {stderr_text}")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(args)}\n"
            f"stdout: {stdout_text}\n"
            f"stderr: {stderr_text}"
        )


async def capture_snapshot() -> Path:
    out_path = make_snapshot_path()

    await run_cmd(
        "rpicam-still",
        "-n",
        "-o", str(out_path),
        "--width", "1280",
        "--height", "720",
    )

    if not out_path.is_file():
        raise RuntimeError(f"Snapshot file was not created: {out_path}")
    if out_path.stat().st_size == 0:
        raise RuntimeError(f"Snapshot file is empty: {out_path}")

    return out_path


async def capture_video(seconds: int) -> Path:
    out_path = make_video_path()
    timeout_ms = max(1, seconds) * 1000

    await run_cmd(
        "rpicam-vid",
        "-n",
        "-t", str(timeout_ms),
        "--codec", "libav",
        "--libav-format", "mp4",
        "-o", str(out_path),
        "--width", "1280",
        "--height", "720",
    )

    if not out_path.exists():
        raise RuntimeError(f"Video file was not created: {out_path}")

    size = out_path.stat().st_size
    print(f"[video] created: {out_path} ({size} bytes)")

    if size == 0:
        raise RuntimeError(f"Video file is empty: {out_path}")

    return out_path


def guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".mp4":
        return "video/mp4"

    return "application/octet-stream"


async def upload_file(session: aiohttp.ClientSession, path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    file_size = path.stat().st_size
    content_type = guess_content_type(path)

    print(f"[upload] uploading: {path.name} ({file_size} bytes, {content_type})")

    with path.open("rb") as f:
        data = aiohttp.FormData()
        data.add_field(
            "file",
            f,
            filename=path.name,
            content_type=content_type,
        )

        async with session.post(UPLOAD_URL, data=data) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Upload failed: {resp.status} {text}")

            print(f"[upload] success: {path.name}")
            print(f"[upload] response: {text}")