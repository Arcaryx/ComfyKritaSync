from __future__ import annotations

import asyncio
import uuid
from .websockets.src.websockets import client as ws_client
from PyQt5.QtCore import QThread, pyqtSignal, QObject


class LoopThread(QThread):
    def __init__(self, loop):
        super().__init__()
        self._loop = loop

    def run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


class KritaClient(QObject):
    websocket_updated = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._websocket = None

        self._loop = asyncio.new_event_loop()
        self._loop.set_debug(True)
        self._loop_thread = LoopThread(self._loop)
        self._loop_thread.start()
        self._id = str(uuid.uuid4())

    _instance: KritaClient | None = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = KritaClient()
        return cls._instance

    async def connect(self):
        async for self._websocket in ws_client.connect(f"ws://127.0.0.1:8188/krita-sync-ws?clientId={self._id}&clientType=krita", max_size=2**30, read_limit=2**30):
            try:
                self.websocket_updated.emit(True)
                async for message in self._websocket:
                    print(message)
            except Exception as e:
                continue
            break
        self._websocket = None
        self.websocket_updated.emit(False)

    async def disconnect(self):
        if self._websocket is not None:
            await self._websocket.close()
            self._websocket = None

    def is_connected(self):
        return self._websocket is not None

    def run(self, future):
        return asyncio.run_coroutine_threadsafe(future, self._loop)

    def is_event_loop_running(self):
        return self._loop.is_running()
