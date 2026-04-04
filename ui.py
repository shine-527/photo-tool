"""照片處理小工具 — Tkinter 主介面"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from processor import process_images


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("照片處理小工具")
        self.geometry("860x620")
        self.minsize(780, 560)

        self.file_list: list[str] = []

        self._build_toolbar()
        self._build_main_area()
        self._build_bottom_bar()

    # ── 上方工具列 ───────────────────────────────────────────

    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")

        ttk.Button(bar, text="新增檔案", command=self._add_files).pack(side="left", padx=2)
        ttk.Button(bar, text="新增資料夾", command=self._add_folder).pack(side="left", padx=2)
        ttk.Button(bar, text="移除選取", command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(bar, text="清除全部", command=self._clear_files).pack(side="left", padx=2)

        ttk.Label(bar, text="  輸出資料夾:").pack(side="left")
        self.output_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop", "output"))
        ttk.Entry(bar, textvariable=self.output_var, width=30).pack(side="left", padx=2)
        ttk.Button(bar, text="瀏覽…", command=self._browse_output).pack(side="left", padx=2)

    # ── 主區域：左側檔案列表 + 右側設定 ─────────────────────

    def _build_main_area(self):
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        # 左側：檔案清單
        left = ttk.Frame(pane)
        pane.add(left, weight=1)

        self.file_listbox = tk.Listbox(left, selectmode="extended", activestyle="none")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.file_listbox.pack(side="left", fill="both", expand=True)

        # 右側：設定區（可捲動）
        right = ttk.Frame(pane)
        pane.add(right, weight=1)

        canvas = tk.Canvas(right, highlightthickness=0)
        vsb = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        self.settings_frame = ttk.Frame(canvas)
        self.settings_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.settings_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 滑鼠滾輪支援
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._build_settings()

    # ── 設定面板 ─────────────────────────────────────────────

    def _build_settings(self):
        f = self.settings_frame
        pad = {"padx": 8, "pady": 4, "sticky": "w"}

        # ── 縮放 / 壓縮 ──
        sec1 = ttk.LabelFrame(f, text="縮放 / 壓縮", padding=6)
        sec1.pack(fill="x", pady=4)

        self.resize_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec1, text="啟用縮放", variable=self.resize_enabled).grid(row=0, column=0, columnspan=4, **pad)

        ttk.Label(sec1, text="寬:").grid(row=1, column=0, **pad)
        self.resize_w = tk.IntVar(value=1920)
        ttk.Entry(sec1, textvariable=self.resize_w, width=7).grid(row=1, column=1, **pad)

        ttk.Label(sec1, text="高:").grid(row=1, column=2, **pad)
        self.resize_h = tk.IntVar(value=1080)
        ttk.Entry(sec1, textvariable=self.resize_h, width=7).grid(row=1, column=3, **pad)

        self.keep_ratio = tk.BooleanVar(value=True)
        ttk.Checkbutton(sec1, text="等比縮放", variable=self.keep_ratio).grid(row=2, column=0, columnspan=4, **pad)

        ttk.Label(sec1, text="品質:").grid(row=3, column=0, **pad)
        self.quality = tk.IntVar(value=85)
        ttk.Scale(sec1, from_=10, to=100, variable=self.quality, orient="horizontal").grid(row=3, column=1, columnspan=2, sticky="we")
        self.quality_label = ttk.Label(sec1, text="85")
        self.quality_label.grid(row=3, column=3, **pad)
        self.quality.trace_add("write", lambda *_: self.quality_label.config(text=str(self.quality.get())))

        # ── 濾鏡 ──
        sec2 = ttk.LabelFrame(f, text="濾鏡 / 色彩調整", padding=6)
        sec2.pack(fill="x", pady=4)

        self.filter_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec2, text="啟用濾鏡", variable=self.filter_enabled).grid(row=0, column=0, columnspan=4, **pad)

        self.brightness = tk.DoubleVar(value=1.0)
        self.contrast = tk.DoubleVar(value=1.0)
        self.saturation = tk.DoubleVar(value=1.0)

        for i, (label, var) in enumerate([
            ("亮度:", self.brightness),
            ("對比:", self.contrast),
            ("飽和度:", self.saturation),
        ], start=1):
            ttk.Label(sec2, text=label).grid(row=i, column=0, **pad)
            ttk.Scale(sec2, from_=0.0, to=3.0, variable=var, orient="horizontal").grid(row=i, column=1, columnspan=2, sticky="we")
            lbl = ttk.Label(sec2, text="1.0")
            lbl.grid(row=i, column=3, **pad)
            var.trace_add("write", lambda *_, v=var, l=lbl: l.config(text=f"{v.get():.1f}"))

        self.grayscale = tk.BooleanVar()
        ttk.Checkbutton(sec2, text="黑白", variable=self.grayscale).grid(row=4, column=0, columnspan=4, **pad)

        # ── 浮水印 ──
        sec3 = ttk.LabelFrame(f, text="浮水印", padding=6)
        sec3.pack(fill="x", pady=4)

        self.wm_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec3, text="啟用浮水印", variable=self.wm_enabled).grid(row=0, column=0, columnspan=4, **pad)

        self.wm_type = tk.StringVar(value="text")
        ttk.Radiobutton(sec3, text="文字", variable=self.wm_type, value="text").grid(row=1, column=0, **pad)
        ttk.Radiobutton(sec3, text="圖片", variable=self.wm_type, value="image").grid(row=1, column=1, **pad)

        ttk.Label(sec3, text="文字:").grid(row=2, column=0, **pad)
        self.wm_text = tk.StringVar(value="© 版權所有")
        ttk.Entry(sec3, textvariable=self.wm_text, width=20).grid(row=2, column=1, columnspan=3, sticky="we", padx=8)

        ttk.Label(sec3, text="字體大小:").grid(row=3, column=0, **pad)
        self.wm_font_size = tk.IntVar(value=36)
        ttk.Entry(sec3, textvariable=self.wm_font_size, width=7).grid(row=3, column=1, **pad)

        ttk.Label(sec3, text="圖片:").grid(row=4, column=0, **pad)
        self.wm_image_path = tk.StringVar()
        ttk.Entry(sec3, textvariable=self.wm_image_path, width=18).grid(row=4, column=1, columnspan=2, sticky="we", padx=8)
        ttk.Button(sec3, text="選擇", command=self._browse_wm_image).grid(row=4, column=3, **pad)

        ttk.Label(sec3, text="位置:").grid(row=5, column=0, **pad)
        self.wm_position = tk.StringVar(value="右下")
        ttk.Combobox(sec3, textvariable=self.wm_position, values=["左上", "右上", "左下", "右下", "居中"], width=8, state="readonly").grid(row=5, column=1, **pad)

        ttk.Label(sec3, text="透明度:").grid(row=6, column=0, **pad)
        self.wm_opacity = tk.IntVar(value=128)
        ttk.Scale(sec3, from_=0, to=255, variable=self.wm_opacity, orient="horizontal").grid(row=6, column=1, columnspan=2, sticky="we")
        self.wm_opacity_label = ttk.Label(sec3, text="128")
        self.wm_opacity_label.grid(row=6, column=3, **pad)
        self.wm_opacity.trace_add("write", lambda *_: self.wm_opacity_label.config(text=str(self.wm_opacity.get())))

        ttk.Label(sec3, text="縮放:").grid(row=7, column=0, **pad)
        self.wm_scale = tk.DoubleVar(value=0.2)
        ttk.Scale(sec3, from_=0.05, to=1.0, variable=self.wm_scale, orient="horizontal").grid(row=7, column=1, columnspan=2, sticky="we")
        self.wm_scale_label = ttk.Label(sec3, text="0.20")
        self.wm_scale_label.grid(row=7, column=3, **pad)
        self.wm_scale.trace_add("write", lambda *_: self.wm_scale_label.config(text=f"{self.wm_scale.get():.2f}"))

        # ── 格式轉換 ──
        sec4 = ttk.LabelFrame(f, text="輸出格式", padding=6)
        sec4.pack(fill="x", pady=4)

        ttk.Label(sec4, text="格式:").grid(row=0, column=0, **pad)
        self.output_format = tk.StringVar(value="JPG")
        ttk.Combobox(sec4, textvariable=self.output_format, values=["JPG", "PNG", "WEBP", "BMP"], width=8, state="readonly").grid(row=0, column=1, **pad)

        # ── 重新命名 ──
        sec5 = ttk.LabelFrame(f, text="批次重新命名", padding=6)
        sec5.pack(fill="x", pady=4)

        self.rename_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec5, text="啟用重新命名", variable=self.rename_enabled).grid(row=0, column=0, columnspan=4, **pad)

        ttk.Label(sec5, text="規則:").grid(row=1, column=0, **pad)
        self.rename_pattern = tk.StringVar(value="photo_{n:03d}")
        ttk.Entry(sec5, textvariable=self.rename_pattern, width=20).grid(row=1, column=1, columnspan=3, sticky="we", padx=8)

        ttk.Label(sec5, text="可用：{n} 序號、{name} 原檔名", foreground="gray").grid(row=2, column=0, columnspan=4, **pad)

    # ── 底部列：開始處理 + 進度條 ────────────────────────────

    def _build_bottom_bar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")

        self.start_btn = ttk.Button(bar, text="開始處理", command=self._start_processing)
        self.start_btn.pack(side="left", padx=4)

        self.progress = ttk.Progressbar(bar, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=4)

        self.progress_label = ttk.Label(bar, text="就緒")
        self.progress_label.pack(side="left", padx=4)

        self.open_btn = ttk.Button(bar, text="開啟輸出資料夾", command=self._open_output, state="disabled")
        self.open_btn.pack(side="right", padx=4)

    # ── 工具列操作 ───────────────────────────────────────────

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="選擇圖片",
            filetypes=[
                ("圖片檔案", "*.jpg *.jpeg *.png *.webp *.bmp *.heic *.heif *.tiff"),
                ("所有檔案", "*.*"),
            ],
        )
        for p in paths:
            if p not in self.file_list:
                self.file_list.append(p)
                self.file_listbox.insert("end", os.path.basename(p))

    def _add_folder(self):
        folder = filedialog.askdirectory(title="選擇資料夾")
        if not folder:
            return
        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif", ".tiff"}
        for name in sorted(os.listdir(folder)):
            if Path(name).suffix.lower() in exts:
                full = os.path.join(folder, name)
                if full not in self.file_list:
                    self.file_list.append(full)
                    self.file_listbox.insert("end", name)

    def _remove_selected(self):
        for i in reversed(self.file_listbox.curselection()):
            self.file_listbox.delete(i)
            self.file_list.pop(i)

    def _clear_files(self):
        self.file_listbox.delete(0, "end")
        self.file_list.clear()

    def _browse_output(self):
        d = filedialog.askdirectory(title="選擇輸出資料夾")
        if d:
            self.output_var.set(d)

    def _browse_wm_image(self):
        p = filedialog.askopenfilename(title="選擇浮水印圖片", filetypes=[("圖片", "*.png *.jpg *.jpeg *.webp")])
        if p:
            self.wm_image_path.set(p)

    def _open_output(self):
        path = self.output_var.get()
        if os.path.isdir(path):
            subprocess.Popen(["explorer", os.path.normpath(path)])

    # ── 處理流程 ─────────────────────────────────────────────

    def _gather_settings(self) -> dict:
        return {
            "resize_enabled": self.resize_enabled.get(),
            "resize_width": self.resize_w.get(),
            "resize_height": self.resize_h.get(),
            "resize_keep_ratio": self.keep_ratio.get(),
            "quality": self.quality.get(),
            "filter_enabled": self.filter_enabled.get(),
            "brightness": self.brightness.get(),
            "contrast": self.contrast.get(),
            "saturation": self.saturation.get(),
            "grayscale": self.grayscale.get(),
            "watermark_enabled": self.wm_enabled.get(),
            "watermark_type": self.wm_type.get(),
            "watermark_text": self.wm_text.get(),
            "watermark_font_size": self.wm_font_size.get(),
            "watermark_image_path": self.wm_image_path.get(),
            "watermark_position": self.wm_position.get(),
            "watermark_opacity": self.wm_opacity.get(),
            "watermark_scale": self.wm_scale.get(),
            "output_format": self.output_format.get(),
            "rename_enabled": self.rename_enabled.get(),
            "rename_pattern": self.rename_pattern.get(),
        }

    def _start_processing(self):
        if not self.file_list:
            messagebox.showwarning("提示", "請先加入圖片檔案！")
            return

        output_dir = self.output_var.get()
        if not output_dir:
            messagebox.showwarning("提示", "請選擇輸出資料夾！")
            return

        settings = self._gather_settings()
        self.start_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.file_list)
        self.progress_label.config(text="處理中…")

        def run():
            def on_progress(current, total):
                self.after(0, lambda: self._update_progress(current, total))

            process_images(self.file_list, settings, output_dir, progress_cb=on_progress)
            self.after(0, self._processing_done)

        threading.Thread(target=run, daemon=True).start()

    def _update_progress(self, current, total):
        self.progress["value"] = current
        self.progress_label.config(text=f"{current}/{total}")

    def _processing_done(self):
        self.start_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self.progress_label.config(text="完成！")
        messagebox.showinfo("完成", "所有圖片處理完成！")
