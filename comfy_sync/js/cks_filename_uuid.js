import { app } from "../../../scripts/app.js";
import { ComfyWidgets } from "../../../scripts/widgets.js";

app.registerExtension({
    name: "cks.filename_uuid",
    init() {
        const stringMethod = ComfyWidgets["STRING"]
        ComfyWidgets["STRING"] = function (node, inputName, inputData) {
            const res = stringMethod.apply(this, arguments);
                if(inputName === "cks_filename_uuid"){
                    res.widget.type = "hidden";
                    res.widget.computeSize = () => [0, -4];
                }

            return res;
        }
    },
});
