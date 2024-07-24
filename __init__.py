from .comfy_sync import nodes, server

NODE_CLASS_MAPPINGS = {
    "CKS_SendImageKrita": nodes.SendImageKrita
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "CKS_SendImageKrita": "Send Image to Krita",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
