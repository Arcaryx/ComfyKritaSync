from __future__ import annotations

import asyncio
import uuid
from .websockets.src.websockets import client as ws_client
from PyQt5.QtCore import QThread


class LoopThread(QThread):
    def __init__(self, loop):
        super().__init__()
        self._loop = loop

    def run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


class KritaClient:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
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
        async with ws_client.connect(f"ws://127.0.0.1:8188/krita-sync-ws?clientId={self._id}&clientType=krita"):
            pass

    def run(self, future):
        return self._loop.create_task(future)
