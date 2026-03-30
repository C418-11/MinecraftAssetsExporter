import os
from pathlib import Path

APP_TITLE = "Minecraft 散列资源文件导出器"
WINDOW_GEOMETRY = "800x600"
DEFAULT_MINECRAFT_PATH = Path(os.environ.get("APPDATA", Path.home())) / ".minecraft"

# UI 颜色常量
BUTTON_SELECT_BG = "#4CAF50"
BUTTON_EXPORT_BG = "#2196F3"
BUTTON_FG = "white"
PATH_LABEL_FONT = ("Arial", 12)
PATH_LABEL_VALID_COLOR = "blue"
PATH_LABEL_INVALID_COLOR = "red"

# Treeview 颜色常量
COLOR_VALID = "black"
COLOR_PARTIAL = "orange"
COLOR_INVALID = "red"

# 文本常量
RESULT_WINDOW_TITLE = "{filename} 文件层级结构"
DEFAULT_PATH_TEXT = "未选择文件夹"

# 路径常量
ASSETS_INDEXES = Path("assets", "indexes")
ASSETS_OBJECTS = Path("assets", "objects")
INDEXES_FILE_SUFFIX = ".json"
INDEXES_PATH_TEMPLATE = f"{{ver_key}}{INDEXES_FILE_SUFFIX} → {{description}}"

# 布局常量
TREEVIEW_COLUMN = "fullpath"

# 版本索引描述缓存
INDEXES_CACHE_PATH = Path("./indexes.json")
