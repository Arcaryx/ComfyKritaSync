import io
import os
import uuid
import folder_paths  # type: ignore
from PIL import Image
from ..krita_sync.cks_common.CksBinaryMessage import MessageType
from ..krita_sync.cks_common import CksBinaryMessage
from server import PromptServer  # type: ignore
from aiohttp import web, WSMsgType
from . import ws_krita


@PromptServer.instance.routes.get('/krita-sync-ws')
async def krita_websocket_handler(request):
    ws = web.WebSocketResponse(max_msg_size=2 ** 30)
    await ws.prepare(request)
    sid = request.rel_url.query.get('clientId', '')
    client_type = request.rel_url.query.get('clientType', '')
    print(f"Client {sid} connected to krita-sync-ws as type {client_type}")

    if sid:
        # Reusing existing session, remove old
        ws_krita.KritaWsManager.instance().sockets.pop(sid, None)
    else:
        sid = uuid.uuid4().hex
    ws_krita.KritaWsManager.instance().sockets[sid] = ws

    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                print('ws connection.py closed with exception %s' % ws.exception())
            else:
                decoded_message = CksBinaryMessage.decode_message(msg.data)
                print(f"Total payloads: {len(decoded_message.payloads)}")
                json_payload = decoded_message.payloads[0][1]
                print(json_payload)
                if json_payload["MessageType"] == str(MessageType.GetImageKrita):
                    byte_array = decoded_message.payloads[1][1]
                    image = Image.open(io.BytesIO(byte_array))
                    filename_prefix = json_payload["FileNamePrefix"]
                    full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_temp_directory())
                    file = f"{filename}_s.png"
                    image.save(os.path.join(full_output_folder, file), compress_level=1)
                    os.rename(os.path.join(full_output_folder, file), os.path.join(full_output_folder, f"{filename}_.png"))  # >:(

    finally:
        ws_krita.KritaWsManager.instance().sockets.pop(sid, None)
    return ws
