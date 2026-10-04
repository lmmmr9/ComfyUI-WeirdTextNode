import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

try:
    from aiohttp import web
except Exception:
    web = None

try:
    from server import PromptServer
except Exception:
    PromptServer = None

NODE_DIR = Path(__file__).resolve().parent
DB_NAME = "weird_prompt.db"
DB_PATH = NODE_DIR / DB_NAME
ROUTE = "/weird_prompt_sqlite/action"

EMPTY_CHOICE = "(暂无数据表)"

COLUMNS = ("prompt_name", "prompt_text", "prompt_lora", "prompt_trigger")
_IDENT_UNSAFE = re.compile(r"[^0-9A-Za-z_\u4e00-\u9fff]")
_IDENT_MAX = 64


def _normalize_table(name):
    """把用户输入的表名转成安全可用的标识符；非法返回空串。"""
    if isinstance(name, str):
        name = name.strip()
    if not name or len(name) > _IDENT_MAX:
        return ""
    if _IDENT_UNSAFE.search(name):
        return ""
    return name


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _list_tables():
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
    except sqlite3.Error as exc:
        print(f"[WeirdPromptSQLite] 读取表列表失败: {exc}")
        return []
    return [row["name"] for row in rows]


def _row_to_dict(row):
    data = {"ID": row["ID"]}
    for col in COLUMNS:
        data[col] = "" if row[col] is None else str(row[col])
    return data


def _values_from(payload):
    return tuple("" if payload.get(col) is None else str(payload.get(col)) for col in COLUMNS)


def _create_table(name):
    table = _normalize_table(name)
    if not table:
        return {"ok": False, "error": "表名无效（仅支持中英文、数字、下划线，且不超过 64 个字符）"}
    try:
        with _db() as conn:
            existed = _table_exists(conn, table)
            conn.execute(
                f'CREATE TABLE IF NOT EXISTS "{table}"(\n'
                "  ID INTEGER PRIMARY KEY,\n"
                "  prompt_name TEXT,\n"
                "  prompt_text TEXT,\n"
                "  prompt_lora TEXT,\n"
                "  prompt_trigger TEXT\n)"
            )
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"建表失败: {exc}"}
    return {
        "ok": True,
        "table": table,
        "existed": existed,
        "tables": _list_tables(),
    }


def _fetch_row(table, row_id):
    table = _normalize_table(table)
    if not table:
        return None, "无效的表名"
    try:
        with _db() as conn:
            if not _table_exists(conn, table):
                return None, f"表「{table}」不存在"
            row = conn.execute(
                f'SELECT ID, prompt_name, prompt_text, prompt_lora, prompt_trigger '
                f'FROM "{table}" WHERE ID = ?',
                (row_id,),
            ).fetchone()
    except sqlite3.Error as exc:
        return None, f"读取失败: {exc}"
    if row is None:
        return None, f"未找到 ID={row_id} 的记录"
    return _row_to_dict(row), None


def _count_rows(conn, table):
    return conn.execute(f'SELECT COUNT(*) AS n FROM "{table}"').fetchone()["n"]


def _insert_row(table, payload):
    table = _normalize_table(table)
    if not table:
        return {"ok": False, "error": "无效的表名"}
    values = _values_from(payload)
    try:
        with _db() as conn:
            if not _table_exists(conn, table):
                return {"ok": False, "error": f"表「{table}」不存在"}
            cur = conn.execute(
                f'INSERT INTO "{table}"(prompt_name, prompt_text, prompt_lora, prompt_trigger) '
                "VALUES (?, ?, ?, ?)",
                values,
            )
            row_id = cur.lastrowid
            count = _count_rows(conn, table)
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"新增失败: {exc}"}
    result = {"ok": True, "table": table, "id": row_id, "count": count}
    result.update(dict(zip(COLUMNS, values)))
    return result


def _update_row(table, row_id, payload):
    table = _normalize_table(table)
    if not table:
        return {"ok": False, "error": "无效的表名"}
    values = _values_from(payload)
    try:
        with _db() as conn:
            if not _table_exists(conn, table):
                return {"ok": False, "error": f"表「{table}」不存在"}
            cur = conn.execute(
                f'UPDATE "{table}" SET prompt_name=?, prompt_text=?, prompt_lora=?, prompt_trigger=? '
                "WHERE ID=?",
                values + (row_id,),
            )
            if cur.rowcount == 0:
                return {"ok": False, "error": f"未找到 ID={row_id} 的记录，无法更新"}
            count = _count_rows(conn, table)
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"更新失败: {exc}"}
    result = {"ok": True, "table": table, "id": row_id, "count": count}
    result.update(dict(zip(COLUMNS, values)))
    return result


def _delete_row(table, row_id):
    table = _normalize_table(table)
    if not table:
        return {"ok": False, "error": "无效的表名"}
    try:
        with _db() as conn:
            if not _table_exists(conn, table):
                return {"ok": False, "error": f"表「{table}」不存在"}
            cur = conn.execute(f'DELETE FROM "{table}" WHERE ID=?', (row_id,))
            if cur.rowcount == 0:
                return {"ok": False, "error": f"未找到 ID={row_id} 的记录，无法删除"}
            count = _count_rows(conn, table)
    except sqlite3.Error as exc:
        return {"ok": False, "error": f"删除失败: {exc}"}
    return {"ok": True, "table": table, "id": row_id, "count": count}


def _handle_action(payload):
    if not isinstance(payload, dict):
        return {"ok": False, "error": "无效的请求体"}

    action = payload.get("action")

    if action == "tables":
        return {"ok": True, "tables": _list_tables()}

    if action == "create":
        return _create_table(payload.get("name"))

    table = payload.get("table")
    if action == "get":
        row, error = _fetch_row(table, payload.get("row_id", 0))
        if error:
            return {"ok": False, "error": error}
        result = {"ok": True, "table": _normalize_table(table)}
        result.update(row)
        return result

    if action == "insert":
        return _insert_row(table, payload)

    if action == "update":
        if not payload.get("write_back"):
            return {"ok": False, "error": "回写关闭，更新未执行（如需修改请打开回写）"}
        return _update_row(table, payload.get("row_id", 0), payload)

    if action == "delete":
        if not payload.get("write_back"):
            return {"ok": False, "error": "回写关闭，删除未执行（如需删除请打开回写）"}
        return _delete_row(table, payload.get("row_id", 0))

    return {"ok": False, "error": f"未知操作: {action}"}


_ACTION_NAMES = {
    "tables": "列出数据表",
    "create": "新建数据表",
    "get": "读取记录",
    "insert": "新增记录",
    "update": "更新记录",
    "delete": "删除记录",
}


def _log_action(payload, result):
    """把一次操作的结果打印到 ComfyUI 控制台。"""
    payload = payload if isinstance(payload, dict) else {}
    action = payload.get("action")
    label = _ACTION_NAMES.get(action, str(action))

    if action == "create":
        detail = f"表={result.get('table') or payload.get('name')}"
    elif action == "tables":
        detail = ""
    else:
        detail = f"表={payload.get('table')}"
        if action in ("get", "insert", "update", "delete"):
            detail += f" ID={payload.get('row_id', 0)}"

    if result.get("ok"):
        extra = ""
        if action == "create":
            extra = "（已存在）" if result.get("existed") else "（新建）"
        elif action == "tables":
            extra = f" 共 {len(result.get('tables', []))} 张"
        elif action == "insert":
            extra = f" 新 ID={result.get('id')}"
        elif action == "update":
            extra = f" 共 {result.get('count')} 条"
        elif action == "delete":
            extra = f" 剩余 {result.get('count')} 条"
        print(f"[WeirdPromptSQLite] {label}: {detail}{extra}")
    else:
        where = f"{detail} -> " if detail else ""
        print(f"[WeirdPromptSQLite] {label}失败: {where}{result.get('error')}")


def _register_route():
    if web is None or PromptServer is None:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return

    @server.routes.post(ROUTE)
    async def weird_prompt_sqlite_action(request):
        try:
            payload = await request.json()
        except Exception:
            payload = None
        result = _handle_action(payload)
        _log_action(payload, result)
        return web.json_response(result, status=200 if result.get("ok") else 400)


class WeirdPromptSQLiteNode:
    @classmethod
    def INPUT_TYPES(cls):
        tables = _list_tables()
        names = tables or [EMPTY_CHOICE]
        return {
            "required": {
                "table": (names, {"default": names[0]}),
                "new_table": ("STRING", {"default": ""}),
                "row_id": ("INT", {"default": 0, "min": 0, "step": 1}),
                "prompt_name": ("STRING", {"multiline": True, "default": ""}),
                "prompt_text": ("STRING", {"multiline": True, "default": ""}),
                "prompt_lora": ("STRING", {"multiline": True, "default": ""}),
                "prompt_trigger": ("STRING", {"multiline": True, "default": ""}),
                "write_back": ("BOOLEAN", {"default": False, "label_on": "回写开", "label_off": "回写关"}),
            },
        }

    RETURN_TYPES = ("INT", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("id", "prompt_name", "prompt_text", "prompt_lora", "prompt_trigger")
    FUNCTION = "apply"
    OUTPUT_NODE = True
    CATEGORY = "text/utils"
    DESCRIPTION = (
        "对固定数据库 weird_prompt.db 中的自定义表做增删改查："
        "在 new_table 填入表名后点「新建表」创建（已存在则直接选中），table 下拉框选择要操作的表。"
        "row_id 为记录主键 ID，「读取」按 ID 把四个字段载入下方输入框；"
        "「新增」插入一条记录并返回新 ID。"
        "「回写」开关位于「新增」与「更新」之间，作为误操作保护："
        "开启时「更新」按 ID 写回四个字段、「删除」按 ID 删除记录；"
        "关闭时「更新」「删除」都不实际生效，仅提示回写关闭。"
        "输出 id 与四个字段 prompt_name、prompt_text、prompt_lora、prompt_trigger。"
    )

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        try:
            mtime = DB_PATH.stat().st_mtime_ns
        except OSError:
            mtime = 0
        return mtime

    def apply(
        self,
        table="",
        new_table="",
        row_id=0,
        prompt_name="",
        prompt_text="",
        prompt_lora="",
        prompt_trigger="",
        write_back=False,
    ):
        row, _error = _fetch_row(table, row_id)
        if row is None:
            print(f"[WeirdPromptSQLite] 节点执行: 表={table} ID={row_id} 无记录，输出空值")
            return {
                "ui": {col: [""] for col in COLUMNS},
                "result": (0, "", "", "", ""),
            }
        values = tuple(row[col] for col in COLUMNS)
        print(f"[WeirdPromptSQLite] 节点执行: 表={table} ID={row['ID']} 输出四个字段")
        return {
            "ui": {col: [row[col]] for col in COLUMNS},
            "result": (int(row["ID"]),) + values,
        }


_register_route()

NODE_CLASS_MAPPINGS = {
    "WeirdPromptSQLiteNode": WeirdPromptSQLiteNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WeirdPromptSQLiteNode": "Weird Prompt SQLite Node",
}
