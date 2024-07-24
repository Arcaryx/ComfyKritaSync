import uuid
from server import PromptServer  # type: ignore
from aiohttp import web, WSMsgType
from . import ws_krita


@PromptServer.instance.routes.get('/krita-sync-ws')
async def krita_websocket_handler(request):
    ws = web.WebSocketResponse()
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
        await ws_krita.KritaWsManager.instance().send("status", {"status": "CONNECTED-HELLO-ARCA", 'sid': sid}, sid)

        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                print('ws connection.py closed with exception %s' % ws.exception())

    finally:
        ws_krita.KritaWsManager.instance().sockets.pop(sid, None)
    return ws
