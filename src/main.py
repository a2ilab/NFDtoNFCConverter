import os
import unicodedata
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import logging

__version__ = "1.0.1"

# Logger 설정
logging.basicConfig(level=logging.INFO)

# Unicode 체크박스 기호
UNCHECKED = "☐"
CHECKED = "☑"

def abbreviate_path(path, max_length=60):
    if len(path) <= max_length:
        return path
    half = (max_length - 3) // 2
    return path[:half] + "..." + path[-half:]

class NFConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NFD → NFC 변환기 v1.0.1")

        self.selected_dir = None
        self.check_states = {}
        self.original_names = {}

        top_frame = tk.Frame(root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_select_dir = tk.Button(top_frame, text="폴더 선택", command=self.select_directory)
        self.btn_select_dir.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_dir = tk.Label(top_frame, text="선택된 폴더: 없음")
        self.lbl_dir.pack(side=tk.LEFT, padx=(0, 10))

        self.all_var = tk.BooleanVar()
        self.chk_all = tk.Checkbutton(top_frame, text="전체 선택", variable=self.all_var, command=self.toggle_all)
        self.chk_all.pack(side=tk.LEFT)

        self.tree = ttk.Treeview(root, columns=("type", "old_name", "new_name", "relative_path"),
                                 show="tree headings")
        for col, width in [("#0", 200), ("type", 60), ("old_name", 150), ("new_name", 150), ("relative_path", 200)]:
            self.tree.heading(col, text=col if col != "#0" else "항목")
            self.tree.column(col, width=width, anchor=tk.CENTER if col == "type" else tk.W)

        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.tree.bind("<Button-1>", self.on_tree_click)

        self.lbl_status = tk.Label(root, text="", anchor="w")
        self.lbl_status.pack(fill=tk.X, padx=10, pady=(0, 5))

        bottom_frame = tk.Frame(root)
        bottom_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_convert = tk.Button(bottom_frame, text="선택 항목 변환", command=self.convert_selected)
        self.btn_convert.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_refresh = tk.Button(bottom_frame, text="새로고침", command=self.refresh)
        self.btn_refresh.pack(side=tk.LEFT)

    def update_status(self, message):
        self.root.after(0, lambda: self.lbl_status.config(text=abbreviate_path(message)))

    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.selected_dir = directory
            self.lbl_dir.config(text=f"선택된 폴더: {directory}")
            self.build_tree()

    def build_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.check_states.clear()
        self.original_names.clear()
        threading.Thread(target=self.scan_folder, daemon=True).start()

    def scan_folder(self):
        self.update_status("스캔 중...")
        tree_data = self.build_candidate_tree(self.selected_dir, self.selected_dir)
        self.root.after(0, lambda: self.insert_tree_item("", tree_data) if tree_data else None)
        self.update_status("스캔 완료.")

    def build_candidate_tree(self, directory, base):
        folder_name = os.path.basename(directory)
        normalized_folder_name = unicodedata.normalize('NFC', folder_name)
        rel_path = os.path.relpath(directory, base) or ""
        node = {
            'type': 'folder',
            'old_name': folder_name,
            'new_name': normalized_folder_name,
            'path': directory,
            'relative_path': rel_path,
            'candidate': folder_name != normalized_folder_name,
            'children': []
        }

        try:
            entries = os.listdir(directory)
        except Exception:
            entries = []

        for entry in entries:
            full_path = os.path.join(directory, entry)
            if os.path.isdir(full_path):
                child = self.build_candidate_tree(full_path, base)
                if child:
                    node['children'].append(child)
            elif os.path.isfile(full_path):
                normalized_entry = unicodedata.normalize('NFC', entry)
                if entry != normalized_entry:
                    node['children'].append({
                        'type': 'file', 'old_name': entry, 'new_name': normalized_entry,
                        'path': full_path,
                        'relative_path': os.path.join(rel_path, entry) if rel_path else entry,
                        'candidate': True
                    })
        return node if node['candidate'] or node['children'] else None

    def insert_tree_item(self, parent, node):
        text = f"{UNCHECKED} {node['old_name']}"
        item_id = self.tree.insert(parent, "end", text=text, values=(node['type'], node['old_name'], node['new_name'], node['relative_path']))
        self.check_states[item_id] = False
        self.original_names[item_id] = node['old_name']
        for child in node.get('children', []):
            self.insert_tree_item(item_id, child)

    def on_tree_click(self, event):
        if self.tree.identify("region", event.x, event.y) == "tree":
            item = self.tree.identify_row(event.y)
            if item:
                self.toggle_item(item)

    def toggle_item(self, item):
        state = not self.check_states.get(item, False)
        self.set_item_recursive(item, state)

    def set_item_recursive(self, item, state):
        self.check_states[item] = state
        original = self.original_names.get(item, "")
        self.tree.item(item, text=f"{CHECKED if state else UNCHECKED} {original}")
        for child in self.tree.get_children(item):
            self.set_item_recursive(child, state)

    def toggle_all(self):
        for item in self.tree.get_children():
            self.set_item_recursive(item, self.all_var.get())

    def convert_selected(self):
        checked = [item for item, state in self.check_states.items() if state]
        if not checked:
            messagebox.showinfo("알림", "변환할 항목을 선택해주세요.")
            return

        errors = []
        for item in checked:
            typ, old_name, new_name, rel_path = self.tree.item(item)['values']
            old_path = os.path.join(self.selected_dir, rel_path)
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            logging.info("변환 시도: %s → %s", old_path, new_path)
            try:
                if os.path.exists(new_path):
                    raise FileExistsError("대상 항목 존재")
                os.rename(old_path, new_path)
            except Exception as e:
                errors.append(f"{rel_path}: {e}")

        if errors:
            messagebox.showerror("오류", "\n".join(errors))
        else:
            messagebox.showinfo("성공", "변환 완료.")
        self.build_tree()

    def refresh(self):
        if self.selected_dir:
            self.build_tree()

if __name__ == "__main__":
    root = tk.Tk()
    NFConverterApp(root)
    root.mainloop()