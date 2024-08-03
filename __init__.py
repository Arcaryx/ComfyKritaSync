from .comfy_sync import nodes, server

NODE_CLASS_MAPPINGS = {
    "CKS_SendImageKrita": nodes.SendImageKrita,
    "CKS_GetImageKrita": nodes.GetImageKrita
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "CKS_SendImageKrita": "Send Image to Krita",
    "CKS_GetImageKrita": "Get Image from Krita"
}
WEB_DIRECTORY = "./comfy_sync/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
