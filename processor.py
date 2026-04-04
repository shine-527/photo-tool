"""圖片處理模組 — 縮放、壓縮、濾鏡、浮水印、格式轉換、重新命名"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


def _ensure_rgb(img: Image.Image) -> Image.Image:
    """確保圖片為 RGB/RGBA 模式，方便後續處理。"""
    if img.mode in ("RGB", "RGBA"):
        return img
    return img.convert("RGBA") if "A" in img.mode else img.convert("RGB")


# ── 縮放 / 壓縮 ─────────────────────────────────────────────

def resize_image(img: Image.Image, width: int, height: int, keep_ratio: bool = True) -> Image.Image:
    if keep_ratio:
        img.thumbnail((width, height), Image.LANCZOS)
        return img
    return img.resize((width, height), Image.LANCZOS)


# ── 濾鏡 / 色彩調整 ─────────────────────────────────────────

def apply_filters(
    img: Image.Image,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    grayscale: bool = False,
) -> Image.Image:
    img = _ensure_rgb(img)
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)
    if grayscale:
        img = img.convert("L").convert("RGB")
    return img


# ── 浮水印 ───────────────────────────────────────────────────

_POSITION_MAP = {
    "左上": "top_left",
    "右上": "top_right",
    "左下": "bottom_left",
    "右下": "bottom_right",
    "居中": "center",
}

def _calc_position(base_size: tuple, wm_size: tuple, position: str, margin: int = 10) -> tuple:
    bw, bh = base_size
    ww, wh = wm_size
    pos = _POSITION_MAP.get(position, position)
    positions = {
        "top_left": (margin, margin),
        "top_right": (bw - ww - margin, margin),
        "bottom_left": (margin, bh - wh - margin),
        "bottom_right": (bw - ww - margin, bh - wh - margin),
        "center": ((bw - ww) // 2, (bh - wh) // 2),
    }
    return positions.get(pos, positions["bottom_right"])


def add_text_watermark(
    img: Image.Image,
    text: str,
    position: str = "右下",
    opacity: int = 128,
    font_size: int = 36,
    color: tuple = (255, 255, 255),
) -> Image.Image:
    img = _ensure_rgb(img).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("msyh.ttc", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = _calc_position(img.size, (tw, th), position)
    draw.text((x, y), text, fill=(*color, opacity), font=font)

    return Image.alpha_composite(img, overlay)


def add_image_watermark(
    img: Image.Image,
    watermark_path: str,
    position: str = "右下",
    opacity: int = 128,
    scale: float = 0.2,
) -> Image.Image:
    img = _ensure_rgb(img).convert("RGBA")
    wm = Image.open(watermark_path).convert("RGBA")

    wm_w = int(img.width * scale)
    wm_h = int(wm.height * (wm_w / wm.width))
    wm = wm.resize((wm_w, wm_h), Image.LANCZOS)

    if opacity < 255:
        r, g, b, a = wm.split()
        a = a.point(lambda p: int(p * opacity / 255))
        wm = Image.merge("RGBA", (r, g, b, a))

    x, y = _calc_position(img.size, wm.size, position)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(wm, (x, y))

    return Image.alpha_composite(img, layer)


# ── 格式轉換 & 儲存 ─────────────────────────────────────────

FORMAT_MAP = {
    "JPG": "JPEG",
    "JPEG": "JPEG",
    "PNG": "PNG",
    "WEBP": "WEBP",
    "BMP": "BMP",
}


def save_image(img: Image.Image, output_path: str, fmt: str = "JPG", quality: int = 85):
    pil_fmt = FORMAT_MAP.get(fmt.upper(), "JPEG")
    if pil_fmt == "JPEG" and img.mode == "RGBA":
        img = img.convert("RGB")
    kwargs = {}
    if pil_fmt in ("JPEG", "WEBP"):
        kwargs["quality"] = quality
    img.save(output_path, format=pil_fmt, **kwargs)


# ── 批次重新命名 ─────────────────────────────────────────────

def generate_new_name(pattern: str, index: int, original: str) -> str:
    stem = Path(original).stem
    return pattern.format(n=index, name=stem, i=index)


# ── 主要處理流程 ─────────────────────────────────────────────

def process_images(file_list: list, settings: dict, output_dir: str, progress_cb=None):
    os.makedirs(output_dir, exist_ok=True)
    total = len(file_list)

    # 嘗試註冊 HEIC 支援
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    for idx, filepath in enumerate(file_list):
        try:
            img = Image.open(filepath)
            img = _ensure_rgb(img)

            # 縮放
            if settings.get("resize_enabled"):
                w = settings.get("resize_width", img.width)
                h = settings.get("resize_height", img.height)
                keep = settings.get("resize_keep_ratio", True)
                img = resize_image(img, w, h, keep)

            # 濾鏡
            if settings.get("filter_enabled"):
                img = apply_filters(
                    img,
                    brightness=settings.get("brightness", 1.0),
                    contrast=settings.get("contrast", 1.0),
                    saturation=settings.get("saturation", 1.0),
                    grayscale=settings.get("grayscale", False),
                )

            # 浮水印
            if settings.get("watermark_enabled"):
                wm_type = settings.get("watermark_type", "text")
                pos = settings.get("watermark_position", "右下")
                opa = settings.get("watermark_opacity", 128)
                if wm_type == "text":
                    img = add_text_watermark(
                        img,
                        text=settings.get("watermark_text", ""),
                        position=pos,
                        opacity=opa,
                        font_size=settings.get("watermark_font_size", 36),
                    )
                elif wm_type == "image":
                    wm_path = settings.get("watermark_image_path", "")
                    if wm_path and os.path.isfile(wm_path):
                        img = add_image_watermark(
                            img,
                            watermark_path=wm_path,
                            position=pos,
                            opacity=opa,
                            scale=settings.get("watermark_scale", 0.2),
                        )

            # 輸出格式 & 檔名
            out_fmt = settings.get("output_format", "JPG")
            ext = out_fmt.lower() if out_fmt.upper() != "JPEG" else "jpg"

            if settings.get("rename_enabled") and settings.get("rename_pattern"):
                base = generate_new_name(settings["rename_pattern"], idx + 1, filepath)
            else:
                base = Path(filepath).stem

            out_path = os.path.join(output_dir, f"{base}.{ext}")
            quality = settings.get("quality", 85)
            save_image(img, out_path, fmt=out_fmt, quality=quality)

        except Exception as e:
            print(f"處理失敗: {filepath} — {e}")

        if progress_cb:
            progress_cb(idx + 1, total)
