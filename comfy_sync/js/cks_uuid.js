import { app } from "../../../scripts/app.js";
import { ComfyWidgets } from "../../../scripts/widgets.js";

app.registerExtension({
    name: "cks.uuid",
    init() {
        const stringMethod = ComfyWidgets["STRING"]
        ComfyWidgets["STRING"] = function (node, inputName, inputData) {
            const res = stringMethod.apply(this, arguments);
                if(inputName === "cks_uuid"){
                    res.widget.type = "hidden";
                    res.widget.computeSize = () => [0, -4];
                    res.widget.beforeQueued = () => {
                        res.widget.value = crypto.randomUUID();
                    }
                }

            return res;
        }
    }
});
