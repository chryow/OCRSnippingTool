"""Helper script to bundle OCRSnippingTool into a standalone executable via PyInstaller.

Usage:
    pip install pyinstaller
    python build_exe.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    entry = root / "ocr_snip" / "__main__.py"

    if sys.platform == "win32":
        pynput_backend = "pynput.keyboard._win32"
    elif sys.platform == "darwin":
        pynput_backend = "pynput.keyboard._darwin"
    else:
        pynput_backend = "pynput.keyboard._xorg"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "OCRSnippingTool",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--collect-all",
        "rapidocr",
        "--collect-all",
        "onnxruntime",
        "--collect-all",
        "langdetect",
        "--hidden-import",
        pynput_backend,
        str(entry),
    ]

    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
