import { app } from "../../scripts/app.js";

const NODE_CLASS = "weird_LoadImageOutput";
const FOLDER_WIDGET = "folder";
const IMAGE_WIDGET = "image";
const ROOT_FOLDER = ".";
const OUTPUT_SUFFIX = " [output]";

function relativePath(value) {
  if (typeof value !== "string") return "";
  return value.endsWith(OUTPUT_SUFFIX)
    ? value.slice(0, -OUTPUT_SUFFIX.length)
    : value;
}

function normalizeFolder(value) {
  const text = value == null ? "" : String(value);
  if (text === "" || text === "/" || text === ROOT_FOLDER) return "";
  return text.replace(/\/+$/, "");
}

function filterValues(values, folder) {
  if (!Array.isArray(values)) return [];
  const prefix = normalizeFolder(folder);
  if (!prefix) return values.slice();
  const wanted = `${prefix}/`;
  return values.filter((value) => relativePath(value).startsWith(wanted));
}

function applyFolderSelection(node, folderWidget, imageWidget) {
  const values = filterValues(
    node.__readAllImages?.() ?? [],
    folderWidget.value
  );
  if (!values.length || values.includes(imageWidget.value)) return;

  imageWidget.value = values[0];
  imageWidget.callback?.(imageWidget.value, app.canvas, node, [0, 0]);
  node.setDirtyCanvas?.(true, true);
}

function renameRefreshButtons(node) {
  const targets = [
    { combo: FOLDER_WIDGET, label: "refresh folder" },
    { combo: IMAGE_WIDGET, label: "refresh image" },
  ];
  for (const { combo, label } of targets) {
    const start = node.widgets.findIndex((w) => w.name === combo);
    if (start === -1) continue;
    for (let i = start + 1; i < node.widgets.length; i++) {
      const widget = node.widgets[i];
      if (widget.type !== "button") continue;
      if (!/^refresh(#\d+)?$/.test(widget.name ?? "")) break;
      widget.name = label;
      widget.label = label;
      break;
    }
  }
}

function installFolderFilter(node) {
  const folderWidget = node.widgets?.find((w) => w.name === FOLDER_WIDGET);
  const imageWidget = node.widgets?.find((w) => w.name === IMAGE_WIDGET);
  if (!folderWidget || !imageWidget) return;

  const options = imageWidget.options;
  const descriptor = Object.getOwnPropertyDescriptor(options, "values");
  if (typeof descriptor?.get === "function" && descriptor.get.__weirdFolderFilter) {
    return;
  }

  let fallback = Array.isArray(descriptor?.value) ? descriptor.value : [];
  node.__readAllImages = () => {
    if (typeof descriptor?.get === "function") {
      const values = descriptor.get.call(options);
      return Array.isArray(values) ? values : [];
    }
    return fallback;
  };

  const getter = () => {
    const values = filterValues(node.__readAllImages(), folderWidget.value);
    if (values.length && !values.includes(imageWidget.value) && !node.__selectQueued) {
      node.__selectQueued = true;
      setTimeout(() => {
        node.__selectQueued = false;
        applyFolderSelection(node, folderWidget, imageWidget);
      }, 0);
    }
    return values;
  };
  getter.__weirdFolderFilter = true;

  Object.defineProperty(options, "values", {
    configurable: true,
    enumerable: true,
    get: getter,
    set: (values) => {
      if (typeof descriptor?.set === "function") {
        descriptor.set.call(options, values);
      } else {
        fallback = Array.isArray(values) ? values : fallback;
      }
    },
  });

  if (!node.__folderCallbackWired) {
    node.__folderCallbackWired = true;
    const previousCallback = folderWidget.callback;
    folderWidget.callback = function (value, ...rest) {
      if (typeof previousCallback === "function") {
        previousCallback.call(this, value, ...rest);
      }
      applyFolderSelection(node, folderWidget, imageWidget);
    };
  }
}

app.registerExtension({
  name: "comfy.weirdLoadImageOutput",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      onNodeCreated?.apply(this, arguments);
      try {
        renameRefreshButtons(this);
      } catch (err) {
        console.error("[weird_LoadImageOutput] 刷新按钮重命名失败:", err);
      }
      try {
        installFolderFilter(this);
      } catch (err) {
        console.error("[weird_LoadImageOutput] 文件夹筛选初始化失败:", err);
      }
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      onConfigure?.apply(this, arguments);
      try {
        renameRefreshButtons(this);
      } catch (err) {
        console.error("[weird_LoadImageOutput] 刷新按钮重命名失败:", err);
      }
      try {
        installFolderFilter(this);
      } catch (err) {
        console.error("[weird_LoadImageOutput] 文件夹筛选恢复失败:", err);
      }
    };
  },
});
