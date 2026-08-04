"""Cross-platform Ctrl-C/SIGTERM handling for the CLI entry points.

asyncio's loop.add_signal_handler isn't implemented on Windows's default
event loop (it raises NotImplementedError), so this falls back to the
standard signal module there.
"""

from __future__ import annotations

import asyncio
import signal


def install_shutdown_handler(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    except NotImplementedError:

        def _handler(signum, frame) -> None:
            loop.call_soon_threadsafe(stop_event.set)

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
