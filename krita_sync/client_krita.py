from __future__ import annotations

import asyncio
import io
import os
import uuid
from enum import IntEnum

from PyQt5.QtCore import QThread, pyqtSignal, QObject, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QImage, QImageWriter
from krita import Krita  # type: ignore

from .cks_common.CksBinaryMessage import CksBinaryMessage, PayloadType, MessageType, GetImageKritaJsonPayload, DocumentSyncJsonPayload, SendImageKritaJsonPayload
from .websockets.src.websockets import client as ws_client
import traceback
from typing import cast


def print_exception_trace(exception):
    traceback.print_exception(type(exception), exception, exception.__traceback__)


class ConnectionState(IntEnum):
    Disconnected = 0
    Connected = 1
    Connecting = 2


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


def _get_document_name(document):
    document_name = document.fileName()
    if (document_name is None) or (document_name == ""):
        return document.name()
    else:
        return os.path.basename(document.fileName())


class KritaClient(QObject):
    websocket_updated = pyqtSignal(ConnectionState)
    websocket_message_received = pyqtSignal(CksBinaryMessage)

    def __init__(self):
        super().__init__()
        self._websocket = None

        self._loop = asyncio.new_event_loop()
        self._loop.set_debug(True)
        self._loop_thread = LoopThread(self._loop)
        self._loop_thread.start()
        self._id = str(uuid.uuid4())
        self._connection_state = ConnectionState.Disconnected
        self.connection_coroutine = None
        self.websocket_message_received.connect(self.websocket_message_received_handler)

        notifier = Krita.instance().notifier()
        notifier.setActive(True)
        notifier.imageCreated.connect(self.documents_changed_handler)
        notifier.imageClosed.connect(self.documents_changed_handler)
        notifier.imageSaved.connect(self.documents_changed_handler)
        self.websocket_updated.connect(self.websocket_updated_handler)
        self.document_map = {}

    _instance: KritaClient | None = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = KritaClient()
        return cls._instance

    def websocket_updated_handler(self, connected):
        if connected:
            self.documents_changed_handler(None)

    def documents_changed_handler(self, _):
        if self._websocket is not None:
            documents = Krita.instance().documents()
            self.document_map = [(document.rootNode().uniqueId().toString()[1:-1], _get_document_name(document)) for document in documents]

            message = CksBinaryMessage(DocumentSyncJsonPayload(self.document_map))
            message_bytes = message.encode_message()
            self.run(self._websocket.send(message_bytes))

    def websocket_message_received_handler(self, decoded_message):
        print(f"Total payloads: {len(decoded_message.payloads)}")
        json_payload = decoded_message.json_payload
        print(json_payload)

        if json_payload.type == MessageType.SendImageKrita:
            send_image_krita_payload = cast(SendImageKritaJsonPayload, json_payload)
            documents = Krita.instance().documents()
            for document in documents:
                document_uuid = document.rootNode().uniqueId().toString()[1:-1]

                if send_image_krita_payload.krita_document == document_uuid:
                    created_layer_index = 1
                    for payload in decoded_message.payloads:
                        image = _extract_message_png_image(payload)
                        if image is not None:
                            self.create(document, f"test-{created_layer_index}", image)
                            created_layer_index += 1
        elif json_payload.type == MessageType.GetImageKrita:
            get_image_krita_payload = cast(GetImageKritaJsonPayload, json_payload)
            documents = Krita.instance().documents()
            for document in documents:
                document_uuid = document.rootNode().uniqueId().toString()[1:-1]

                if get_image_krita_payload.krita_document == document_uuid:
                    target_layer_string = get_image_krita_payload.krita_layer
                    target_layer = document.nodeByName(target_layer_string)
                    if target_layer is None:
                        raise Exception(f"Krita layer {target_layer_string} not found.")
                    # TODO: Make sure we can pull a group of layers properly
                    pixel_data = target_layer.projectionPixelData(0, 0, document.width(), document.height())
                    q_image = QImage(pixel_data, document.width(), document.height(), QImage.Format.Format_ARGB32)

                    buffer = QBuffer()
                    buffer.open(QIODevice.WriteOnly)
                    q_image.save(buffer, "PNG")
                    byte_array = buffer.data()

                    message = CksBinaryMessage(json_payload)
                    message.add_payload(PayloadType.PNG, io.BytesIO(byte_array).getvalue())  # TODO: Is this necessary?

                    message_bytes = message.encode_message()

                    self.run(self._websocket.send(message_bytes))

                    break

    def create(self, doc: Krita.Document, name: str, img: QImage | None = None, ):
        node = doc.createNode(name, "paintlayer")
        if img:
            converted_image = img.convertToFormat(QImage.Format.Format_ARGB32)

            ptr = converted_image.constBits()
            converted_image_bytes = QByteArray(ptr.asstring(converted_image.byteCount()))
            node.setPixelData(converted_image_bytes, 0, 0, converted_image.width(), converted_image.height())
            root = doc.rootNode()
            root.addChildNode(node, None)

    # FIXME: We're not getting errors/logs at all when websockets fail to connect
    async def connect(self, url):
        try:
            url = url.replace("http", "ws", 1)
            self._connection_state = ConnectionState.Connecting
            self.websocket_updated.emit(self._connection_state)
            async for self._websocket in ws_client.connect(f"{url}/krita-sync-ws?clientId={self._id}&clientType=krita", max_size=2 ** 30, read_limit=2 ** 30):
                try:
                    self._connection_state = ConnectionState.Connected
                    self.websocket_updated.emit(self._connection_state)
                    async for message in self._websocket:
                        decoded_message = CksBinaryMessage.decode_message(message)
                        self.websocket_message_received.emit(decoded_message)
                except Exception as e:
                    print_exception_trace(e)
                    print("Exception while processing ws messages, waiting 5 seconds before attempting to reconnect")
                    self._websocket = None
                    self._connection_state = ConnectionState.Connecting
                    self.websocket_updated.emit(self._connection_state)

                    await asyncio.sleep(5)

                    continue

                break
        except Exception as e:
            print("Exception while connecting to ws", e)
        self._websocket = None
        self._connection_state = ConnectionState.Disconnected
        self.websocket_updated.emit(self._connection_state)

    async def disconnect(self):
        if self._websocket is not None:
            await self._websocket.close()
            self._websocket = None

    def get_connection_state(self):
        return self._connection_state

    def kill_connection_coroutine(self):
        if self.connection_coroutine is not None:
            self.connection_coroutine.cancel()
            self.connection_coroutine = None
            self._connection_state = ConnectionState.Disconnected
            self.websocket_updated.emit(self._connection_state)

    def run(self, future):
        return asyncio.run_coroutine_threadsafe(future, self._loop)

    def is_event_loop_running(self):
        return self._loop.is_running()
