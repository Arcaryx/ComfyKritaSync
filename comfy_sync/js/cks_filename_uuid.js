import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

app.registerExtension({
    name: "cks.filename_uuid",
    async setup() {

    },
    async nodeCreated(node) {
        if (node?.widgets.some(widget => widget.name === "cks_filename_uuid")) {
            console.log("HELLO")
        }
    }
});
