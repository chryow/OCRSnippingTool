"""Smart multilingual text formatting helpers (e.g. PDF/article paragraph unwrapping)."""

from __future__ import annotations

import re

_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*•▪▸‣]|(?:\d+|[a-zA-Z])[.)])\s+")


def _is_no_space_script(ch: str) -> bool:
    """Return True if `ch` belongs to a script that doesn't separate words with spaces."""
    if not ch:
        return False
    cp = ord(ch)
    return (
        (0x4E00 <= cp <= 0x9FFF)      # CJK Unified Ideographs
        or (0x3400 <= cp <= 0x4DBF)   # CJK Ext A
        or (0x3040 <= cp <= 0x30FF)   # Hiragana & Katakana
        or (0x0E00 <= cp <= 0x0E7F)   # Thai
        or (0x0E80 <= cp <= 0x0EFF)   # Lao
        or (0x1780 <= cp <= 0x17FF)   # Khmer
        or (0x1000 <= cp <= 0x109F)   # Myanmar
    )


def unwrap_paragraphs(text: str) -> str:
    """Merge hard-wrapped OCR lines into flowing paragraphs while keeping structure.

    Preserves:
    - Blank-line paragraph boundaries
    - Bulleted / numbered list items
    - Hyphenated word joins across line breaks (e.g. `multi-\\nlingual` -> `multilingual`)
    - Natural CJK/Japanese/Thai joining without injecting extra ASCII spaces
    """
    if not text or not text.strip():
        return text

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_blocks = re.split(r"\n\s*\n+", normalized)
    output_blocks: list[str] = []

    for block in raw_blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        merged_lines: list[str] = []
        current = lines[0]

        for nxt in lines[1:]:
            if _LIST_ITEM_RE.match(nxt) or _LIST_ITEM_RE.match(current):
                merged_lines.append(current)
                current = nxt
                continue

            # Rejoin hyphenated line-break word splits (Latin/Cyrillic letters)
            if (
                len(current) >= 2
                and current.endswith("-")
                and current[-2].isalpha()
                and nxt[0].islower()
            ):
                current = current[:-1] + nxt
            elif _is_no_space_script(current[-1]) and _is_no_space_script(nxt[0]):
                current = current + nxt
            else:
                current = f"{current} {nxt}"

        merged_lines.append(current)
        output_blocks.append("\n".join(merged_lines))

    return "\n\n".join(output_blocks)
