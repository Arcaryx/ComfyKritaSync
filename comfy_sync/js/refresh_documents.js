import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const DOCUMENT_WIDGET_INDEX = 0;
const documentHistoryByNodeId = {};
const cksNodeTypes = ["CKS_GetImageKrita", "CKS_SendImageKrita"]

const saveHistory = async function() {
    for (const cksNodeType of cksNodeTypes) {
        const cksGraphNodes = app.graph.findNodesByType(cksNodeType);

        cksGraphNodes.forEach(cksGraphNode => {
            const nodeId = cksGraphNode.id;
            const currentNodeDocumentWidget = cksGraphNode.widgets[DOCUMENT_WIDGET_INDEX];

            console.debug(`CKS_DEBUG: Saving history for node ${nodeId}: ${currentNodeDocumentWidget.value}`)
            documentHistoryByNodeId[nodeId] = currentNodeDocumentWidget.value;
        });
    }
}

const restoreHistory = async function() {
    for (const cksNodeType of cksNodeTypes) {
        const cksGraphNodes = app.graph.findNodesByType(cksNodeType);

        cksGraphNodes.forEach(cksGraphNode => {
            const nodeId = cksGraphNode.id;
            const currentNodeDocumentWidget = cksGraphNode.widgets[DOCUMENT_WIDGET_INDEX];
            const cksNodeDocumentOptions = currentNodeDocumentWidget.options.values;
            console.debug(`CKS_DEBUG: Document Options: ${JSON.stringify(cksNodeDocumentOptions)}`)

            if (documentHistoryByNodeId.hasOwnProperty(nodeId)) {
                if (cksNodeDocumentOptions.includes(documentHistoryByNodeId[nodeId])) {
                    console.debug(`CKS_DEBUG: Restoring history for node ${nodeId}: ${currentNodeDocumentWidget.value} -> ${documentHistoryByNodeId[nodeId]}`)
                    currentNodeDocumentWidget.value = documentHistoryByNodeId[nodeId];
                    cksGraphNode.widgets_values[DOCUMENT_WIDGET_INDEX] = documentHistoryByNodeId[nodeId];
                }
            }
        });
    }
    for (let prop in documentHistoryByNodeId) {
        if (documentHistoryByNodeId.hasOwnProperty(prop)) {
            delete documentHistoryByNodeId[prop];
        }
    }
}

app.registerExtension({
    name: "cks.refresh",
    async setup() {
        api.addEventListener("cks_refresh", async () => {
            // Save history here [Untitled 1] [Undefined so save nothing]
            await saveHistory();

            // Call refresh [Untitled 1 -> Undefined] [Undefined -> Document 1]
            await app.refreshComboInNodes()

            // Check if history needs to be restored [No available nodes] [Document 1 -> Untitled 1]
            await restoreHistory();
        })
    }
});
