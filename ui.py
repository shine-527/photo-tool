"""照片處理小工具 — Tkinter 主介面（shadcn 風格）"""

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from processor import get_preview_image, process_images

# ── 色彩系統 ─────────────────────────────────────────────────
BG = "#fafafa"
CARD = "#ffffff"
BORDER = "#e4e4e7"
PRIMARY = "#18181b"
PRIMARY_FG = "#fafafa"
MUTED = "#71717a"
ACCENT = "#f4f4f5"
DANGER = "#ef4444"
DANGER_FG = "#ffffff"
FONT = "微軟正黑體"


# ── 自訂按鈕元件 ──────────────────────────────────────────────

class Btn(tk.Button):
    """Shadcn 風格的扁平按鈕，支援 default / outline / ghost / danger 四種樣式。"""
    _STYLES = {
        "default": dict(bg=PRIMARY, fg=PRIMARY_FG, activebackground="#27272a",
                        activeforeground=PRIMARY_FG, relief="flat", bd=0),
        "outline": dict(bg=CARD, fg=PRIMARY, activebackground=ACCENT,
                        activeforeground=PRIMARY, relief="solid", bd=1,
                        highlightbackground=BORDER, highlightthickness=1),
        "ghost":   dict(bg=BG, fg=PRIMARY, activebackground=ACCENT,
                        activeforeground=PRIMARY, relief="flat", bd=0),
        "danger":  dict(bg=DANGER, fg=DANGER_FG, activebackground="#dc2626",
                        activeforeground=DANGER_FG, relief="flat", bd=0),
    }

    def __init__(self, parent, text, command=None, variant="default", **kw):
        cfg = dict(self._STYLES.get(variant, self._STYLES["default"]))
        cfg.update(dict(
            text=text, command=command,
            font=(FONT, 9), cursor="hand2",
            padx=12, pady=5,
        ))
        cfg.update(kw)
        super().__init__(parent, **cfg)


# ── 主應用程式 ────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("照片處理小工具")
        self.geometry("1160x700")
        self.minsize(960, 600)
        self.configure(bg=BG)

        self.file_list: list[str] = []
        self._preview_job = None
        self._preview_photo = None

        self._apply_theme()
        self._build_toolbar()
        self._build_main_area()
        self._build_bottom_bar()

    # ── 主題 ─────────────────────────────────────────────────

    def _apply_theme(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=PRIMARY, font=(FONT, 9))
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("TLabel", background=CARD, foreground=PRIMARY)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=(FONT, 8))
        s.configure("TCheckbutton", background=CARD, foreground=PRIMARY)
        s.configure("TRadiobutton", background=CARD, foreground=PRIMARY)
        s.configure("TEntry", fieldbackground=CARD, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
        s.configure("TCombobox", fieldbackground=CARD, bordercolor=BORDER)
        s.configure("TScale", background=CARD, troughcolor=ACCENT, sliderlength=14)
        s.configure("TProgressbar", troughcolor=ACCENT, background=PRIMARY, bordercolor=BORDER)
        s.configure("TSeparator", background=BORDER)
        s.configure("TScrollbar", background=ACCENT, troughcolor=BG,
                    bordercolor=BG, arrowcolor=MUTED, relief="flat")

    # ── 工具列 ───────────────────────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=CARD, padx=10, pady=8,
                       highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x")

        Btn(bar, "+ 新增檔案", self._add_files).pack(side="left", padx=(0, 4))
        Btn(bar, "新增資料夾", self._add_folder, "outline").pack(side="left", padx=4)
        Btn(bar, "移除選取", self._remove_selected, "ghost").pack(side="left", padx=4)
        Btn(bar, "清除全部", self._clear_files, "danger").pack(side="left", padx=4)

        tk.Label(bar, text="輸出資料夾:", bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=(16, 4))
        self.output_var = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Desktop", "output"))
        ttk.Entry(bar, textvariable=self.output_var, width=28).pack(side="left", padx=4)
        Btn(bar, "瀏覽…", self._browse_output, "ghost", padx=8).pack(side="left", padx=4)

    # ── 主區域 ───────────────────────────────────────────────

    def _build_main_area(self):
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        # 左側：檔案列表
        left = tk.Frame(pane, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        pane.add(left, weight=1)

        tk.Label(left, text="圖片列表", bg=CARD, fg=MUTED,
                 font=(FONT, 8, "bold"), padx=10, pady=7).pack(anchor="w")
        tk.Frame(left, bg=BORDER, height=1).pack(fill="x")

        lb_frame = tk.Frame(left, bg=CARD)
        lb_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.file_listbox = tk.Listbox(
            lb_frame, selectmode="extended", activestyle="none",
            bg=CARD, fg=PRIMARY, selectbackground=ACCENT, selectforeground=PRIMARY,
            relief="flat", bd=0, font=(FONT, 9), highlightthickness=0,
        )
        sb = ttk.Scrollbar(lb_frame, orient="vertical",
                           command=self.file_listbox.yview)
        self.file_listbox.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.file_listbox.pack(side="left", fill="both", expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", lambda _: self._schedule_preview())

        # 右側：預覽 + 設定
        right = tk.Frame(pane, bg=BG)
        pane.add(right, weight=2)

        self._build_preview(right)
        self._build_settings_panel(right)

    # ── 預覽區 ───────────────────────────────────────────────

    def _build_preview(self, parent):
        card = tk.Frame(parent, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 8))

        tk.Label(card, text="即時預覽", bg=CARD, fg=MUTED,
                 font=(FONT, 8, "bold"), padx=10, pady=7).pack(anchor="w")
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x")

        self._preview_canvas = tk.Canvas(
            card, height=270, bg="#f0f0f0",
            highlightthickness=0, relief="flat",
        )
        self._preview_canvas.pack(fill="x", padx=8, pady=8)
        self._preview_canvas.bind("<Configure>", lambda _: self._schedule_preview())
        self._show_placeholder()

    # ── 設定面板 ─────────────────────────────────────────────

    def _build_settings_panel(self, parent):
        card = tk.Frame(parent, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="調整設定", bg=CARD, fg=MUTED,
                 font=(FONT, 8, "bold"), padx=10, pady=7).pack(anchor="w")
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x")

        canvas = tk.Canvas(card, highlightthickness=0, bg=CARD)
        vsb = ttk.Scrollbar(card, orient="vertical", command=canvas.yview)
        self.settings_frame = tk.Frame(canvas, bg=CARD)
        self.settings_frame.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.settings_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * e.delta / 120), "units"))

        self._build_settings()

    def _section(self, title: str) -> tk.Frame:
        """建立帶標題的設定區塊。"""
        wrapper = tk.Frame(self.settings_frame, bg=CARD)
        wrapper.pack(fill="x", padx=10, pady=5)

        tk.Label(wrapper, text=title, bg=CARD, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Frame(wrapper, bg=BORDER, height=1).pack(fill="x", pady=(0, 6))

        body = tk.Frame(wrapper, bg=CARD)
        body.pack(fill="x")
        return body

    def _slider_row(self, parent, row, label, var, lo, hi, fmt=".1f"):
        """建立帶數值標籤的滑桿列。"""
        tk.Label(parent, text=label, bg=CARD, fg=PRIMARY,
                 font=(FONT, 9), width=6, anchor="w").grid(
            row=row, column=0, padx=(0, 6), pady=3, sticky="w")

        ttk.Scale(parent, from_=lo, to=hi, variable=var,
                  orient="horizontal").grid(
            row=row, column=1, sticky="we", padx=(0, 8))

        val_lbl = tk.Label(parent, bg=CARD, fg=MUTED,
                           font=(FONT, 9), width=5, anchor="e")
        val_lbl.grid(row=row, column=2, padx=4, pady=3, sticky="e")

        def _update(*_):
            try:
                val_lbl.config(text=format(var.get(), fmt))
            except Exception:
                pass
            self._schedule_preview()

        var.trace_add("write", _update)
        _update()
        parent.columnconfigure(1, weight=1)
        return val_lbl

    def _build_settings(self):
        # ── 縮放 / 壓縮 ─────────────────────────────────────
        sec1 = self._section("縮放 / 壓縮")

        self.resize_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec1, text="啟用縮放", variable=self.resize_enabled).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.resize_enabled.trace_add("write", lambda *_: self._schedule_preview())

        dim_row = tk.Frame(sec1, bg=CARD)
        dim_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(dim_row, text="寬:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.resize_w = tk.IntVar(value=1920)
        ttk.Entry(dim_row, textvariable=self.resize_w, width=7).pack(side="left", padx=(2, 10))
        tk.Label(dim_row, text="高:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.resize_h = tk.IntVar(value=1080)
        ttk.Entry(dim_row, textvariable=self.resize_h, width=7).pack(side="left", padx=2)
        self.resize_w.trace_add("write", lambda *_: self._schedule_preview())
        self.resize_h.trace_add("write", lambda *_: self._schedule_preview())

        self.keep_ratio = tk.BooleanVar(value=True)
        ttk.Checkbutton(sec1, text="等比縮放", variable=self.keep_ratio).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=2)
        self.keep_ratio.trace_add("write", lambda *_: self._schedule_preview())

        self.quality = tk.IntVar(value=85)
        self._slider_row(sec1, 3, "品質:", self.quality, 10, 100, "d")

        # ── 濾鏡 / 色彩調整 ─────────────────────────────────
        sec2 = self._section("濾鏡 / 色彩調整")

        self.filter_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec2, text="啟用濾鏡", variable=self.filter_enabled).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.filter_enabled.trace_add("write", lambda *_: self._schedule_preview())

        self.brightness = tk.DoubleVar(value=1.0)
        self.contrast = tk.DoubleVar(value=1.0)
        self.saturation = tk.DoubleVar(value=1.0)
        self._slider_row(sec2, 1, "亮度:", self.brightness, 0.0, 3.0)
        self._slider_row(sec2, 2, "對比:", self.contrast, 0.0, 3.0)
        self._slider_row(sec2, 3, "飽和度:", self.saturation, 0.0, 3.0)

        self.grayscale = tk.BooleanVar()
        ttk.Checkbutton(sec2, text="黑白", variable=self.grayscale).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=2)
        self.grayscale.trace_add("write", lambda *_: self._schedule_preview())

        # ── 浮水印 ──────────────────────────────────────────
        sec3 = self._section("浮水印")

        self.wm_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec3, text="啟用浮水印", variable=self.wm_enabled).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.wm_enabled.trace_add("write", lambda *_: self._schedule_preview())

        type_row = tk.Frame(sec3, bg=CARD)
        type_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=2)
        self.wm_type = tk.StringVar(value="text")
        ttk.Radiobutton(type_row, text="文字", variable=self.wm_type,
                        value="text").pack(side="left", padx=(0, 12))
        ttk.Radiobutton(type_row, text="圖片", variable=self.wm_type,
                        value="image").pack(side="left")
        self.wm_type.trace_add("write", lambda *_: self._schedule_preview())

        text_row = tk.Frame(sec3, bg=CARD)
        text_row.grid(row=2, column=0, columnspan=3, sticky="we", pady=2)
        tk.Label(text_row, text="文字:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_text = tk.StringVar(value="© 版權所有")
        ttk.Entry(text_row, textvariable=self.wm_text, width=20).pack(
            side="left", padx=(4, 12), fill="x", expand=True)
        tk.Label(text_row, text="字體大小:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_font_size = tk.IntVar(value=36)
        ttk.Entry(text_row, textvariable=self.wm_font_size, width=5).pack(side="left", padx=4)
        self.wm_text.trace_add("write", lambda *_: self._schedule_preview())
        self.wm_font_size.trace_add("write", lambda *_: self._schedule_preview())

        img_row = tk.Frame(sec3, bg=CARD)
        img_row.grid(row=3, column=0, columnspan=3, sticky="we", pady=2)
        tk.Label(img_row, text="圖片:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_image_path = tk.StringVar()
        ttk.Entry(img_row, textvariable=self.wm_image_path, width=20).pack(
            side="left", padx=4, fill="x", expand=True)
        Btn(img_row, "選擇", self._browse_wm_image, "outline",
            padx=8, pady=3).pack(side="left")
        self.wm_image_path.trace_add("write", lambda *_: self._schedule_preview())

        pos_row = tk.Frame(sec3, bg=CARD)
        pos_row.grid(row=4, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(pos_row, text="位置:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_position = tk.StringVar(value="右下")
        ttk.Combobox(pos_row, textvariable=self.wm_position,
                     values=["左上", "右上", "左下", "右下", "居中"],
                     width=8, state="readonly").pack(side="left", padx=4)
        self.wm_position.trace_add("write", lambda *_: self._schedule_preview())

        self.wm_opacity = tk.IntVar(value=128)
        self._slider_row(sec3, 5, "透明度:", self.wm_opacity, 0, 255, "d")

        self.wm_scale = tk.DoubleVar(value=0.2)
        self._slider_row(sec3, 6, "縮放:", self.wm_scale, 0.05, 1.0, ".2f")

        # ── 輸出格式 ─────────────────────────────────────────
        sec4 = self._section("輸出格式")
        fmt_row = tk.Frame(sec4, bg=CARD)
        fmt_row.grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(fmt_row, text="格式:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.output_format = tk.StringVar(value="JPG")
        ttk.Combobox(fmt_row, textvariable=self.output_format,
                     values=["JPG", "PNG", "WEBP", "BMP"],
                     width=8, state="readonly").pack(side="left", padx=4)
        self.output_format.trace_add("write", lambda *_: self._schedule_preview())

    # ── 底部列 ───────────────────────────────────────────────

    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=CARD, padx=10, pady=8,
                       highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x")

        self.start_btn = Btn(bar, "▶  開始處理", self._start_processing)
        self.start_btn.pack(side="left", padx=(0, 10))

        self.progress = ttk.Progressbar(bar, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=4)

        self.progress_label = tk.Label(bar, text="就緒", bg=CARD, fg=MUTED,
                                       font=(FONT, 9))
        self.progress_label.pack(side="left", padx=6)

        self.open_btn = Btn(bar, "開啟輸出資料夾", self._open_output,
                            "outline", state="disabled")
        self.open_btn.pack(side="right")

    # ── 檔案操作 ─────────────────────────────────────────────

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
        self._schedule_preview()

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
        self._schedule_preview()

    def _remove_selected(self):
        for i in reversed(self.file_listbox.curselection()):
            self.file_listbox.delete(i)
            self.file_list.pop(i)
        self._schedule_preview()

    def _clear_files(self):
        self.file_listbox.delete(0, "end")
        self.file_list.clear()
        self._show_placeholder()

    def _browse_output(self):
        d = filedialog.askdirectory(title="選擇輸出資料夾")
        if d:
            self.output_var.set(d)

    def _browse_wm_image(self):
        p = filedialog.askopenfilename(
            title="選擇浮水印圖片",
            filetypes=[("圖片", "*.png *.jpg *.jpeg *.webp")],
        )
        if p:
            self.wm_image_path.set(p)

    def _open_output(self):
        path = self.output_var.get()
        if os.path.isdir(path):
            subprocess.Popen(["explorer", os.path.normpath(path)])

    # ── 即時預覽 ─────────────────────────────────────────────

    def _schedule_preview(self):
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(350, self._render_preview)

    def _render_preview(self):
        self._preview_job = None
        if not self.file_list:
            self._show_placeholder()
            return

        sel = self.file_listbox.curselection()
        idx = sel[0] if sel else 0
        path = self.file_list[idx]
        settings = self._gather_settings()

        def worker():
            img = get_preview_image(path, settings)
            if img:
                self.after(0, lambda: self._display_preview(img))

        threading.Thread(target=worker, daemon=True).start()

    def _display_preview(self, img: Image.Image):
        w = self._preview_canvas.winfo_width() or 500
        h = self._preview_canvas.winfo_height() or 270
        copy = img.copy()
        copy.thumbnail((w - 16, h - 16), Image.LANCZOS)
        photo = ImageTk.PhotoImage(copy)
        self._preview_photo = photo  # 防止 GC 回收
        self._preview_canvas.delete("all")
        self._preview_canvas.create_image(w // 2, h // 2, anchor="center", image=photo)

    def _show_placeholder(self):
        self._preview_canvas.delete("all")
        w = self._preview_canvas.winfo_width() or 500
        h = self._preview_canvas.winfo_height() or 270
        self._preview_canvas.create_text(
            w // 2, h // 2,
            text="選擇圖片以預覽",
            fill=MUTED, font=(FONT, 12),
        )

    # ── 設定收集 ─────────────────────────────────────────────

    def _gather_settings(self) -> dict:
        def safe_int(var, default):
            try:
                return var.get()
            except Exception:
                return default

        return {
            "resize_enabled":      self.resize_enabled.get(),
            "resize_width":        safe_int(self.resize_w, 1920),
            "resize_height":       safe_int(self.resize_h, 1080),
            "resize_keep_ratio":   self.keep_ratio.get(),
            "quality":             safe_int(self.quality, 85),
            "filter_enabled":      self.filter_enabled.get(),
            "brightness":          self.brightness.get(),
            "contrast":            self.contrast.get(),
            "saturation":          self.saturation.get(),
            "grayscale":           self.grayscale.get(),
            "watermark_enabled":   self.wm_enabled.get(),
            "watermark_type":      self.wm_type.get(),
            "watermark_text":      self.wm_text.get(),
            "watermark_font_size": safe_int(self.wm_font_size, 36),
            "watermark_image_path": self.wm_image_path.get(),
            "watermark_position":  self.wm_position.get(),
            "watermark_opacity":   self.wm_opacity.get(),
            "watermark_scale":     self.wm_scale.get(),
            "output_format":       self.output_format.get(),
            "rename_enabled":      False,
            "rename_pattern":      "",
        }

    # ── 處理流程 ─────────────────────────────────────────────

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
