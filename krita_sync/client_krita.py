from __future__ import annotations

import asyncio
import time
import uuid

from PyQt5.QtCore import QThread, pyqtSignal, QObject, QByteArray
from PyQt5.QtGui import QImage
from krita import Krita  # type: ignore

from .cks_common.CksBinaryMessage import CksBinaryMessage, PayloadType
from .websockets.src.websockets import client as ws_client
import traceback


def print_exception_trace(exception):
    traceback.print_exception(type(exception), exception, exception.__traceback__)


class LoopThread(QThread):
    def __init__(self, loop):
        super().__init__()
        self._loop = loop

    def run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()


def _extract_message_png_image(payload):
    (payload_type, content) = payload
    if payload_type == PayloadType.PNG:
        return QImage.fromData(content, None)
    else:
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
            node.setPixelData(converted_image_bytes, 0, 0, converted_image.width(), converted_image.height())
            root = doc.rootNode()
            root.addChildNode(node, None)

    # FIXME: We're not getting errors/logs at all when websockets fail to connect
    async def connect(self):
        try:
            async for self._websocket in ws_client.connect(
                    f"ws://127.0.0.1:8188/krita-sync-ws?clientId={self._id}&clientType=krita", max_size=2 ** 30,
                    read_limit=2 ** 30):
                try:
                    self.websocket_updated.emit(True)
                    async for message in self._websocket:
                        print("Got a websocket message")
                        if isinstance(message, bytes):
                            decoded_message = CksBinaryMessage.decode_message(message)
                            print(f"Total payloads: {len(decoded_message.payloads)}")
                            print(decoded_message.payloads[0])

                            if len(decoded_message.payloads) > 1:
                                documents = Krita.instance().documents()
                                if len(documents) > 0:
                                    document = documents[0]

                                    created_layer_index = 1
                                    for payload in decoded_message.payloads[1:]:
                                        image = _extract_message_png_image(payload)
                                        if image is not None:
                                            self.create(document, f"test-{created_layer_index}", image)
                                            created_layer_index += 1

                        elif isinstance(message, str):
                            print(message)
                except Exception as e:
                    print_exception_trace(e)
                    print("Exception while processing ws messages, waiting 5 seconds before attempting to reconnect")
                    time.sleep(5)
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
