import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "WeirdPromptAddNode";
const ADD_BUTTON = "add_now";
const CLEAR_BUTTON = "clear_fields";
const CLEAR_LABEL = "清除";
const DEFAULT_LABEL = "添加";
const LABEL_RESET_MS = 1800;

function getWidget(node, name) {
  return node.widgets?.find((w) => w.name === name);
}

function widgetValue(node, name) {
  return getWidget(node, name)?.value;
}

const labelTimers = new WeakMap();

function flashLabel(node, button, text) {
  button.label = text;
  clearTimeout(labelTimers.get(button));
  labelTimers.set(
    button,
    setTimeout(() => {
      button.label = DEFAULT_LABEL;
      labelTimers.delete(button);
      node.setDirtyCanvas?.(true, true);
    }, LABEL_RESET_MS)
  );
  node.setDirtyCanvas?.(true, true);
}

async function pushAdd(node, button) {
  const payload = {
    file: widgetValue(node, "file"),
    key: widgetValue(node, "key"),
    value: widgetValue(node, "value"),
  };
  try {
    const res = await api.fetchApi("/weird_prompt/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.ok) {
      console.error("[WeirdPromptAddNode] 添加失败:", data?.error ?? res.statusText);
      flashLabel(node, button, "添加失败");
      return;
    }
    flashLabel(node, button, `已添加 #${data.index}`);
  } catch (err) {
    console.error("[WeirdPromptAddNode] 添加失败:", err);
    flashLabel(node, button, "添加失败");
  }
}

function clearWidgetValue(node, name) {
  const widget = getWidget(node, name);
  if (!widget) return;
  widget.value = "";
  if (typeof widget.callback === "function") {
    try {
      widget.callback("", app.canvas, node, [0, 0]);
    } catch (err) {
      console.debug("WeirdPromptAddNode widget callback failed", err);
    }
  }
}

function setupButtons(node) {
  if (node.__addButtonsReady) return;
  if (!node.widgets) return;
  node.__addButtonsReady = true;

  const clear = node.addWidget(
    "button",
    CLEAR_BUTTON,
    null,
    () => {
      clearWidgetValue(node, "key");
      clearWidgetValue(node, "value");
      node.setDirtyCanvas?.(true, true);
    },
    { serialize: false, canvasOnly: true }
  );
  clear.label = CLEAR_LABEL;

  const button = node.addWidget(
    "button",
    ADD_BUTTON,
    null,
    () => {
      pushAdd(node, button);
    },
    { serialize: false, canvasOnly: true }
  );
  button.label = DEFAULT_LABEL;

  // 把「清除」放到 key 与 value 之间
  const valueWidget = getWidget(node, "value");
  if (valueWidget) {
    const index = node.widgets.indexOf(valueWidget);
    node.widgets.splice(node.widgets.indexOf(clear), 1);
    node.widgets.splice(index, 0, clear);
  }

  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "comfy.weirdPromptAddNode",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      onNodeCreated?.apply(this, arguments);
      try {
        setupButtons(this);
      } catch (err) {
        console.error("[WeirdPromptAddNode] 按钮初始化失败:", err);
      }
    };
  },
});
