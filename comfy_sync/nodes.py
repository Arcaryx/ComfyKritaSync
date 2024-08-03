import time
import uuid
import torch
import os
import json
import folder_paths  # type: ignore
import numpy as np
from PIL import Image, ImageFile
from PIL.PngImagePlugin import PngInfo
from server import PromptServer, BinaryEventTypes  # type: ignore
from . import ws_krita
from comfy.cli_args import args  # type: ignore

from .ws_krita import KritaWsManager
from ..krita_sync.cks_common.CksBinaryMessage import GetImageKritaJsonPayload, SendImageKritaJsonPayload


class SendImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "document": (KritaWsManager.instance().document_combo,),
            "images": ("IMAGE",)
        },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "send_image_krita"
    OUTPUT_NODE = True
    CATEGORY = "cks"

    def send_image_krita(self, document, images, prompt=None, extra_pnginfo=None):
        filename_prefix = "CKS_temp_" + ''.join(uuid.uuid4().hex)
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_temp_directory(), images[0].shape[1], images[0].shape[0])
        results = []
        result_images = []
        for tensor in images:
            array = 255.0 * tensor.cpu().numpy()
            image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))
            result_images.append(image)

            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for x in extra_pnginfo:
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))
            file = f"{filename}_{counter:05}_.png"
            image.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=1)

            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": "temp"
            })
            counter += 1

        # Send to Krita client
        manager = ws_krita.KritaWsManager.instance()

        # TODO: This needs to contain the Krita document to target
        json_payload = SendImageKritaJsonPayload(krita_document=KritaWsManager.instance().documents[document][0], run_uuid="TODO")
        manager.send_sync(json_payload, result_images, KritaWsManager.instance().documents[document][1])

        return {
            "ui": {
                "images": results
            }
        }


class GetImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "document": (KritaWsManager.instance().document_combo,),
            "layer": ("STRING", {"default": "Background"}, {"multiline": False})
        }}

    RETURN_TYPES = "IMAGE", KritaWsManager.instance().document_combo

    @classmethod
    def update_return_types(cls):
        cls.RETURN_TYPES = "IMAGE", KritaWsManager.instance().document_combo

    RETURN_NAMES = ("image", "document")
    FUNCTION = "get_image_krita"
    OUTPUT_NODE = False
    CATEGORY = "cks"

    def get_image_krita(self, document, layer):
        results = []

        filename_prefix = "CKS_temp_" + ''.join(uuid.uuid4().hex)
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_temp_directory())
        file = f"{filename}_.png"

        json_payload = GetImageKritaJsonPayload(krita_document=KritaWsManager.instance().documents[document][0], krita_layer=layer, filename_prefix=filename_prefix)

        manager = ws_krita.KritaWsManager.instance()
        manager.send_sync(json_payload, None, KritaWsManager.instance().documents[document][1])

        start_time = time.time()
        filepath = os.path.join(full_output_folder, file)
        timeout = 10
        while not os.path.exists(filepath):
            if time.time() - start_time > timeout:
                raise FileNotFoundError(f'{filepath} not found after {timeout} seconds')
            time.sleep(0.1)

        image = Image.open(filepath)
        np_image = np.array(image).astype(np.float32) / 255.0
        torch_image = torch.from_numpy(np_image)[None,]

        # Results needed for preview in ComfyUI client
        results.append({
            "filename": file,
            "subfolder": subfolder,
            "type": "temp"
        })
        return {
            "ui": {
                "images": results
            },
            "result": (torch_image, document)
        }
