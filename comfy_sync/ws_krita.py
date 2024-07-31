from __future__ import annotations

import asyncio
import struct
from io import BytesIO

from server import BinaryEventTypes, PromptServer, send_socket_catch_exception  # type: ignore
from ..krita_sync.cks_common import CksBinaryMessage


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

    _instance: KritaWsManager | None = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = KritaWsManager()
        return cls._instance

    async def send(self, json_data, image_data=None, sid=None):
        print(f"sending json_data: {json_data}")
        cks_message = CksBinaryMessage()

        cks_message.add_payload('json', json_data)

        if image_data is not None:
            bytes_io = BytesIO()
            image_data.save(bytes_io, format="PNG")
            cks_message.add_payload('png', bytes_io.getvalue())

        cks_message_bytes = cks_message.encode_message()

        if sid is None:
            sockets = list(self.sockets.values())
            for ws in sockets:
                await ws.send_bytes(cks_message_bytes)
        elif sid in self.sockets:
            await self.sockets[sid].send_bytes(cks_message_bytes)

    def send_sync(self, json_data, image_data=None, sid=None):
        print("Send_sync")
        self.loop.call_soon_threadsafe(
            self.messages.put_nowait,
            (json_data, image_data, sid)
        )

    async def publish_loop(self):
        while True:
            print("Waiting for a message")
            msg = await self.messages.get()
            print("Got a message!")
            await self.send(*msg)
