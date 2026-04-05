"""照片處理小工具 — Tkinter 主介面（shadcn 風格）"""

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from processor import BORDER_COLORS, WATERMARK_FONTS, get_preview_image, process_images

# ── 色彩系統 ─────────────────────────────────────────────────
BG      = "#fafafa"
CARD    = "#ffffff"
BORDER  = "#e4e4e7"
PRIMARY = "#18181b"
PRIMARY_FG = "#fafafa"
MUTED   = "#71717a"
ACCENT  = "#f4f4f5"
DANGER  = "#ef4444"
DANGER_FG = "#ffffff"
FONT    = "微軟正黑體"


# ── 自訂按鈕 ─────────────────────────────────────────────────

class Btn(tk.Button):
    """Shadcn 風格扁平按鈕。variant: default / outline / ghost / danger"""
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
        cfg.update(dict(text=text, command=command,
                        font=(FONT, 9), cursor="hand2", padx=12, pady=5))
        cfg.update(kw)
        super().__init__(parent, **cfg)


# ── 主應用程式 ────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("照片處理小工具")
        self.geometry("1200x720")
        self.minsize(1000, 600)
        self.configure(bg=BG)

        self.file_list: list[str] = []
        self._preview_job   = None
        self._preview_photo = None       # 處理後圖 (防 GC)
        self._preview_orig  = None       # 原圖 (防 GC)

        self._apply_theme()
        self._build_toolbar()
        self._build_main_area()
        self._build_bottom_bar()

    # ── 主題 ─────────────────────────────────────────────────

    def _apply_theme(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=PRIMARY, font=(FONT, 9))
        s.configure("TFrame",      background=BG)
        s.configure("TLabel",      background=CARD, foreground=PRIMARY)
        s.configure("TCheckbutton", background=CARD, foreground=PRIMARY)
        s.configure("TRadiobutton", background=CARD, foreground=PRIMARY)
        s.configure("TEntry",      fieldbackground=CARD, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
        s.configure("TCombobox",   fieldbackground=CARD, bordercolor=BORDER)
        s.configure("TScale",      background=CARD, troughcolor=ACCENT, sliderlength=14)
        s.configure("TProgressbar", troughcolor=ACCENT, background=PRIMARY, bordercolor=BORDER)
        s.configure("TScrollbar",  background=ACCENT, troughcolor=BG,
                    bordercolor=BG, arrowcolor=MUTED, relief="flat")

    # ── 工具列 ───────────────────────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=CARD, padx=10, pady=8,
                       highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x")

        Btn(bar, "+ 新增檔案",  self._add_files).pack(side="left", padx=(0, 4))
        Btn(bar, "新增資料夾",  self._add_folder,        "outline").pack(side="left", padx=4)
        Btn(bar, "移除選取",    self._remove_selected,   "ghost").pack(side="left", padx=4)
        Btn(bar, "清除全部",    self._clear_files,        "danger").pack(side="left", padx=4)

        tk.Label(bar, text="輸出資料夾:", bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=(16, 4))
        self.output_var = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Desktop", "output"))
        ttk.Entry(bar, textvariable=self.output_var, width=28).pack(side="left", padx=4)
        Btn(bar, "瀏覽…", self._browse_output, "ghost", padx=8).pack(side="left", padx=4)

    # ── 主區域（三欄） ───────────────────────────────────────

    def _build_main_area(self):
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        # 左欄：檔案列表
        left = tk.Frame(pane, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        pane.add(left, weight=1)
        self._build_file_panel(left)

        # 中欄：設定
        mid = tk.Frame(pane, bg=BG)
        pane.add(mid, weight=2)
        self._build_settings_panel(mid)

        # 右欄：前後對比預覽
        right = tk.Frame(pane, bg=BG)
        pane.add(right, weight=2)
        self._build_preview(right)

    # ── 左欄：檔案列表 ───────────────────────────────────────

    def _build_file_panel(self, parent):
        tk.Label(parent, text="圖片列表", bg=CARD, fg=MUTED,
                 font=(FONT, 8, "bold"), padx=10, pady=7).pack(anchor="w")
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")

        lbf = tk.Frame(parent, bg=CARD)
        lbf.pack(fill="both", expand=True, padx=4, pady=4)

        self.file_listbox = tk.Listbox(
            lbf, selectmode="extended", activestyle="none",
            bg=CARD, fg=PRIMARY, selectbackground=ACCENT, selectforeground=PRIMARY,
            relief="flat", bd=0, font=(FONT, 9), highlightthickness=0,
        )
        sb = ttk.Scrollbar(lbf, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.file_listbox.pack(side="left", fill="both", expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", lambda _: self._schedule_preview())

    # ── 右欄：前後對比預覽 ───────────────────────────────────

    def _build_preview(self, parent):
        card = tk.Frame(parent, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True)

        # 標題列（含左右標籤）
        hdr = tk.Frame(card, bg=CARD)
        hdr.pack(fill="x", padx=10, pady=7)
        tk.Label(hdr, text="前後對比", bg=CARD, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(side="left")
        tk.Label(hdr, text="原圖", bg=CARD, fg=MUTED,
                 font=(FONT, 8)).pack(side="left", padx=(20, 0))
        tk.Label(hdr, text="│", bg=CARD, fg=BORDER,
                 font=(FONT, 8)).pack(side="left", padx=4)
        tk.Label(hdr, text="處理後", bg=CARD, fg=MUTED,
                 font=(FONT, 8)).pack(side="left")

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x")

        self._preview_canvas = tk.Canvas(
            card, bg="#f0f0f0", highlightthickness=0, relief="flat",
        )
        self._preview_canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self._preview_canvas.bind("<Configure>", lambda _: self._schedule_preview())
        self._show_placeholder()

    # ── 中欄：設定面板 ───────────────────────────────────────

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

    # ── 設定區塊輔助 ─────────────────────────────────────────

    def _section(self, title: str) -> tk.Frame:
        wrapper = tk.Frame(self.settings_frame, bg=CARD)
        wrapper.pack(fill="x", padx=10, pady=5)
        tk.Label(wrapper, text=title, bg=CARD, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Frame(wrapper, bg=BORDER, height=1).pack(fill="x", pady=(0, 6))
        body = tk.Frame(wrapper, bg=CARD)
        body.pack(fill="x")
        return body

    def _slider_row(self, parent, row, label, var, lo, hi, fmt=".1f"):
        tk.Label(parent, text=label, bg=CARD, fg=PRIMARY,
                 font=(FONT, 9), width=6, anchor="w").grid(
            row=row, column=0, padx=(0, 6), pady=3, sticky="w")
        ttk.Scale(parent, from_=lo, to=hi, variable=var,
                  orient="horizontal").grid(row=row, column=1, sticky="we", padx=(0, 8))
        val = tk.Label(parent, bg=CARD, fg=MUTED, font=(FONT, 9), width=5, anchor="e")
        val.grid(row=row, column=2, padx=4, pady=3, sticky="e")

        def _upd(*_):
            try:
                val.config(text=format(var.get(), fmt))
            except Exception:
                pass
            self._schedule_preview()

        var.trace_add("write", _upd)
        _upd()
        parent.columnconfigure(1, weight=1)
        return val

    # ── 所有設定區塊 ─────────────────────────────────────────

    def _build_settings(self):
        # ── 縮放 / 壓縮 ─────────────────────────────────────
        sec1 = self._section("縮放 / 壓縮")

        self.resize_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec1, text="啟用縮放", variable=self.resize_enabled).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.resize_enabled.trace_add("write", lambda *_: self._schedule_preview())

        dim = tk.Frame(sec1, bg=CARD)
        dim.grid(row=1, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(dim, text="寬:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.resize_w = tk.IntVar(value=1920)
        ttk.Entry(dim, textvariable=self.resize_w, width=7).pack(side="left", padx=(2, 10))
        tk.Label(dim, text="高:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.resize_h = tk.IntVar(value=1080)
        ttk.Entry(dim, textvariable=self.resize_h, width=7).pack(side="left", padx=2)
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
        self.contrast   = tk.DoubleVar(value=1.0)
        self.saturation = tk.DoubleVar(value=1.0)
        self._slider_row(sec2, 1, "亮度:",  self.brightness, 0.0, 3.0)
        self._slider_row(sec2, 2, "對比:",  self.contrast,   0.0, 3.0)
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

        # 文字 + 字體大小
        text_row = tk.Frame(sec3, bg=CARD)
        text_row.grid(row=2, column=0, columnspan=3, sticky="we", pady=2)
        tk.Label(text_row, text="文字:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_text = tk.StringVar(value="© 版權所有")
        ttk.Entry(text_row, textvariable=self.wm_text, width=16).pack(
            side="left", padx=(4, 8), fill="x", expand=True)
        tk.Label(text_row, text="大小:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_font_size = tk.IntVar(value=36)
        ttk.Entry(text_row, textvariable=self.wm_font_size, width=5).pack(side="left", padx=4)
        self.wm_text.trace_add("write", lambda *_: self._schedule_preview())
        self.wm_font_size.trace_add("write", lambda *_: self._schedule_preview())

        # 字體選擇
        font_row = tk.Frame(sec3, bg=CARD)
        font_row.grid(row=3, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(font_row, text="字體:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_font = tk.StringVar(value="微軟正黑體")
        ttk.Combobox(font_row, textvariable=self.wm_font,
                     values=list(WATERMARK_FONTS.keys()),
                     width=12, state="readonly").pack(side="left", padx=4)
        self.wm_font.trace_add("write", lambda *_: self._schedule_preview())

        # 圖片浮水印
        img_row = tk.Frame(sec3, bg=CARD)
        img_row.grid(row=4, column=0, columnspan=3, sticky="we", pady=2)
        tk.Label(img_row, text="圖片:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_image_path = tk.StringVar()
        ttk.Entry(img_row, textvariable=self.wm_image_path, width=18).pack(
            side="left", padx=4, fill="x", expand=True)
        Btn(img_row, "選擇", self._browse_wm_image, "outline",
            padx=8, pady=3).pack(side="left")
        self.wm_image_path.trace_add("write", lambda *_: self._schedule_preview())

        # 位置
        pos_row = tk.Frame(sec3, bg=CARD)
        pos_row.grid(row=5, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(pos_row, text="位置:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.wm_position = tk.StringVar(value="右下")
        ttk.Combobox(pos_row, textvariable=self.wm_position,
                     values=["左上", "右上", "左下", "右下", "居中"],
                     width=8, state="readonly").pack(side="left", padx=4)
        self.wm_position.trace_add("write", lambda *_: self._schedule_preview())

        self.wm_opacity = tk.IntVar(value=128)
        self._slider_row(sec3, 6, "透明度:", self.wm_opacity, 0, 255, "d")
        self.wm_scale = tk.DoubleVar(value=0.2)
        self._slider_row(sec3, 7, "縮放:",   self.wm_scale,   0.05, 1.0, ".2f")

        # ── 邊框設定 ─────────────────────────────────────────
        sec4 = self._section("邊框設定")

        self.border_enabled = tk.BooleanVar()
        ttk.Checkbutton(sec4, text="啟用邊框", variable=self.border_enabled).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.border_enabled.trace_add("write", lambda *_: self._schedule_preview())

        self.border_width = tk.IntVar(value=20)
        self._slider_row(sec4, 1, "寬度:", self.border_width, 1, 150, "d")

        color_row = tk.Frame(sec4, bg=CARD)
        color_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(color_row, text="顏色:", bg=CARD, font=(FONT, 9)).pack(side="left")
        self.border_color = tk.StringVar(value="黑")
        ttk.Combobox(color_row, textvariable=self.border_color,
                     values=list(BORDER_COLORS.keys()),
                     width=8, state="readonly").pack(side="left", padx=4)
        self.border_color.trace_add("write", lambda *_: self._schedule_preview())

        self.border_softness = tk.IntVar(value=0)
        self._slider_row(sec4, 3, "柔度:", self.border_softness, 0, 60, "d")

        # ── 輸出格式 ─────────────────────────────────────────
        sec5 = self._section("輸出格式")
        fmt_row = tk.Frame(sec5, bg=CARD)
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

    # ── 即時預覽（前後對比） ─────────────────────────────────

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
            try:
                orig = Image.open(path)
                from processor import _ensure_rgb
                orig = _ensure_rgb(orig)
            except Exception:
                orig = None

            processed = get_preview_image(path, settings)

            if orig is not None and processed is not None:
                self.after(0, lambda: self._display_before_after(orig, processed))

        threading.Thread(target=worker, daemon=True).start()

    def _display_before_after(self, orig: Image.Image, processed: Image.Image):
        cw = self._preview_canvas.winfo_width()  or 500
        ch = self._preview_canvas.winfo_height() or 600

        half_w = cw // 2 - 10   # 留 2px 分隔線 + 邊距
        slot_h  = ch - 16

        orig_copy = orig.copy()
        proc_copy = processed.copy()
        orig_copy.thumbnail((half_w, slot_h), Image.LANCZOS)
        proc_copy.thumbnail((half_w, slot_h), Image.LANCZOS)

        orig_photo = ImageTk.PhotoImage(orig_copy)
        proc_photo = ImageTk.PhotoImage(proc_copy)
        self._preview_orig  = orig_photo   # 防 GC
        self._preview_photo = proc_photo

        self._preview_canvas.delete("all")

        # 左側：原圖（置中於左半）
        lx = cw // 4
        self._preview_canvas.create_image(lx, ch // 2, anchor="center", image=orig_photo)

        # 分隔線
        self._preview_canvas.create_line(
            cw // 2, 0, cw // 2, ch, fill=BORDER, width=1, dash=(4, 4)
        )

        # 右側：處理後（置中於右半）
        rx = cw // 4 * 3
        self._preview_canvas.create_image(rx, ch // 2, anchor="center", image=proc_photo)

        # 標籤
        lbl_y = 14
        self._preview_canvas.create_rectangle(
            4, 4, 50, 22, fill=PRIMARY, outline="")
        self._preview_canvas.create_text(
            27, lbl_y, text="原圖", fill=PRIMARY_FG, font=(FONT, 8, "bold"))

        self._preview_canvas.create_rectangle(
            cw // 2 + 4, 4, cw // 2 + 62, 22, fill=PRIMARY, outline="")
        self._preview_canvas.create_text(
            cw // 2 + 33, lbl_y, text="處理後", fill=PRIMARY_FG, font=(FONT, 8, "bold"))

    def _show_placeholder(self):
        self._preview_canvas.delete("all")
        cw = self._preview_canvas.winfo_width()  or 500
        ch = self._preview_canvas.winfo_height() or 600
        self._preview_canvas.create_text(
            cw // 2, ch // 2, text="選擇圖片以預覽",
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
            "resize_enabled":       self.resize_enabled.get(),
            "resize_width":         safe_int(self.resize_w, 1920),
            "resize_height":        safe_int(self.resize_h, 1080),
            "resize_keep_ratio":    self.keep_ratio.get(),
            "quality":              safe_int(self.quality, 85),
            "filter_enabled":       self.filter_enabled.get(),
            "brightness":           self.brightness.get(),
            "contrast":             self.contrast.get(),
            "saturation":           self.saturation.get(),
            "grayscale":            self.grayscale.get(),
            "watermark_enabled":    self.wm_enabled.get(),
            "watermark_type":       self.wm_type.get(),
            "watermark_text":       self.wm_text.get(),
            "watermark_font_size":  safe_int(self.wm_font_size, 36),
            "watermark_font":       WATERMARK_FONTS.get(self.wm_font.get(), "msyh.ttc"),
            "watermark_image_path": self.wm_image_path.get(),
            "watermark_position":   self.wm_position.get(),
            "watermark_opacity":    self.wm_opacity.get(),
            "watermark_scale":      self.wm_scale.get(),
            "border_enabled":       self.border_enabled.get(),
            "border_width":         self.border_width.get(),
            "border_color":         self.border_color.get(),
            "border_softness":      self.border_softness.get(),
            "output_format":        self.output_format.get(),
            "rename_enabled":       False,
            "rename_pattern":       "",
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
        self.progress_label.config(text="完成！")
        messagebox.showinfo("完成", "所有圖片處理完成！")
