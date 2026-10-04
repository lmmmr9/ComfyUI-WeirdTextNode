import os

try:
    from aiohttp import web
except Exception:
    web = None

try:
    from server import PromptServer
except Exception:
    PromptServer = None

import folder_paths
from nodes import LoadImage

ROOT_FOLDER = "."


def _is_visible(name):
    return not name.startswith('.')


def _register_route():
    if web is None or PromptServer is None:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return

    @server.routes.get("/weird/files/output")
    async def get_output_files_recursive(request):
        directory = folder_paths.get_output_directory()

        entries = []
        for root, dirs, filenames in os.walk(directory):
            dirs[:] = [d for d in dirs if _is_visible(d)]
            for filename in filenames:
                if not _is_visible(filename):
                    continue
                path = os.path.join(root, filename)
                relative_path = os.path.relpath(path, directory).replace(os.sep, "/")
                entries.append((relative_path, os.path.getmtime(path)))

        entries.sort(key=lambda entry: -entry[1])
        return web.json_response([f"{relative_path} [output]" for relative_path, _ in entries], status=200)

    @server.routes.get("/weird/folders/output")
    async def get_output_folders(request):
        directory = folder_paths.get_output_directory()

        folders = []
        for root, dirs, _ in os.walk(directory):
            dirs[:] = [d for d in dirs if _is_visible(d)]
            if root == directory:
                continue
            folders.append(os.path.relpath(root, directory).replace(os.sep, "/"))

        return web.json_response([ROOT_FOLDER] + sorted(folders), status=200)


class weird_LoadImageOutput(LoadImage):
    SEARCH_ALIASES = ["output image", "previous generation", "recursive output image"]

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "folder": ("COMBO", {
                    "default": ROOT_FOLDER,
                    "remote": {
                        "route": "/weird/folders/output",
                        "refresh_button": True,
                    },
                }),
                "image": ("COMBO", {
                    "image_upload": True,
                    "image_folder": "output",
                    "remote": {
                        "route": "/weird/files/output",
                        "refresh_button": True,
                        "control_after_refresh": "first",
                    },
                }),
            }
        }

    DESCRIPTION = "Load an image from the output folder, including subfolders. The folder box switches between the output root (.) and its subfolders; picking the root lists the whole output tree, picking a subfolder only lists the images under it (recursively). When the refresh button is clicked, the node will update the list and automatically select the first image."
    EXPERIMENTAL = True
    FUNCTION = "load_image"

    def load_image(self, image, folder=None):
        return super().load_image(image)

    @classmethod
    def IS_CHANGED(s, image, folder=None):
        return super().IS_CHANGED(image)

    @classmethod
    def VALIDATE_INPUTS(s, image, folder=None):
        if not folder_paths.exists_annotated_filepath(image):
            return "Invalid image file: {}".format(image)

        return True


_register_route()

NODE_CLASS_MAPPINGS = {
    "weird_LoadImageOutput": weird_LoadImageOutput,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "weird_LoadImageOutput": "Load Image (from Outputs, Recursive)",
}
