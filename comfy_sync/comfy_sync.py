from server import PromptServer   # type: ignore
from aiohttp import web


@PromptServer.instance.routes.post("/comfy_sync/updated")
async def workflow_updated(request):
    json_data = await request.json()
    print(json_data)
    return web.Response(status=200)
