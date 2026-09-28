import json
import shutil

from .weird_prompt_node import (
    EMPTY_CHOICE,
    PromptServer,
    _find_file,
    _list_prompt_files,
    _to_text,
    load_json_file,
    web,
)


def _append_entry(path, key, value):
    raw, error = load_json_file(path)
    if error:
        return {"ok": False, "error": error}

    if isinstance(raw, dict):
        payload = dict(raw)
        new_key = key.strip() if isinstance(key, str) else ""
        if not new_key:
            return {"ok": False, "error": "key 不能为空"}
        if new_key in payload:
            return {
                "ok": False,
                "error": f"键「{new_key}」已存在（序号 {list(payload).index(new_key)}），未添加",
            }
        payload[new_key] = _to_text(value)
        added_key = new_key
    elif isinstance(raw, list):
        payload = list(raw)
        payload.append(_to_text(value))
        added_key = str(len(payload) - 1)
    else:
        return {"ok": False, "error": f"{path.name} 结构不支持，需为对象或数组"}

    index = len(payload) - 1

    # 写入前先备份原文件，备份失败则不写入
    backup = path.with_name(path.name + ".bak")
    try:
        shutil.copy2(path, backup)
    except OSError as exc:
        return {"ok": False, "error": f"备份 {backup.name} 失败，未写入: {exc}"}

    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)
            f.write("\n")
        tmp.replace(path)
    except OSError as exc:
        return {"ok": False, "error": f"写入 {path.name} 失败: {exc}"}

    return {
        "ok": True,
        "file": path.name,
        "index": index,
        "count": len(payload),
        "key": added_key,
        "backup": backup.name,
    }


def _register_route():
    if web is None or PromptServer is None:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return

    @server.routes.post("/weird_prompt/add")
    async def weird_prompt_add(request):
        try:
            payload = await request.json()
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return web.json_response({"ok": False, "error": "无效的请求体"}, status=400)

        path = _find_file(payload.get("file"))
        if path is None:
            return web.json_response(
                {"ok": False, "error": f"未找到 {payload.get('file')}"}, status=404
            )

        result = _append_entry(path, payload.get("key"), payload.get("value"))
        return web.json_response(result, status=200 if result.get("ok") else 400)


class WeirdPromptAddNode:
    @classmethod
    def INPUT_TYPES(cls):
        files = _list_prompt_files()
        names = [p.name for p in files] or [EMPTY_CHOICE]
        return {
            "required": {
                "file": (names, {"default": names[0]}),
                "key": ("STRING", {"default": ""}),
                "value": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "apply"
    OUTPUT_NODE = True
    CATEGORY = "text/utils"
    DESCRIPTION = (
        "向选定的 weird_prompt*.json 末尾添加一条提示词：key 为一行文本框（键名），value 为多行文本框（提示词）。"
        "点击「添加」按钮立即写入文件，成功后按钮短暂显示新增的序号，失败原因打印在浏览器控制台。"
        "键名已存在时不会覆盖，会提示已存在的序号。"
        "key 与 value 之间的「清除」按钮只清空这两个输入框，不修改文件。"
        "每次添加前会先把原文件备份为同目录下的 <文件名>.bak（覆盖上一次备份），备份失败则不写入。"
    )

    @classmethod
    def VALIDATE_INPUTS(cls, file="", key="", value=""):
        return True

    def apply(self, file="", key="", value=""):
        return {"ui": {}, "result": ()}


_register_route()

NODE_CLASS_MAPPINGS = {
    "WeirdPromptAddNode": WeirdPromptAddNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WeirdPromptAddNode": "Weird Prompt Add Node",
}
