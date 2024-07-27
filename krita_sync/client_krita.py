from __future__ import annotations

import asyncio
import struct
import uuid

from PIL import Image
from PyQt5.QtGui import QImage

from .websockets.src.websockets import client as ws_client
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QByteArray
from krita import Krita  # type: ignore


class LoopThread(QThread):
    def __init__(self, loop):
        super().__init__()
        self._loop = loop

    def run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


def _extract_message_png_image(data: memoryview):
    s = struct.calcsize(">II")
    if len(data) > s:
        event, format = struct.unpack_from(">II", data)
        # ComfyUI server.py: BinaryEventTypes.PREVIEW_IMAGE=1, PNG=2
        if event == 1 and format == 2:
            return QImage.fromData(data[s:], None)
    return None


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

    def create(
        self,
        doc: Krita.Document,
        name: str,
        img: QImage | None = None,
    ):
        node = doc.createNode(name, "paintlayer")
        if img:
            converted_image = img.convertToFormat(QImage.Format.Format_ARGB32)
            ptr = converted_image.constBits()
            converted_image_bytes = QByteArray(ptr.asstring(converted_image.byteCount()))
            node.setPixelData(converted_image_bytes, 0, 0, 1024, 1024)
            root = doc.rootNode()
            root.addChildNode(node, None)

    # FIXME: We're not getting errors/logs at all when websockets fail to connect
    async def connect(self):
        try:
            async for self._websocket in ws_client.connect(f"ws://127.0.0.1:8188/krita-sync-ws?clientId={self._id}&clientType=krita", max_size=2**30, read_limit=2**30):
                try:
                    self.websocket_updated.emit(True)
                    async for message in self._websocket:
                        if isinstance(message, bytes):
                            image = _extract_message_png_image(memoryview(message))
                            documents = Krita.instance().documents()
                            if image is not None and len(documents) > 0:
                                document = documents[0]
                                self.create(document, "test", image)

                        elif isinstance(message, str):
                            print(message)
                except Exception as e:
                    print("Exception while processing ws messages", e)
                    continue
                break
        except Exception as e:
            print("Exception while connecting to ws", e)
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
