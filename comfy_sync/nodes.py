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
from ..krita_sync.cks_common.CksBinaryMessage import MessageType


class SendImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
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

    def send_image_krita(self, images, prompt=None, extra_pnginfo=None):
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
        # TODO: Should send all images once instead of sending images one at a time?
        manager = ws_krita.KritaWsManager.instance()
        manager.send_sync(
            MessageType.SendImageKrita,
            {
                "KritaDocument": "image.png",  # TODO: This needs to contain the Krita document to target
                "RunUuid": "TODO"
            },
            result_images
        )

        return {"ui": {"images": results}}


class GetImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        # TODO: Get list of documents from Krita clients, this will need to be refreshed when new documents are opened
        #documents = ["image1.png", "image2.png", "image3.png"]
        #return {"required": {
        #    "document": (documents,),
        #    "layer": ("STRING", {"default": "example layer"}, {"multiline": False})
        #}}
        return {"required": {
           "document": ("STRING", {"default": "Unnamed"}, {"multiline": False}),
           "layer": ("STRING", {"default": "example layer"}, {"multiline": False})
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "get_image_krita"
    OUTPUT_NODE = False
    CATEGORY = "cks"

    def get_image_krita(self, document, layer):
        results = []

        filename_prefix = "CKS_temp_" + ''.join(uuid.uuid4().hex)
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_temp_directory())
        file = f"{filename}_.png"

        manager = ws_krita.KritaWsManager.instance()
        manager.send_sync(
            MessageType.GetImageKrita,
            {
                "KritaDocument": document,  # TODO: This needs to contain the Krita document to target
                "KritaLayer": layer,
                "FileNamePrefix": filename_prefix
            }
        )

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
        return torch_image, {"ui": {"images": results}}
