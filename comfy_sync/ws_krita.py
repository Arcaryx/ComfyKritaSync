from __future__ import annotations

import asyncio
import struct
import types
from io import BytesIO

from server import BinaryEventTypes, PromptServer, send_socket_catch_exception  # type: ignore
from . import nodes
from ..krita_sync.cks_common import CksBinaryMessage
from ..krita_sync.cks_common.CksBinaryMessage import CksJsonPayload, PayloadType


def encode_bytes(event, data):
    if not isinstance(event, int):
        raise RuntimeError(f"Binary event types must be integers, got {event}")

    packed = struct.pack(">I", event)
    message = bytearray(packed)
    message.extend(data)
    return message


class KritaWsManager:
    def __init__(self):
        self.sockets = dict()
        self.messages = asyncio.Queue()
        self.loop = PromptServer.instance.loop
        self.publish_task = self.loop.create_task(self.publish_loop())
        self.documents = dict()
        self.document_combo = ["Missing Document"]
        self.remote_documents = []

        # This exists to function with ComfyUI_NetDist
        self.original_put = PromptServer.instance.prompt_queue.put
        def new_prompt_queue_put(self, item):
            with self.mutex:
                KritaWsManager.instance().clean_document_combo()
                KritaWsManager.instance().original_put(item)
        PromptServer.instance.prompt_queue.put = types.MethodType(new_prompt_queue_put, PromptServer.instance.prompt_queue)
        PromptServer.instance.add_on_prompt_handler(self.fix_document_combo)

    _instance: KritaWsManager | None = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = KritaWsManager()
        return cls._instance

    def fix_document_combo(self, json_data):
        # This exists to function with ComfyUI_NetDist
        prompt = json_data["prompt"]
        for v in prompt.values():
            if "class_type" in v:
                cls = v["class_type"]
                if cls == "CKS_GetImageKrita" or cls == "CKS_SendImageKrita" or cls == "CKS_SelectKritaDocument":
                    inputs = v["inputs"]
                    document_combo_item = inputs["document"]
                    if document_combo_item not in self.document_combo:
                        self.remote_documents.append(document_combo_item)
                        self.document_combo.append(document_combo_item)
                        nodes.update_node_return_types()

        return json_data

    def clean_document_combo(self):
        for document_combo_item in self.remote_documents:
            if document_combo_item in self.document_combo:
                self.document_combo.remove(document_combo_item)
                nodes.update_node_return_types()
        self.remote_documents = []

    async def send(self, json_payload: CksJsonPayload, image_data=None, sid=None):
        cks_message = CksBinaryMessage(json_payload)

        if image_data is not None:
            for image in image_data:
                bytes_io = BytesIO()
                image.save(bytes_io, format="PNG")
                cks_message.add_payload(PayloadType.PNG, bytes_io.getvalue())

        cks_message_bytes = cks_message.encode_message()

        if sid is None:
            sockets = list(self.sockets.values())
            for ws in sockets:
                await ws.send_bytes(cks_message_bytes)
        elif sid in self.sockets:
            await self.sockets[sid].send_bytes(cks_message_bytes)

    def send_sync(self, json_payload: CksJsonPayload = None, image_data=None, sid=None):
        self.loop.call_soon_threadsafe(
            self.messages.put_nowait,
            (json_payload, image_data, sid)
        )

    async def publish_loop(self):
        while True:
            msg = await self.messages.get()
            await self.send(*msg)
