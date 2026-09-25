import { app } from "../../scripts/app.js";

const NODE_CLASS = "WeirdTextNode";
const WIDGET_NAMES = ["text", "text_out"];
const SYNC_WIDGET = "sync";
const BUTTON_WIDGET = "sync_toggle";

function syncLabel(on) {
  return on ? "同步上框 → 下框：开" : "同步上框 → 下框：关";
}

function setWidgetValue(node, name, value) {
  const widget = node.widgets?.find((w) => w.name === name);
  if (!widget) return;
  widget.value = value;
  if (typeof widget.callback === "function") {
    try {
      widget.callback(value, app.canvas, node, [0, 0]);
    } catch (err) {
      console.debug("WeirdTextNode widget callback failed", err);
    }
  }
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

function readValue(message, name) {
  const raw = message?.[name];
  if (Array.isArray(raw) && raw.length) return raw[0];
  if (typeof raw === "string") return raw;
  return undefined;
}

function setupSyncButton(node) {
  if (node.__syncButtonReady) return;
  const widgets = node.widgets;
  if (!widgets) return;
  const syncWidget = widgets.find((w) => w.name === SYNC_WIDGET);
  const outWidget = widgets.find((w) => w.name === "text_out");
  if (!syncWidget || !outWidget) return;
  node.__syncButtonReady = true;

  const button = node.addWidget(
    "button",
    BUTTON_WIDGET,
    null,
    () => {
      syncWidget.value = !syncWidget.value;
      button.label = syncLabel(syncWidget.value);
      node.setDirtyCanvas?.(true, true);
    },
    { serialize: false, canvasOnly: true }
  );
  button.label = syncLabel(syncWidget.value);

  // hide the raw boolean widget, it is driven by the button
  syncWidget.computeSize = () => [0, -4];

  // place the button between the two text boxes
  const index = widgets.indexOf(button);
  widgets.splice(index, 1);
  widgets.splice(widgets.indexOf(outWidget), 0, button);

  node.setSize?.(node.computeSize?.());
}

app.registerExtension({
  name: "comfy.weirdTextNode",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      onNodeCreated?.apply(this, arguments);
      setupSyncButton(this);
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      onConfigure?.apply(this, arguments);
      const syncWidget = this.widgets?.find((w) => w.name === SYNC_WIDGET);
      const button = this.widgets?.find((w) => w.name === BUTTON_WIDGET);
      if (syncWidget && button) {
        button.label = syncLabel(syncWidget.value);
      }
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      for (const name of WIDGET_NAMES) {
        const value = readValue(message, name);
        if (value !== undefined) {
          setWidgetValue(this, name, value);
        }
      }
    };
  },
});
