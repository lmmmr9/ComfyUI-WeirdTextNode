class WeirdTextNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "up_text": ("STRING", {"multiline": True, "default": ""}),
                "sync": ("BOOLEAN", {"default": True, "label_on": "同步开", "label_off": "同步关"}),
            },
            "optional": {
                "low_text": ("STRING", {"multiline": True, "default": ""}),
                "up_text_in": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("up_text_out", "low_text_out")
    FUNCTION = "apply"
    OUTPUT_NODE = True
    CATEGORY = "text/utils"
    DESCRIPTION = (
        "上方文本框接收上游节点的文本/字符串（未连接时可手动输入），输入端口为 up_text_in。"
        "开启同步时，每次运行把上方内容复制到下方文本框；"
        "关闭同步时，下方文本框保留手动编辑的内容。"
        "上框内容从 up_text_out 输出，下框内容从 low_text_out 输出。"
    )

    def apply(self, up_text="", sync=True, low_text="", up_text_in=None):
        value = up_text_in if up_text_in is not None else up_text
        if sync:
            return {"ui": {"up_text": [value], "low_text": [value]}, "result": (value, value)}
        return {"ui": {"up_text": [value]}, "result": (value, low_text)}


NODE_CLASS_MAPPINGS = {
    "WeirdTextNode": WeirdTextNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "WeirdTextNode": "Weird Text Node",
}
