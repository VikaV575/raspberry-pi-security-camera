import asyncio

try:
    from .config import DEVICE_ID
    from .live import stop_live_stream
    from .state import AgentState
    from .ws_client import connect_forever
except ImportError:
    from config import DEVICE_ID
    from live import stop_live_stream
    from state import AgentState
    from ws_client import connect_forever


async def run_agent() -> None:
    state = AgentState()

    try:
        await connect_forever(state)
    finally:
        print("[shutdown] cleaning up...")
        await stop_live_stream(state)


def main() -> None:
    if DEVICE_ID == "PUT_DEVICE_ID_HERE":
        raise SystemExit("You must set DEVICE_ID env var or edit the script.")

    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\n[shutdown] agent stopped")

if __name__ == "__main__":
    main()