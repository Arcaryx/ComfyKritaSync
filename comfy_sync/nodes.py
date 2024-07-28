from PIL import Image
import numpy as np
import torch
from server import PromptServer, BinaryEventTypes  # type: ignore
from . import ws_krita


class SendImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "images": ("IMAGE",)
        }}

    RETURN_TYPES = ()
    FUNCTION = "send_image_krita"
    OUTPUT_NODE = True
    CATEGORY = "cks"

    def send_image_krita(self, images):
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
                {"testkey": "testvalue"},
                image,
                # TODO: This needs to contain the Krita document to target
            )

            # Results needed for preview in ComfyUI client
            results.append(
                # Could put some kind of ID here, but for now just match them by index
                {"source": "websocket", "content-type": "image/png", "type": "output"}
            )
            return {"ui": {"images": results}}


class GetImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        # TODO: Get list of documents from Krita clients, this will need to be refreshed when new documents are opened
        documents = ["image1.png", "image2.png", "image3.png"]
        return {"required": {
            "document": (documents,),
            "layer": ("STRING", {"default": "example layer"}, {"multiline": False})
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "get_image_krita"
    OUTPUT_NODE = False
    CATEGORY = "cks"

    def get_image_krita(self, document, layer):
        results = []

        # TODO: Get image from Krita websocket
        image = Image.new("RGB", (1024, 1024), (255, 255, 255))
        np_image = np.array(image).astype(np.float32) / 255.0
        torch_image = torch.from_numpy(np_image)[None,]

        # Send to ComfyUI client (for preview)
        server = PromptServer.instance
        server.send_sync(
            BinaryEventTypes.UNENCODED_PREVIEW_IMAGE,
            ["PNG", image, None],
            server.client_id
        )

        # Results needed for preview in ComfyUI client
        results.append(
            # Could put some kind of ID here, but for now just match them by index
            {"source": "websocket", "content-type": "image/png", "type": "output"}
        )
        return torch_image, {"ui": {"images": results}}
