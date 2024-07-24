from PIL import Image
import numpy as np
from server import PromptServer, BinaryEventTypes  # type: ignore
from . import ws_krita


class SendImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"images": ("IMAGE",)}}

    RETURN_TYPES = ()
    FUNCTION = "send_images_krita"
    OUTPUT_NODE = True
    CATEGORY = "cks"

    def send_images_krita(self, images):
        results = []
        for tensor in images:
            array = 255.0 * tensor.cpu().numpy()
            image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))

            # Send to ComfyUI client (for preview)
            server = PromptServer.instance
            server.send_sync(
                BinaryEventTypes.UNENCODED_PREVIEW_IMAGE,
                ["PNG", image, None],
                server.client_id
            )

            # Send to Krita client
            manager = ws_krita.KritaWsManager.instance()
            manager.send_sync(
                BinaryEventTypes.UNENCODED_PREVIEW_IMAGE,
                ["PNG", image, None],
                # TODO: This needs to contain the Krita document to target
            )

            # Results needed for preview in ComfyUI client
            results.append(
                # Could put some kind of ID here, but for now just match them by index
                {"source": "websocket", "content-type": "image/png", "type": "output"}
            )
            return {"ui": {"images": results}}
