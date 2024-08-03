import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

app.registerExtension({
    name: "cks.refresh",
    async setup() {
        api.addEventListener("cks_refresh", async () => {
            await app.refreshComboInNodes()
        })
    }
});
