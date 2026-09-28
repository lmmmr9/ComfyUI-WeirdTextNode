import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "WeirdPromptNode";
const WIDGET_NAMES = ["key", "value"];
const WRITE_BACK_WIDGET = "write_back";
const UPDATE_BUTTON = "update_now";

function getWidget(node, name) {
  return node.widgets?.find((w) => w.name === name);
}

function widgetValue(node, name) {
  return getWidget(node, name)?.value;
}

function readValue(message, name) {
  const raw = message?.[name];
  if (Array.isArray(raw) && raw.length) return raw[0];
  if (typeof raw === "string") return raw;
  return undefined;
}

function setWidgetValue(node, name, value) {
  const widget = getWidget(node, name);
  if (!widget) return;
  widget.value = value;
  if (typeof widget.callback === "function") {
    try {
      widget.callback(value, app.canvas, node, [0, 0]);
    } catch (err) {
      console.debug("WeirdPromptNode widget callback failed", err);
    }
  }
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

async function pushUpdate(node) {
  const payload = {
    file: widgetValue(node, "file"),
    index: widgetValue(node, "index"),
    key: widgetValue(node, "key"),
    value: widgetValue(node, "value"),
    write_back: !!widgetValue(node, WRITE_BACK_WIDGET),
  };
  try {
    const res = await api.fetchApi("/weird_prompt/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.ok) {
      console.error("[WeirdPromptNode] 更新失败:", data?.error ?? res.statusText);
      return;
    }
    if (typeof data.key === "string") setWidgetValue(node, "key", data.key);
    if (typeof data.value === "string") setWidgetValue(node, "value", data.value);
  } catch (err) {
    console.error("[WeirdPromptNode] 更新失败:", err);
  }
}

function setupButtons(node) {
  if (node.__promptButtonsReady) return;
  if (!node.widgets) return;
  node.__promptButtonsReady = true;

  const update = node.addWidget(
    "button",
    UPDATE_BUTTON,
    null,
    () => {
      pushUpdate(node);
    },
    { serialize: false, canvasOnly: true }
  );
  update.label = "更新";

  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "comfy.weirdPromptNode",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      onNodeCreated?.apply(this, arguments);
      try {
        setupButtons(this);
      } catch (err) {
        console.error("[WeirdPromptNode] 按钮初始化失败:", err);
      }
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, [message]);
      for (const name of WIDGET_NAMES) {
        const value = readValue(message, name);
        if (value !== undefined) setWidgetValue(this, name, value);
      }
      this.setDirtyCanvas?.(true, true);
    };
  },
});
