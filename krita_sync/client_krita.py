from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from copy import copy
from enum import IntEnum

from PyQt5.QtCore import QThread, pyqtSignal, QObject, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QImage
from krita import Krita  # type: ignore

from .cks_common.CksBinaryMessage import CksBinaryMessage, PayloadType, MessageType, GetImageKritaJsonPayload, DocumentSyncJsonPayload, SendImageKritaJsonPayload
from krita_sync.util import get_document_name
from .websockets.src.websockets import client as ws_client
import traceback
from typing import cast


def _print_exception_trace(exception):
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


def _flatten_tree(node):
    result = [node]
    child_nodes = node.childNodes()
    child_nodes = sorted(child_nodes, key=lambda node: node.index(), reverse=True)
    for child in child_nodes:
        result.extend(_flatten_tree(child))
    return result


class KritaClient(QObject):
    websocket_updated = pyqtSignal(ConnectionState)
    websocket_message_received = pyqtSignal(CksBinaryMessage)
    image_added = pyqtSignal(str, str, list)
    document_changed = pyqtSignal(str)
    delete_selected_image = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._websocket = None

        self._loop = asyncio.new_event_loop()
        self._loop.set_debug(False)
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
        self.document_list = [] # Tuple(DocumentId, DocumentName)
        self.run_map = {}       # DocumentId -> {RunId, ImageIds}
        self.image_map = {}     # ImageId -> QImage

    _instance: KritaClient | None = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = KritaClient()
        return cls._instance

    def delete_cks_image(self):
        self.delete_selected_image.emit()

    def websocket_updated_handler(self, connected):
        if connected:
            self.documents_changed_handler(None)

    def discard_image(self, document_id, run_uuid, image_uuid):
        if document_id in self.run_map and run_uuid in self.run_map[document_id]:
            images_metadata = self.run_map[document_id][run_uuid]
            for image_metadata in images_metadata:
                if image_metadata["image_uuid"] == image_uuid:
                    images_metadata.remove(image_metadata)
                    break
        if image_uuid in self.image_map:
            del self.image_map[image_uuid]

    def clear_history_for_document_id(self, document_id):
        # Get all image IDs for those documents from self.run_map and delete the images in self.image_map, as well as the runs from self.run_map
        if document_id in self.run_map:
            # Get all image_ids for the document
            for run_id, images_metadata in self.run_map[document_id].items():
                for image_metadata in images_metadata:
                    image_id = image_metadata["image_uuid"]
                    if image_id in self.image_map:
                        del self.image_map[image_id]
            del self.run_map[document_id]

    def documents_changed_handler(self, _):
        if self._websocket is not None:
            documents = Krita.instance().documents()

            # Get old document IDs from self.document_list
            old_document_ids = [doc_id for doc_id, _ in self.document_list]

            self.document_list = [(document.rootNode().uniqueId().toString()[1:-1], get_document_name(document)) for document in documents]

            # Get new document IDs from self.document_list
            new_document_ids = [doc_id for doc_id, _ in self.document_list]

            # Get a list of any document IDs that are now missing from new_document_ids compared to old_document_ids
            missing_document_ids = set(old_document_ids) - set(new_document_ids)

            # Get all image IDs for those documents from self.run_map and delete the images in self.image_map, as well as the runs from self.run_map
            for missing_doc_id in missing_document_ids:
                self.clear_history_for_document_id(missing_doc_id)

            message = CksBinaryMessage(DocumentSyncJsonPayload(self.document_list))
            message_bytes = message.encode_message()
            self.run(self._websocket.send(message_bytes))

    def websocket_message_received_handler(self, decoded_message):
        json_payload = decoded_message.json_payload

        if json_payload.type == MessageType.SendImageKrita:
            send_image_krita_payload = cast(SendImageKritaJsonPayload, json_payload)

            documents = Krita.instance().documents()
            document_ids = [document.rootNode().uniqueId().toString()[1:-1] for document in documents]

            if send_image_krita_payload.krita_document not in document_ids:
                print(f"Krita document {send_image_krita_payload.krita_document} not found, skipping.")
                return

            if (send_image_krita_payload.add_to_previous_run
                and send_image_krita_payload.krita_document in self.run_map
                and len(self.run_map[send_image_krita_payload.krita_document]) > 0):
                previous_run_uuid = next(reversed(self.run_map[send_image_krita_payload.krita_document]))
                run_uuid = previous_run_uuid
                send_image_krita_payload.run_uuid = run_uuid
            else:
                run_uuid = send_image_krita_payload.run_uuid

            images_metadata = []
            for payload in decoded_message.payloads:
                image = _extract_message_png_image(payload)
                if image is None:
                    raise Exception("Error extracting png image from payload.")
                image_uuid = str(uuid.uuid4())

                image_metadata = copy(send_image_krita_payload.__dict__)
                image_metadata["image_uuid"] = image_uuid

                self.image_map[image_uuid] = image
                if send_image_krita_payload.krita_document in self.run_map:
                    if run_uuid in self.run_map[send_image_krita_payload.krita_document]:
                        self.run_map[send_image_krita_payload.krita_document][run_uuid].append(image_metadata)
                    else:
                        self.run_map[send_image_krita_payload.krita_document][run_uuid] = [image_metadata]
                else:
                    self.run_map[send_image_krita_payload.krita_document] = OrderedDict()
                    self.run_map[send_image_krita_payload.krita_document][run_uuid] = [image_metadata]
                images_metadata.append(image_metadata)
            self.image_added.emit(send_image_krita_payload.krita_document, run_uuid, images_metadata)

        elif json_payload.type == MessageType.GetImageKrita:
            get_image_krita_payload = cast(GetImageKritaJsonPayload, json_payload)
            documents = Krita.instance().documents()

            for document in documents:
                document_uuid = document.rootNode().uniqueId().toString()[1:-1]

                if get_image_krita_payload.krita_document == document_uuid:
                    target_layer_string = get_image_krita_payload.krita_layer

                    layer_names = target_layer_string.split("/")
                    if len(layer_names) == 1:
                        node_list = _flatten_tree(document.rootNode())
                        node_list = [node for node in node_list if node.name() == layer_names[0] and node.type() in ["grouplayer", "paintlayer"]]
                        if len(node_list) > 0:
                            target_layer = node_list[0]
                    else:
                        current_node = document.rootNode()
                        for i in range(len(layer_names) - 1):
                            current_node = self.getOrCreateGroupNode(document, current_node, layer_names[i], create_if_missing=False)
                        found_nodes = current_node.findChildNodes(layer_names[-1], False, False, "grouplayer", 0)
                        if len(found_nodes) > 0:
                            found_nodes = sorted(found_nodes, key=lambda node: node.index(), reverse=True)
                            target_layer = found_nodes[0]
                        else:
                            found_nodes = current_node.findChildNodes(layer_names[-1], False, False, "paintlayer", 0)
                            if len(found_nodes) > 0:
                                found_nodes = sorted(found_nodes, key=lambda node: node.index(), reverse=True)
                                target_layer = found_nodes[0]
                            else:
                                target_layer = current_node

                    if target_layer is None:
                        raise Exception(f"Krita layer {target_layer_string} not found.")

                    pixel_data = target_layer.projectionPixelData(0, 0, document.width(), document.height())
                    q_image = QImage(pixel_data, document.width(), document.height(), QImage.Format.Format_ARGB32)

                    buffer = QBuffer()
                    buffer.open(QIODevice.WriteOnly)
                    q_image.save(buffer, "PNG")
                    byte_array = buffer.data()

                    message = CksBinaryMessage(json_payload)
                    message.add_payload(PayloadType.PNG, byte_array)

                    message_bytes = message.encode_message()

                    self.run(self._websocket.send(message_bytes))

                    break

    def getOrCreateGroupNode(self, doc: Krita.Document, parent_node, group_layer_name: str, create_if_missing: bool = True):
        group_nodes = parent_node.findChildNodes(group_layer_name, False, False, "grouplayer", 0)

        if len(group_nodes) == 0:
            if create_if_missing:
                group_node = doc.createNode(group_layer_name, "grouplayer")
                parent_node.addChildNode(group_node, None)
                return group_node
            return None
        else:
            group_nodes = sorted(group_nodes, key=lambda node: node.index(), reverse=True)
            return group_nodes[0]

    def create(self, doc: Krita.Document, layer_name: str, img: QImage | None = None, preview: bool=False):
        if not img:
            raise ValueError("img must not be None!")
        layer_names = layer_name.split("/")
        if len(layer_names) == 1:
            new_layer_parent_node = doc.rootNode()
            node = doc.createNode(layer_name, "paintlayer")
        else:
            new_layer_parent_node = doc.rootNode()
            for i in range(len(layer_names)-1):
                new_layer_parent_node = self.getOrCreateGroupNode(doc, new_layer_parent_node, layer_names[i])
            node = doc.createNode(layer_names[-1], "paintlayer")

        if preview:
            node.setLocked(True)

        converted_image = img.convertToFormat(QImage.Format.Format_ARGB32)

        ptr = converted_image.constBits()
        converted_image_bytes = QByteArray(ptr.asstring(converted_image.byteCount()))
        node.setPixelData(converted_image_bytes, 0, 0, converted_image.width(), converted_image.height())
        new_layer_parent_node.addChildNode(node, None)

    def remove(self, doc: Krita.Document, layer_name: str):
        layer_names = layer_name.split("/")
        if len(layer_names) == 1:
            preview_node = doc.nodeByName(layer_name)
            if preview_node is not None:
                preview_node.remove()
        else:
            current_node = doc.rootNode()
            for i in range(len(layer_names) - 1):
                found_nodes = current_node.findChildNodes(layer_names[i], False, False, "grouplayer", 0)
                if len(found_nodes) > 0:
                    current_node = found_nodes[0]
                else:
                    print(f"Couldn't find layer {layer_names[i]} while searching for path {layer_name}")
                    return
            found_nodes = current_node.findChildNodes(layer_names[-1], False, False, "paintlayer", 0)
            if len(found_nodes) > 0:
                found_nodes[0].remove()
            else:
                print(f"Couldn't find layer {layer_names[-1]} while searching for path {layer_name}")

    async def connect(self, url):
        try:
            url = url.replace("http", "ws", 1)
            self._connection_state = ConnectionState.Connecting
            self.websocket_updated.emit(self._connection_state)

            async for self._websocket in ws_client.connect(
                uri=f"{url}/krita-sync-ws?clientId={self._id}&clientType=krita",
                # logger=logging.getLogger(), if we need to add a logger
                max_size=2 ** 30,
                read_limit=2 ** 30
            ):
                try:
                    self._connection_state = ConnectionState.Connected
                    self.websocket_updated.emit(self._connection_state)
                    async for message in self._websocket:
                        decoded_message = CksBinaryMessage.decode_message(message)
                        self.websocket_message_received.emit(decoded_message)
                except Exception as e:
                    _print_exception_trace(e)
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
