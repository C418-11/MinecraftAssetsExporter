import json
import shutil
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog
from tkinter import ttk
from typing import Literal
from typing import cast

import config as cfg
from data import FileInfo, NodeInfo, NodeStatus, TreeNode
from indexes import get_cached_indexes, get_indexes
from utils import show_error, show_warning, show_info, join_resource_path, check_object_validity, sort_by_another


class MinecraftAssetsExporterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(cfg.APP_TITLE)
        self.root.geometry(cfg.WINDOW_GEOMETRY)
        self.last_selected_path: Path | None = None
        self.ver_keys = []
        self.select_version: str | None = None
        self.process_tree_thread: threading.Thread | None = None
        self.processor_running = False
        self.processor_lock = threading.Lock()
        self.export_thread: threading.Thread | None = None
        self.export_running = False

        # 初始化UI组件
        self._create_widgets()
        self._setup_bindings()
        # 自动检测默认目录
        self._auto_select_default_folder()

    def _auto_select_default_folder(self) -> None:
        """自动选择默认目录（如果有效）"""
        if cfg.DEFAULT_MINECRAFT_PATH.exists() and self._validate_assets_structure(cfg.DEFAULT_MINECRAFT_PATH):
            self.last_selected_path = cfg.DEFAULT_MINECRAFT_PATH
            self._update_path_display(cfg.DEFAULT_MINECRAFT_PATH)
            self._process_selected_folder(cfg.DEFAULT_MINECRAFT_PATH)

    def _create_widgets(self) -> None:
        """创建所有UI组件"""
        self._create_action_buttons()
        self._create_path_label()
        self._create_listbox()

    def _create_action_buttons(self) -> None:
        """创建操作按钮"""
        self.btn_select = tk.Button(
            self.root,
            text="选择 .minecraft 文件夹",
            command=self._select_folder,
            padx=10, pady=5,
            bg=cfg.BUTTON_SELECT_BG, fg=cfg.BUTTON_FG
        )
        self.btn_select.grid(row=0, column=0, padx=10, pady=10, sticky="nw")

        self.btn_export = tk.Button(
            self.root,
            text="导出选中版本",
            command=self._export_selected,
            padx=10, pady=5,
            bg=cfg.BUTTON_EXPORT_BG, fg=cfg.BUTTON_FG
        )
        self.btn_export.grid(row=0, column=0, padx=10, pady=10, sticky="ne")

    def _create_path_label(self) -> None:
        """创建路径显示标签"""
        self.lbl_path = tk.Label(self.root, text=cfg.DEFAULT_PATH_TEXT)
        self.lbl_path.grid(row=1, column=0, padx=10, pady=10, sticky="nw")
        self.lbl_path.config(font=cfg.PATH_LABEL_FONT, fg=cfg.PATH_LABEL_VALID_COLOR)

    def _create_listbox(self) -> None:
        """创建列表框组件"""
        frame = tk.Frame(self.root)
        frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        self.listbox = tk.Listbox(frame, width=100, height=20)
        self.listbox.pack(side=cast(Literal["left"], tk.LEFT), fill=cast(Literal["both"], tk.BOTH))

        # 配置网格自适应
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def _setup_bindings(self) -> None:
        """设置事件绑定"""
        self.listbox.bind("<Double-Button-1>", lambda e: self._export_selected())

    def _select_folder(self) -> None:
        """处理文件夹选择"""
        initial_dir = self.last_selected_path or cfg.DEFAULT_MINECRAFT_PATH
        folder_path = filedialog.askdirectory(
            title=cfg.APP_TITLE,
            initialdir=initial_dir,
            mustexist=True
        )

        if folder_path:
            folder_path = Path(folder_path)
            self.last_selected_path = folder_path
            self._update_path_display(folder_path)
            self._process_selected_folder(folder_path)

    def _update_path_display(self, path: Path) -> None:
        """更新路径显示状态"""
        self.lbl_path.config(text=str(path))
        self.root.update_idletasks()

    def _process_selected_folder(self, folder_path: Path) -> None:
        """处理选中的文件夹"""
        if not self._validate_assets_structure(folder_path):
            self._cleanup_version_indexes()
            show_error("所选文件夹缺少 assets/indexes 或 assets/objects 目录！")
            return

        self._load_version_indexes(folder_path)

    def _validate_assets_structure(self, folder_path: Path) -> bool:
        """验证assets目录结构"""
        indexes_dir = folder_path / cfg.ASSETS_INDEXES
        objects_dir = folder_path / cfg.ASSETS_OBJECTS
        valid = indexes_dir.is_dir() and objects_dir.is_dir()

        self.lbl_path.config(fg=cfg.PATH_LABEL_VALID_COLOR if valid else cfg.PATH_LABEL_INVALID_COLOR)
        return valid

    def _cleanup_version_indexes(self) -> None:
        """清理版本索引"""
        self.ver_keys = []
        self.listbox.delete(0, tk.END)

    def _display_version_indexes(self, versions: list[str], indexes: dict[str, str]) -> None:
        """显示版本索引"""
        self._cleanup_version_indexes()

        for ver_key in sort_by_another(versions, list(indexes.keys())):
            description = indexes.get(ver_key, "无法获取到有效的版本描述")
            display_text = cfg.INDEXES_PATH_TEMPLATE.format(ver_key=ver_key, description=description)
            self.listbox.insert(tk.END, display_text)
            self.ver_keys.append(ver_key)

    def _load_version_indexes(self, folder_path: Path) -> None:
        """加载版本索引到列表框"""
        indexes_dir = folder_path / cfg.ASSETS_INDEXES
        versions = [f.stem for f in indexes_dir.glob(f"*{cfg.INDEXES_FILE_SUFFIX}")]

        self._display_version_indexes(versions, get_cached_indexes())

        threading.Thread(
            target=self._async_update_version_indexes,
            args=(versions,),
            daemon=True
        ).start()

    def _async_update_version_indexes(self, versions: list[str]) -> None:
        """异步更新版本索引描述"""
        data = get_indexes()
        if not data:
            return
        self._display_version_indexes(versions, data)

    def _export_selected(self) -> None:
        """处理导出操作"""
        if not (selected := self.listbox.curselection()):
            show_warning("请先选择一个要导出的项目！")
            return

        selected_index = selected[0]
        self.select_version = self.ver_keys[selected_index]
        source_path = self.last_selected_path / cfg.ASSETS_INDEXES / f"{self.select_version}{cfg.INDEXES_FILE_SUFFIX}"

        if not source_path.exists():
            show_error("原始文件不存在！")
            return
        if hasattr(self, "result_window") and self.result_window.winfo_exists():
            show_warning("请先关闭之前的导出窗口！")
            self.result_window.lift()
            self.result_window.focus_set()
            return
        with self.processor_lock:
            if self.processor_running or (self.process_tree_thread and self.process_tree_thread.is_alive()):
                show_warning("请等待之前的导出操作完成！")
                return
            # 创建进度窗口
            self.result_window = tk.Toplevel(self.root)
            self.result_window.title("处理中")
            self.result_window.geometry("600x400")
            self.result_window.protocol("WM_DELETE_WINDOW", self._on_result_window_close)

            # 添加进度条
            self.progress_frame = ttk.Frame(self.result_window)
            self.progress_frame.pack(pady=20)

            self.progress_label = ttk.Label(self.progress_frame, text="正在初始化...")
            self.progress_label.pack()

            self.progress = ttk.Progressbar(self.progress_frame, length=400)
            self.progress.pack(pady=10)

            self.root.update()

            # 异步处理文件树
            self.process_tree_thread = threading.Thread(
                target=self._async_display_file_tree,
                args=(source_path,),
                daemon=True
            )
            self.process_tree_thread.start()
            self.processor_running = True

    def _on_result_window_close(self) -> None:
        self.processor_running = False
        if self.process_tree_thread.is_alive():
            # noinspection PyTypeChecker
            self.root.after(100, self._on_result_window_close)
        else:
            self.result_window.destroy()

    def _async_display_file_tree(self, source_path: str) -> None:
        """异步处理文件树数据"""
        try:
            with open(source_path, encoding="utf-8") as f:
                self.version_data = json.load(f)
                total_files = len(self.version_data["objects"])
                self.root.after(0, self._update_progress_config, total_files)

                self._process_tree_data(self.version_data["objects"], self.last_selected_path)
                # noinspection PyTypeChecker
                self.root.after(0, self._build_treeview_ui)
        except Exception as e:
            traceback.print_exc()
            self.root.after(0, show_error, f"处理文件失败: {str(e)}", self.root)
        finally:
            if self.processor_running:  # 所在的窗口都要destroy了还管progress干什么
                # noinspection PyTypeChecker
                self.root.after(0, self.progress_frame.destroy)

    def _update_progress_config(self, total: int) -> None:
        """更新进度条配置"""
        self.progress["maximum"] = total
        self.progress_label.config(text="正在验证文件...")

    def _process_tree_data(self, objects_data: dict[str, FileInfo], dot_minecraft_path: Path) -> None:
        """预处理所有节点数据"""
        node_info: dict[str, NodeInfo] = {}
        leaf_nodes: list[str] = []
        processed_count = 0

        # 处理叶子节点
        for path, info in objects_data.items():
            if not self.processor_running:
                return
            is_valid = check_object_validity(info, dot_minecraft_path)
            parts = path.split("/")
            parent = ""
            for i, part in enumerate(parts):
                current_node = f"{parent}/{part}" if parent else part
                if current_node not in node_info:
                    node_info[current_node] = NodeInfo(children=set(), status=None)
                if parent:
                    node_info[parent]["children"].add(current_node)
                parent = current_node

                if i == len(parts) - 1:
                    node_info[current_node]["status"] = NodeStatus.VALID if is_valid else NodeStatus.INVALID
                    leaf_nodes.append(current_node)

            # 更新进度
            processed_count += 1
            self.root.after(0, self._update_progress, processed_count)

        # 计算父节点状态
        for node in node_info.keys():
            if node_info[node]["status"] is None:
                self._calculate_node_status(node, node_info)

        # 生成节点列表
        nodes: dict[str, TreeNode] = {}
        for path in node_info:
            parts = path.split("/")
            parent_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
            nodes[path] = TreeNode(
                parent_path=parent_path,
                name=parts[-1],
                path=path,
                status=node_info[path]["status"]
            )
        self.tree_nodes = nodes

    def _update_progress(self, value: int) -> None:
        """更新进度条"""
        self.progress["value"] = value
        self.progress_label.config(
            text=f"已处理 {value}/{int(self.progress['maximum'])} 个文件"
        )

    def _calculate_node_status(
            self,
            node: str,
            node_info: dict[str, NodeInfo],
    ) -> NodeStatus:
        """递归计算节点状态"""
        if node_info[node]["status"] is not None:
            return node_info[node]["status"]

        statuses: list[NodeStatus] = []
        for child in node_info[node]["children"]:
            statuses.append(self._calculate_node_status(child, node_info))

        # 判断节点状态
        all_invalid = all(s == NodeStatus.INVALID for s in statuses)
        any_issue = any(s in (NodeStatus.PARTIAL, NodeStatus.INVALID) for s in statuses)

        if all_invalid:
            node_info[node]["status"] = NodeStatus.INVALID
        elif any_issue:
            node_info[node]["status"] = NodeStatus.PARTIAL
        else:
            node_info[node]["status"] = NodeStatus.VALID

        return node_info[node]["status"]

    def _build_treeview_ui(self) -> None:
        """在结果窗口中构建Treeview界面"""
        # 确保窗口存在
        if not (self.processor_running and hasattr(self, "result_window") and self.result_window.winfo_exists()):
            return

        self.result_window.title(
            cfg.RESULT_WINDOW_TITLE.format(filename=f"{self.select_version}{cfg.INDEXES_FILE_SUFFIX}"))

        # 导出按钮
        self.export_tree_btn = ttk.Button(
            self.result_window,
            text="导出选中项",
            command=self._export_tree_selected
        )
        self.export_tree_btn.pack(pady=5)

        # Treeview组件初始化
        tree_frame = ttk.Frame(self.result_window)
        self.tree = ttk.Treeview(tree_frame, columns=cfg.TREEVIEW_COLUMN, show="tree")
        vsb = ttk.Scrollbar(tree_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        # 配置样式
        self.tree.tag_configure(NodeStatus.VALID, foreground=cfg.COLOR_VALID)
        self.tree.tag_configure(NodeStatus.PARTIAL, foreground=cfg.COLOR_PARTIAL)
        self.tree.tag_configure(NodeStatus.INVALID, foreground=cfg.COLOR_INVALID)

        # 布局
        tree_frame.pack(fill="both", expand=True)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # 配置网格权重
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # 创建节点
        node_map = {"": ""}  # 根节点映射
        for node in self.tree_nodes.values():
            parent_id = node_map.get(node.parent_path, "")
            node_id = self.tree.insert(
                parent=parent_id,
                index="end",
                text=node.name,
                values=[node.path],
                tags=(node.status,)
            )
            node_map[node.path] = node_id

    def _export_tree_selected(self):
        """处理文件树导出的多选操作"""
        selected_items = self.tree.selection()
        if not selected_items:
            show_warning("请先在文件树中选择要导出的项目！", parent=self.result_window)
            return

        # 选择输出目录
        export_dir = filedialog.askdirectory(title="选择导出目录", parent=self.result_window)
        if not export_dir:
            return
        export_dir = Path(export_dir)

        # 收集所有需要导出的文件路径
        export_resources: list[str] = []
        for item_id in selected_items:
            resource_name = self.tree.item(item_id, "values")[0]
            export_resources.append(resource_name)

        # 启动导出线程
        self.export_thread = threading.Thread(
            target=self._export_resources,
            args=(export_resources, export_dir),
            daemon=True
        )
        self.export_running = True
        self.export_thread.start()

    def _export_resources(self, paths: list[str], export_dir: Path):
        """导出选中的资源文件到指定目录"""
        if not self.export_running:
            show_warning("请等待之前的导出操作完成！", parent=self.result_window)
            return
        try:
            # 收集所有需要导出的资源路径
            export_paths = set()
            for selected_path in paths:
                for resource_path in self.version_data["objects"]:
                    # 匹配精确路径或子路径
                    if resource_path == selected_path or resource_path.startswith(selected_path + "/"):
                        export_paths.add(resource_path)

            total_files = len(export_paths)
            if total_files == 0:
                self.root.after(0, show_warning, "没有找到可导出的文件！", self.result_window)
                return

            # 创建导出进度窗口
            self.export_progress_window = tk.Toplevel(self.result_window)
            self.export_progress_window.geometry("500x115")
            self.export_progress_window.title("导出进度")
            self.export_progress_window.protocol("WM_DELETE_WINDOW", self._on_export_window_close)

            progress_frame = ttk.Frame(self.export_progress_window)
            progress_frame.pack(pady=20)

            self.export_progress_label = ttk.Label(progress_frame, text="正在初始化导出...")
            self.export_progress_label.pack()
            self.export_progress_filename_label = ttk.Label(progress_frame)
            self.export_progress_filename_label.pack()

            self.export_progress = ttk.Progressbar(progress_frame, length=400, maximum=total_files)
            self.export_progress.pack(pady=10)
            self.root.update()

            # 开始导出文件
            success_count = 0
            skip_count = 0
            fail_count = 0
            for idx, resource_path in enumerate(export_paths, 1):
                if not (self.processor_running and self.export_running):  # 用户中断
                    break

                # 更新进度
                self._update_export_progress(idx, total_files, resource_path)

                # 获取文件状态
                file_status = self.tree_nodes[resource_path].status
                if file_status == NodeStatus.INVALID:
                    skip_count += 1
                    continue

                # 构建源路径和目标路径
                file_hash = self.version_data["objects"][resource_path]["hash"]
                src_path = join_resource_path(self.last_selected_path, file_hash)
                dest_path = export_dir / resource_path

                try:
                    # 创建目标目录并复制文件
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest_path)
                    success_count += 1
                except Exception as e:
                    print(f"导出失败 {resource_path}: {str(e)}")
                    fail_count += 1

            # 关闭进度窗口
            self.export_progress_window.destroy()

            # 显示结果
            result_msg = [
                f"{"导出完成！" if self.export_running and self.processor_running else "导出终止！"}"
                f"成功 {success_count}/{total_files - skip_count} 个文件"
            ]
            if skip_count:
                result_msg.append(f"跳过 {skip_count} 个文件")
            if fail_count:
                result_msg.append(f"失败 {fail_count} 个文件")
            show_info("\n".join(result_msg), parent=self.result_window)
        except Exception as e:
            traceback.print_exc()
            show_error(f"导出过程中发生错误: {str(e)}", parent=self.result_window)

    def _update_export_progress(self, current: int, total: int, filename: str):
        """更新导出进度显示"""
        self.export_progress["value"] = current
        self.export_progress_label.config(text=f"正在导出({current}/{total})")
        self.export_progress_filename_label.config(text=filename)

    def _on_export_window_close(self):
        """处理导出窗口关闭事件"""
        self.export_running = False
        if self.export_thread.is_alive():
            # noinspection PyTypeChecker
            self.root.after(100, self._on_export_window_close)
        else:
            self.export_progress_window.destroy()


def main():
    root = tk.Tk()
    MinecraftAssetsExporterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
