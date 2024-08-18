import time
import uuid
import torch
import os
import json
import folder_paths  # type: ignore
import numpy as np
import node_helpers  # type: ignore
from PIL import Image, ImageFile, ImageSequence, ImageOps
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
            "layer": ("STRING", {"default": "Generated"}),
            "images": ("IMAGE",)
        },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = (KritaWsManager.instance().document_combo,)
    RETURN_NAMES = ("document",)
    FUNCTION = "send_image_krita"
    OUTPUT_NODE = True
    CATEGORY = "cks"

    @classmethod
    def update_return_types(cls):
        cls.RETURN_TYPES = (KritaWsManager.instance().document_combo,)

    def send_image_krita(self, document, layer, images, prompt=None, extra_pnginfo=None):
        if document == "Missing Document":
            raise Exception("Missing Document")

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

        if document in KritaWsManager.instance().documents:
            json_payload = SendImageKritaJsonPayload(
                krita_document=KritaWsManager.instance().documents[document][0],
                krita_layer=layer,
                run_uuid=PromptServer.instance.last_prompt_id
            )
            manager.send_sync(json_payload, result_images, KritaWsManager.instance().documents[document][1])
        else:
            print("SendImageKrita skipped because no matching document id.")

        return {
            "ui": {
                "images": results
            },
            "result": (document,)
        }


class GetImageKrita:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "document": (KritaWsManager.instance().document_combo,),
            "layer": ("STRING", {"default": "Background"}),
            "cks_uuid": ("STRING", {"default": ""})
        }}

    RETURN_TYPES = "IMAGE", "MASK", KritaWsManager.instance().document_combo

    @classmethod
    def update_return_types(cls):
        cls.RETURN_TYPES = "IMAGE", "MASK", KritaWsManager.instance().document_combo

    RETURN_NAMES = ("image", "mask", "document")
    FUNCTION = "get_image_krita"
    OUTPUT_NODE = False
    CATEGORY = "cks"

    def get_image_krita(self, document, layer, cks_uuid):
        if document == "Missing Document":
            raise Exception("Missing Document")

        results = []

        filename_prefix = "CKS_temp_" + ''.join(cks_uuid)
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_temp_directory())
        file = f"{filename}_.png"

        if document in KritaWsManager.instance().documents:
            json_payload = GetImageKritaJsonPayload(krita_document=KritaWsManager.instance().documents[document][0], krita_layer=layer, filename_prefix=filename_prefix)

            manager = ws_krita.KritaWsManager.instance()
            manager.send_sync(json_payload, None, KritaWsManager.instance().documents[document][1])
        else:
            print("GetImageKrita request skipped because no matching document id.")

        start_time = time.time()
        filepath = os.path.join(full_output_folder, file)
        timeout = 10
        while not os.path.exists(filepath):
            if time.time() - start_time > timeout:
                raise FileNotFoundError(f'{filepath} not found after {timeout} seconds')
            time.sleep(0.1)

        # Below is from ComfyUI LoadImage node
        img = node_helpers.pillow(Image.open, filepath)

        output_images = []
        output_masks = []
        w, h = None, None

        excluded_formats = ['MPO']

        for i in ImageSequence.Iterator(img):
            i = node_helpers.pillow(ImageOps.exif_transpose, i)
            if i.mode == 'I':
                i = i.point(lambda i: i * (1 / 255))
            image = i.convert("RGB")

            if len(output_images) == 0:
                w = image.size[0]
                h = image.size[1]

            if image.size[0] != w or image.size[1] != h:
                continue

            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            output_images.append(image)
            output_masks.append(mask.unsqueeze(0))

        if len(output_images) > 1 and img.format not in excluded_formats:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

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
            "result": (output_image, output_mask, document)
        }
