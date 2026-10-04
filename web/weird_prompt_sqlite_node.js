import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "WeirdPromptSQLiteNode";
const ROUTE = "/weird_prompt_sqlite/action";
const EMPTY_CHOICE = "(暂无数据表)";
const VALUE_WIDGETS = ["prompt_name", "prompt_text", "prompt_lora", "prompt_trigger"];

function getWidget(node, name) {
  return node.widgets?.find((w) => w.name === name);
}

function widgetValue(node, name) {
  return getWidget(node, name)?.value;
}

function setWidgetValue(node, name, value) {
  const widget = getWidget(node, name);
  if (!widget || value === undefined || value === null) return;
  widget.value = value;
  if (typeof widget.callback === "function") {
    try {
      widget.callback(value, app.canvas, node, [0, 0]);
    } catch (err) {
      console.debug("[WeirdPromptSQLite] widget callback failed", err);
    }
  }
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

async function call(payload) {
  try {
    const res = await api.fetchApi(ROUTE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.ok) {
      console.error("[WeirdPromptSQLite] 操作失败:", data?.error ?? res.statusText);
      return null;
    }
    return data;
  } catch (err) {
    console.error("[WeirdPromptSQLite] 操作失败:", err);
    return null;
  }
}

function applyTables(node, tables) {
  const widget = getWidget(node, "table");
  if (!widget || !Array.isArray(tables)) return;
  const values = tables.length ? tables : [EMPTY_CHOICE];
  if (!widget.options) widget.options = {};
  widget.options.values = values;
  if (!values.includes(widget.value)) {
    widget.value = values[0];
    if (typeof widget.callback === "function") {
      try {
        widget.callback(widget.value, app.canvas, node, [0, 0]);
      } catch (err) {
        console.debug("[WeirdPromptSQLite] table callback failed", err);
      }
    }
  }
  node.setDirtyCanvas?.(true, true);
}

function currentTable(node) {
  const table = widgetValue(node, "table");
  if (!table || table === EMPTY_CHOICE) {
    console.error("[WeirdPromptSQLite] 请先新建或选择一个数据表");
    return "";
  }
  return table;
}

function rowPayload(node, action) {
  const payload = {
    action,
    table: currentTable(node),
    row_id: widgetValue(node, "row_id"),
    write_back: !!widgetValue(node, "write_back"),
  };
  for (const name of VALUE_WIDGETS) payload[name] = widgetValue(node, name);
  return payload;
}

async function refreshTables(node) {
  const data = await call({ action: "tables" });
  if (data) applyTables(node, data.tables);
}

async function createTable(node) {
  const name = widgetValue(node, "new_table");
  const data = await call({ action: "create", name });
  if (!data) return;
  applyTables(node, data.tables);
  setWidgetValue(node, "table", data.table);
}

async function loadRow(node) {
  if (!currentTable(node)) return;
  const data = await call(rowPayload(node, "get"));
  if (!data) return;
  setWidgetValue(node, "row_id", data.ID);
  for (const name of VALUE_WIDGETS) setWidgetValue(node, name, data[name]);
}

async function insertRow(node) {
  if (!currentTable(node)) return;
  const data = await call(rowPayload(node, "insert"));
  if (!data) return;
  setWidgetValue(node, "row_id", data.id);
}

async function updateRow(node) {
  if (!currentTable(node)) return;
  const data = await call(rowPayload(node, "update"));
  if (!data) return;
  const newId = data.ID ?? data.id;
  if (newId !== undefined) setWidgetValue(node, "row_id", newId);
  for (const name of VALUE_WIDGETS) setWidgetValue(node, name, data[name]);
}

async function deleteRow(node) {
  if (!currentTable(node)) return;
  const data = await call({
    action: "delete",
    table: currentTable(node),
    row_id: widgetValue(node, "row_id"),
    write_back: !!widgetValue(node, "write_back"),
  });
  if (data) setWidgetValue(node, "row_id", 0);
}

function addButton(node, name, label, handler) {
  const button = node.addWidget("button", name, null, handler, {
    serialize: false,
    canvasOnly: true,
  });
  button.label = label;
  return button;
}

function setupButtons(node) {
  if (node.__sqliteButtonsReady) return;
  if (!node.widgets) return;
  node.__sqliteButtonsReady = true;

  const refresh = addButton(node, "refresh_tables", "刷新表", () => refreshTables(node));
  const create = addButton(node, "create_table", "新建表", () => createTable(node));
  const load = addButton(node, "load_row", "读取", () => loadRow(node));
  const insert = addButton(node, "insert_row", "新增", () => insertRow(node));
  const update = addButton(node, "update_row", "更新", () => updateRow(node));
  const remove = addButton(node, "delete_row", "删除", () => deleteRow(node));

  // 把「刷新表 / 新建表」放到 new_table 输入框后面
  const newTableWidget = getWidget(node, "new_table");
  if (newTableWidget) {
    const index = node.widgets.indexOf(newTableWidget) + 1;
    node.widgets.splice(node.widgets.indexOf(refresh), 1);
    node.widgets.splice(node.widgets.indexOf(create), 1);
    node.widgets.splice(index, 0, refresh, create);
  }

  // 把「回写」开关放到「新增」与「更新」之间，作为误操作保护开关
  const writeBack = getWidget(node, "write_back");
  if (writeBack) {
    const writeBackIndex = node.widgets.indexOf(writeBack);
    if (writeBackIndex !== -1) {
      node.widgets.splice(writeBackIndex, 1);
      const insertIndex = node.widgets.indexOf(insert);
      node.widgets.splice(insertIndex + 1, 0, writeBack);
    }
  }

  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: "comfy.weirdPromptSQLiteNode",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      onNodeCreated?.apply(this, arguments);
      try {
        setupButtons(this);
      } catch (err) {
        console.error("[WeirdPromptSQLite] 按钮初始化失败:", err);
      }
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      for (const name of VALUE_WIDGETS) {
        const raw = message?.[name];
        const value = Array.isArray(raw) && raw.length ? raw[0] : undefined;
        if (value !== undefined) setWidgetValue(this, name, value);
      }
      this.setDirtyCanvas?.(true, true);
    };
  },
});
