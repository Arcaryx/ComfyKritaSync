import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

app.registerExtension({
    name: "cks.refresh",
    async setup() {
        api.addEventListener("cks_refresh", async () => {
            await app.refreshComboInNodes()
        })
    },
    refreshComboInNodes(defs) {
        for (const cksNodeType of ["CKS_SelectKritaDocument", "CKS_GetImageKrita", "CKS_SendImageKrita"]) {
            const cksNodeDef = defs[cksNodeType];

            let documentOutputIndex = null;
            for(let i = 0; i < cksNodeDef.output_name.length; i++){
                if(cksNodeDef.output_name[i] === "document"){
                    documentOutputIndex = i;
                    break;
                }
            }

            const cksGraphNodes = app.graph.findNodesByType(cksNodeType)

            for(const cksGraphNode of cksGraphNodes){
                if(cksGraphNode.widgets) {
                    for (const widget of cksGraphNode.widgets) {
                        if (widget.name === "document") {
                            const updatedDocuments = cksNodeDef.input.required.document[0];
                            widget.options.values = updatedDocuments
                            // >:(
                            cksGraphNode.constructor.nodeData.input.required.document[0] = updatedDocuments
                        }
                    }
                }

                if(documentOutputIndex !== null){
                    // >:(
                    cksGraphNode.constructor.nodeData.output[documentOutputIndex] = cksNodeDef.output[documentOutputIndex];
                }
            }
        }
    }
});
