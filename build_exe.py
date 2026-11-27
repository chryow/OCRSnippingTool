"""Cross-platform PyInstaller build script for OCRSnippingTool.

Builds standalone executables for Windows (.exe), macOS (.app), and Linux with
an auto-generated application icon and bundled ONNX / PyQt6 dependencies.

Usage:
    pip install pyinstaller
    python build_exe.py                  # Default: onedir bundle (fast startup / macOS .app)
    python build_exe.py --onefile        # Single portable executable (great for Windows .exe)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def generate_app_icons(asset_dir: Path) -> tuple[Path, Path]:
    """Generate crisp PNG and multi-resolution ICO icons matching the in-app theme."""
    asset_dir.mkdir(parents=True, exist_ok=True)
    png_path = asset_dir / "icon.png"
    ico_path = asset_dir / "icon.ico"

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded indigo gradient-like card
    margin = 16
    radius = 112
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=(99, 102, 241, 255),
        outline=(129, 140, 248, 255),
        width=8,
    )

    # Crisp white crop corner brackets
    m = 96
    arm = 84
    w = 28
    white = (255, 255, 255, 255)
    # Top-left
    draw.line([(m, m), (m + arm, m)], fill=white, width=w)
    draw.line([(m, m), (m, m + arm)], fill=white, width=w)
    # Top-right
    draw.line([(size - m, m), (size - m - arm, m)], fill=white, width=w)
    draw.line([(size - m, m), (size - m, m + arm)], fill=white, width=w)
    # Bottom-left
    draw.line([(m, size - m), (m + arm, size - m)], fill=white, width=w)
    draw.line([(m, size - m), (m, size - m - arm)], fill=white, width=w)
    # Bottom-right
    draw.line([(size - m, size - m), (size - m - arm, size - m)], fill=white, width=w)
    draw.line([(size - m, size - m), (size - m, size - m - arm)], fill=white, width=w)

    # Center "A" motif
    try:
        font = ImageFont.load_default(size=210)
    except TypeError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "A", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1]
    draw.text((tx, ty), "A", fill=white, font=font)

    img.save(png_path, format="PNG")
    img.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return png_path, ico_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build standalone OCRSnippingTool executable.")
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Bundle into a single portable executable file.",
    )
    parser.add_argument(
        "--name",
        default="OCRSnippingTool",
        help="Output application name (default: OCRSnippingTool).",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent
    entry = root / "ocr_snip" / "__main__.py"
    png_icon, ico_icon = generate_app_icons(root / "build" / "icons")

    if sys.platform == "win32":
        pynput_backend = "pynput.keyboard._win32"
        icon_arg = str(ico_icon)
    elif sys.platform == "darwin":
        pynput_backend = "pynput.keyboard._darwin"
        icon_arg = str(png_icon)
    else:
        pynput_backend = "pynput.keyboard._xorg"
        icon_arg = str(png_icon)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        args.name,
        "--onefile" if args.onefile else "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths",
        str(root),
        "--icon",
        icon_arg,
        "--collect-all",
        "rapidocr",
        "--collect-all",
        "onnxruntime",
        "--collect-all",
        "langdetect",
        "--hidden-import",
        pynput_backend,
        "--hidden-import",
        "pynput.mouse._win32"
        if sys.platform == "win32"
        else "pynput.mouse._darwin"
        if sys.platform == "darwin"
        else "pynput.mouse._xorg",
        str(entry),
    ]

    if sys.platform == "darwin":
        cmd.extend(["--osx-bundle-identifier", "com.chryow.ocrsnippingtool"])

    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
