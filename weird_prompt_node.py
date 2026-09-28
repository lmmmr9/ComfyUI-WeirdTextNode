import json
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
FILE_PREFIX = "weird_prompt"
FILE_SUFFIX = ".json"
EMPTY_CHOICE = "(未找到 weird_prompt*.json)"

_ENTRY_CACHE = {}


def _search_dirs():
    dirs = []
    try:
        import folder_paths

        user_dir = folder_paths.get_user_directory()
        if user_dir:
            dirs.append(Path(user_dir))
    except Exception:
        pass
    dirs.append(NODE_DIR.parents[1] / "user")
    dirs.append(NODE_DIR)

    seen, result = set(), []
    for d in dirs:
        try:
            real = d.resolve()
        except Exception:
            continue
        if real not in seen and real.is_dir():
            seen.add(real)
            result.append(real)
    return result


def _list_prompt_files():
    files, seen = [], set()
    for d in _search_dirs():
        for p in sorted(d.glob(f"{FILE_PREFIX}*{FILE_SUFFIX}")):
            if p.is_file() and p.name not in seen:
                seen.add(p.name)
                files.append(p)
    return files


def _find_file(name):
    for p in _list_prompt_files():
        if p.name == name:
            return p
    return None


def _resolve_file(name):
    files = _list_prompt_files()
    for p in files:
        if p.name == name:
            return p
    if files:
        print(f"[WeirdPromptNode] 未找到 {name}，改用 {files[0].name}")
        return files[0]
    return None


def _to_text(v):
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False)


def load_json_file(path):
    """读取 json 文件；空白文件视为空对象，返回 (data, error)。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        return None, f"读取 {path.name} 失败: {exc}"
    if not text.strip():
        return {}, None
    try:
        return json.loads(text), None
    except Exception as exc:
        return None, f"{path.name} 不是有效的 json: {exc}"


def _load_entries(path):
    if path is None:
        return []
    try:
        stat = path.stat()
    except OSError:
        return []
    cache_key = (str(path), stat.st_mtime_ns, stat.st_size)
    if cache_key in _ENTRY_CACHE:
        return _ENTRY_CACHE[cache_key]

    data, error = load_json_file(path)
    if error:
        print(f"[WeirdPromptNode] {error}")
        data = None

    entries = []
    if isinstance(data, dict):
        entries = [(str(k), _to_text(v)) for k, v in data.items()]
    elif isinstance(data, list):
        entries = [(str(i), _to_text(v)) for i, v in enumerate(data)]

    if len(_ENTRY_CACHE) > 32:
        _ENTRY_CACHE.clear()
    _ENTRY_CACHE[cache_key] = entries
    return entries


def _write_entry(path, index, key, value, write_back):
    raw, error = load_json_file(path)
    if error:
        return {"ok": False, "error": error}

    if isinstance(raw, dict):
        items = list(raw.items())
        as_dict = True
    elif isinstance(raw, list):
        items = [(str(i), v) for i, v in enumerate(raw)]
        as_dict = False
    else:
        return {"ok": False, "error": f"{path.name} 结构不支持，需为对象或数组"}

    if not items:
        return {"ok": False, "error": f"{path.name} 中没有数据"}

    try:
        i = int(index)
    except (TypeError, ValueError):
        i = 0
    i = max(0, min(i, len(items) - 1))

    if write_back:
        new_key = key if isinstance(key, str) and key else items[i][0]
        new_value = items[i][1] if value is None else _to_text(value)
        if as_dict:
            if new_key != items[i][0] and any(k == new_key for k, _ in items):
                return {"ok": False, "error": f"键「{new_key}」已存在于其他序号，未写入"}
            items[i] = (new_key, new_value)
            payload = {k: v for k, v in items}
        else:
            items[i] = (str(i), new_value)
            payload = [v for _, v in items]

        tmp = path.with_name(path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=4)
                f.write("\n")
            tmp.replace(path)
        except OSError as exc:
            return {"ok": False, "error": f"写入 {path.name} 失败: {exc}"}

    k, v = items[i]
    return {
        "ok": True,
        "file": path.name,
        "index": i,
        "key": k,
        "value": _to_text(v),
        "count": len(items),
        "written": bool(write_back),
    }


def _register_route():
    if web is None or PromptServer is None:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return

    @server.routes.post("/weird_prompt/update")
    async def weird_prompt_update(request):
        try:
            payload = await request.json()
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            return web.json_response({"ok": False, "error": "无效的请求体"}, status=400)

        path = _resolve_file(payload.get("file"))
        if path is None:
            return web.json_response({"ok": False, "error": f"未找到 {payload.get('file')}"}, status=404)

        result = _write_entry(
            path,
            payload.get("index", 0),
            payload.get("key"),
            payload.get("value"),
            bool(payload.get("write_back")),
        )
        return web.json_response(result, status=200 if result.get("ok") else 400)


class WeirdPromptNode:
    @classmethod
    def INPUT_TYPES(cls):
        files = _list_prompt_files()
        names = [p.name for p in files] or [EMPTY_CHOICE]
        counts = [len(_load_entries(p)) for p in files] or [0]
        return {
            "required": {
                "file": (names, {"default": names[0]}),
                "index": ("INT", {"default": 0, "min": 0, "max": max(0, max(counts) - 1), "step": 1}),
                "key": ("STRING", {"default": ""}),
                "value": ("STRING", {"multiline": True, "default": ""}),
                "write_back": ("BOOLEAN", {"default": False, "label_on": "回写开", "label_off": "回写关"}),
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("prompt", "length")
    FUNCTION = "apply"
    OUTPUT_NODE = True
    CATEGORY = "text/utils"
    DESCRIPTION = (
        "从 ComfyUI 的 user 目录（及本节点目录）扫描 weird_prompt*.json，可用 file 切换文件、用 index 切换序号。"
        "key 显示框显示当前序号对应的键，value 显示框显示对应的提示词，提示词从 prompt 输出。"
        "length 输出当前文件的条目总数（有效序号范围为 0 到 length-1）。"
        "json 中键为序号或名称、值为提示词；直接运行即可，无需外部输入。"
        "write_back 控制是否允许写入：开启后点击「更新」会把修改后的 key/value 写回 json，"
        "关闭时「更新」只按当前文件重新读取显示。"
    )

    @classmethod
    def VALIDATE_INPUTS(cls, file="", index=0, key="", value="", write_back=False):
        return True

    @classmethod
    def IS_CHANGED(cls, file="", index=0, key="", value="", write_back=False):
        path = _resolve_file(file)
        mtime = path.stat().st_mtime_ns if path else 0
        return f"{path.name if path else ''}:{index}:{mtime}"

    def apply(self, file, index=0, key="", value="", write_back=False):
        entries = _load_entries(_resolve_file(file))
        if not entries:
            return {"ui": {"key": [""], "value": [""]}, "result": ("", 0)}
        try:
            i = int(index)
        except (TypeError, ValueError):
            i = 0
        i = max(0, min(i, len(entries) - 1))
        k, v = entries[i]
        return {"ui": {"key": [k], "value": [v]}, "result": (v, len(entries))}


_register_route()

NODE_CLASS_MAPPINGS = {
    "WeirdPromptNode": WeirdPromptNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WeirdPromptNode": "Weird Prompt Node",
}
