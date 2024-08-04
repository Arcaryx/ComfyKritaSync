import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";


const DOCUMENT_WIDGET_INDEX = 0;
const documentHistoryByNodeId = {};

const trackDocumentHistoryForNode = function(nodeId, document) {
    let documentHistory = documentHistoryByNodeId[nodeId];

    if(!documentHistory){
        documentHistory = {latest: undefined, before: undefined}
        documentHistoryByNodeId[nodeId] = documentHistory;
    }

    if(documentHistory.latest !== document){
        documentHistory.before = documentHistory.latest;
        documentHistory.latest = document;
    }

    console.debug(`CKS_DEBUG: Document history for nodeId ${nodeId} -> ${JSON.stringify(documentHistory)}`);
}

app.registerExtension({
    name: "cks.refresh",
    async setup() {
        api.addEventListener("cks_refresh", async () => {
            await app.refreshComboInNodes()
        })
    },
    async nodeCreated(node) {
        if (node?.comfyClass === "CKS_GetImageKrita" || node?.comfyClass === "CKS_SendImageKrita") {
            const original_onMouseDown = node.onMouseDown;
            node.onMouseDown = function( e, pos, canvas ) {
                trackDocumentHistoryForNode(node.id, node.widgets[0].value);
                return original_onMouseDown?.apply(this, arguments);
            }
        }
    },
    refreshComboInNodes(defs) {
        for(const cksNodeType of ["CKS_GetImageKrita", "CKS_SendImageKrita"]){
            const cksNodeDef = defs[cksNodeType];
            const cksNodeDocumentInputDef = cksNodeDef.input.required.document[0];
            const ckeNodeDocumentInputDefCount = cksNodeDocumentInputDef.length;

            const cksGraphNodes = app.graph.findNodesByType(cksNodeType)

            cksGraphNodes.forEach(cksGraphNode => {
                const nodeId = cksGraphNode.id;
                let documentHistory = documentHistoryByNodeId[nodeId];
                const currentNodeDocumentWidget = cksGraphNode.widgets[DOCUMENT_WIDGET_INDEX];

                // Can be "converted-widget" if converted to an input
                if(currentNodeDocumentWidget.type === "combo"){
                    // When we do have a document...
                    if(ckeNodeDocumentInputDefCount > 0){
                        // ...but we didn't have a document in `latest` and have one in `before`, set current value to `before`
                        if(!documentHistory?.latest && documentHistory?.before){
                            console.debug("CKS_DEBUG: We have values again after they were previously null, setting to last non-null value")
                            cksGraphNode.widgets[DOCUMENT_WIDGET_INDEX].value = cksGraphNode.widgets_values[DOCUMENT_WIDGET_INDEX] = documentHistory.before;
                        }

                        // Also do a check to set the value properly if the current document no longer exists in the node def
                        if(!cksNodeDocumentInputDef.includes(currentNodeDocumentWidget.value)) {
                            console.debug("CKS_DEBUG: The current combo values don't have the value saved on the widget, trying to update")
                            cksGraphNode.widgets[DOCUMENT_WIDGET_INDEX].value = cksGraphNode.widgets_values[DOCUMENT_WIDGET_INDEX] = cksNodeDocumentInputDef[DOCUMENT_WIDGET_INDEX];
                        }
                    }

                    // Always log the latest document, even if the current state is that there is no document
                    trackDocumentHistoryForNode(nodeId, cksGraphNode.widgets[DOCUMENT_WIDGET_INDEX].value)
                }else if(documentHistory){
                    console.debug("CKS_DEBUG: Removing document history for non-combo widget")
                    delete documentHistoryByNodeId[nodeId];
                }
            });
        }
    }
});
