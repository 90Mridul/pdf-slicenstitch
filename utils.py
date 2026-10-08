from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from PIL import Image


def ensure_parent_dir(path: str | os.PathLike[str]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def normalize_pages_list(pages: Iterable[int], total_pages: int) -> list[int]:
    unique = []
    seen = set()
    for p in pages:
        idx = int(p)
        if 0 <= idx < total_pages and idx not in seen:
            seen.add(idx)
            unique.append(idx)
    return unique


def image_to_bytes(img: Image.Image, mode: str = "RGB") -> bytes:
    if img.mode != mode:
        img = img.convert(mode)
    return img.tobytes("raw", mode)


def build_page_label(index: int, total: int) -> str:
    return f"Page {index + 1} / {total}"


def chunk_height_to_percentage(chunk_height: int, usable_height: int) -> float:
    if usable_height <= 0:
        return 0.0
    return (chunk_height / usable_height) * 100.0


def format_height_status(chunk_height: int, usable_height: int) -> str:
    fill_ratio = chunk_height_to_percentage(chunk_height, usable_height)
    return f"{chunk_height} / {usable_height} px ({fill_ratio:.1f}%)"


def slugify(value: str) -> str:
    name = Path(value).stem
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)
    return safe.strip("_") or "export"
