import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

function debounce(func, wait = 300) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

app.registerExtension({
    name: "comfy_sync.updated",
    async setup() {
        const debouncedCallback = debounce(async (event) => {
            await api.fetchApi("/comfy_sync/updated", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(event.detail)
            })
        }, 2000);

        api.addEventListener("graphChanged", debouncedCallback);
    },
});