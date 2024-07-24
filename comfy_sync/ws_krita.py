from __future__ import annotations

import asyncio
import struct
from server import BinaryEventTypes, PromptServer, send_socket_catch_exception  # type: ignore
from io import BytesIO
from PIL import Image, ImageOps


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

    async def send(self, event, data, sid=None):
        if event == BinaryEventTypes.UNENCODED_PREVIEW_IMAGE:
            await self.send_image(data, sid=sid)
        elif isinstance(data, (bytes, bytearray)):
            await self.send_bytes(event, data, sid)
        else:
            await self.send_json(event, data, sid)

    async def send_image(self, image_data, sid=None):
        image_type = image_data[0]
        image = image_data[1]
        max_size = image_data[2]
        if max_size is not None:
            if hasattr(Image, 'Resampling'):
                resampling = Image.Resampling.BILINEAR
            else:
                resampling = Image.ANTIALIAS

            image = ImageOps.contain(image, (max_size, max_size), resampling)
        type_num = 1
        if image_type == "JPEG":
            type_num = 1
        elif image_type == "PNG":
            type_num = 2

        bytes_io = BytesIO()
        header = struct.pack(">I", type_num)
        bytes_io.write(header)
        image.save(bytes_io, format=image_type, quality=95, compress_level=1)
        preview_bytes = bytes_io.getvalue()
        await self.send_bytes(BinaryEventTypes.PREVIEW_IMAGE, preview_bytes, sid=sid)

    async def send_bytes(self, event, data, sid=None):
        message = encode_bytes(event, data)

        if sid is None:
            sockets = list(self.sockets.values())
            for ws in sockets:
                await send_socket_catch_exception(ws.send_bytes, message)
        elif sid in self.sockets:
            await send_socket_catch_exception(self.sockets[sid].send_bytes, message)

    async def send_json(self, event, data, sid=None):
        message = {"type": event, "data": data}

        if sid is None:
            sockets = list(self.sockets.values())
            for ws in sockets:
                await send_socket_catch_exception(ws.send_json, message)
        elif sid in self.sockets:
            await send_socket_catch_exception(self.sockets[sid].send_json, message)

    def send_sync(self, event, data, sid=None):
        print("Send_sync")
        self.loop.call_soon_threadsafe(
            self.messages.put_nowait,
            (event, data, sid)
        )

    async def publish_loop(self):
        while True:
            print("Waiting for a message")
            msg = await self.messages.get()
            print("Got a message!")
            await self.send(*msg)
