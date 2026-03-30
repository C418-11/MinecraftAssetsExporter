import hashlib
import os
from collections.abc import Sequence
from pathlib import Path
from tkinter import messagebox, Misc

import config as cfg
from data import FileInfo


def show_info(message: str, parent: Misc | None = None) -> None:
    messagebox.showinfo("提示", message=message, parent=parent)


def show_error(message: str, parent: Misc | None = None) -> None:
    messagebox.showerror("错误", message, parent=parent)


def show_warning(message: str, parent: Misc | None = None) -> None:
    messagebox.showwarning("警告", message, parent=parent)


def join_resource_path(dot_minecraft_path: Path, file_hash: str) -> Path:
    return dot_minecraft_path / cfg.ASSETS_OBJECTS / file_hash[:2] / file_hash


def check_object_validity(file_info: FileInfo, dot_minecraft_path: Path) -> bool:
    object_path = join_resource_path(dot_minecraft_path, file_info["hash"])
    if not object_path.is_file():
        return False
    if os.path.getsize(object_path) != file_info["size"]:
        return False
    try:
        with open(object_path, "rb") as f:
            file_hash = hashlib.sha1(f.read()).hexdigest()
    except IOError:
        return False
    return file_hash == file_info["hash"]


def sort_by_another[T](seq: Sequence[T], order_seq: Sequence[T]) -> Sequence[T]:
    order_map = {key: idx for idx, key in enumerate(order_seq)}
    return sorted(seq, key=lambda k: order_map.get(k, len(order_seq)))
