from __future__ import annotations

import threading
import time
from types import TracebackType
from typing import Callable, ClassVar

import sounddevice as sd  # pyright: ignore[reportMissingTypeStubs]

Callback = Callable[[bytearray, int, object, object], None]


class FakeOutputStream:
    """Small callback-driven OutputStream replacement for unit tests."""

    instances: ClassVar[list[FakeOutputStream]] = []

    def __init__(
        self,
        samplerate: int,
        blocksize: int,
        channels: int,
        dtype: str,
        callback: Callback,
    ) -> None:
        self.samplerate: int = samplerate
        self.blocksize: int = blocksize
        self.channels: int = channels
        self.dtype: str = dtype
        self.callback: Callback = callback
        self.started: threading.Event = threading.Event()
        self.closed: bool = False
        self.callback_count: int = 0
        self._callback_done: threading.Event = threading.Event()
        type(self).instances.append(self)

    def __enter__(self) -> FakeOutputStream:
        self.started.set()

        def run_callback() -> None:
            try:
                while True:
                    outdata = bytearray(self.blocksize * self.channels * 4)
                    time.sleep(0.02)
                    try:
                        self.callback(outdata, self.blocksize, None, None)
                    except (sd.CallbackAbort, sd.CallbackStop):
                        break
                    self.callback_count += 1
            finally:
                self._callback_done.set()

        threading.Thread(target=run_callback, daemon=True).start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _ = self._callback_done.wait(timeout=2)
        self.closed = True
