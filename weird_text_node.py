class WeirdTextNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "sync": ("BOOLEAN", {"default": True, "label_on": "同步开", "label_off": "同步关"}),
            },
            "optional": {
                "text_out": ("STRING", {"multiline": True, "default": ""}),
                "text_in": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "apply"
    OUTPUT_NODE = True
    CATEGORY = "text/utils"
    DESCRIPTION = (
        "上方文本框接收上游节点的文本/字符串（未连接时可手动输入）。"
        "开启同步时，每次运行把上方内容复制到下方文本框并输出；"
        "关闭同步时，下方文本框保留手动编辑的内容并作为输出。"
    )

    def apply(self, text="", sync=True, text_out="", text_in=None):
        value = text_in if text_in is not None else text
        if sync:
            return {"ui": {"text": [value], "text_out": [value]}, "result": (value,)}
        return {"ui": {"text": [value]}, "result": (text_out,)}


NODE_CLASS_MAPPINGS = {
    "WeirdTextNode": WeirdTextNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WeirdTextNode": "Weird Text Node",
}
