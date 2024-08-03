import io
import os
import uuid
import folder_paths  # type: ignore
from PIL import Image

from ..krita_sync.cks_common.CksBinaryMessage import MessageType, GetImageKritaJsonPayload, DocumentSyncJsonPayload
from ..krita_sync.cks_common import CksBinaryMessage
from server import PromptServer  # type: ignore
from aiohttp import web, WSMsgType
from . import ws_krita, nodes
from typing import cast


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
                json_payload = decoded_message.json_payload
                print(json_payload)
                if json_payload.type == MessageType.GetImageKrita:
                    get_image_krita_payload = cast(GetImageKritaJsonPayload, json_payload)
                    (_, byte_array) = decoded_message.payloads[0]
                    image = Image.open(io.BytesIO(byte_array))
                    filename_prefix = get_image_krita_payload.filename_prefix
                    full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_temp_directory())
                    file = f"{filename}_s.png"
                    image.save(os.path.join(full_output_folder, file), compress_level=1)
                    os.rename(os.path.join(full_output_folder, file), os.path.join(full_output_folder, f"{filename}_.png"))  # >:(
                elif json_payload.type == MessageType.DocumentSync:
                    document_sync_payload = cast(DocumentSyncJsonPayload, json_payload)
                    base_map = {key: val for key, val in ws_krita.KritaWsManager.instance().documents.items() if val[1] == sid}
                    for item in document_sync_payload.document_map:
                        base_map[f"{item[1]} ({item[0].split('-')[0]})"] = (item[0], sid)
                    ws_krita.KritaWsManager.instance().documents = base_map
                    PromptServer.instance.send_sync("cks_refresh", {})
                    ws_krita.KritaWsManager.instance().document_combo = list(ws_krita.KritaWsManager.instance().documents.keys())
                    nodes.GetImageKrita.update_return_types()

    finally:
        ws_krita.KritaWsManager.instance().sockets.pop(sid, None)
    return ws
