# ComfyKritaSync
ComfyKritaSync enables the transfer of images between ComfyUI and Krita. This project is designed to be installed as both a ComfyUI custom node and a Krita plugin. It was inspired by [krita-ai-diffusion](https://github.com/Acly/krita-ai-diffusion), but with the desire to use custom workflows.

## Installation
1. Clone this repository directly into your `ComfyUI/custom_nodes` directory, or make use of [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) (install via git url).
2. From Krita, use **Tools ▸ Scripts ▸ Import Python Plugin from File...** and select the [zip file](https://github.com/Arcaryx/ComfyKritaSync/archive/refs/heads/main.zip), or just extract directly into the `.local/share/krita/pykrita/` directory.

## Usage
This project is designed to facilitate the transfer of images between ComfyUI and Krita.

<p float="left">
  <img src="/examples/workflow-1-comfy.png" width="400" />
  <img src="/examples/workflow-1-krita.png" width="400" />
</p>

In this example, we're changing the ring color of an Umbreon gen. `Select Krita Document` is used to specify the document once for the workflow. `Get Image from Krita` is used to retrieve the `Base` layer from Krita, while `Send Image to Krita` sends the final result back to Krita.

## Additional Notes
- So far this is only tested on Linux. It should work on Windows/Mac, but there could be issues.
- In Krita, you can use `Ctrl-Del` to remove individual images or `Ctrl-Shift-Del` to remove groups.
- Grouped layers can be specified with forward slashes (/), example: `Group/Result`.
- [ComfyUI_NetDist](https://github.com/city96/ComfyUI_NetDist) is supported. Place `Send Image to Krita` after batching image results if you desire a single group in Krita.
