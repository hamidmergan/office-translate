"""Translation of Markdown and plain text files.

The text is split into blocks at blank lines. Each block is one segment.
In Markdown, front matter and code blocks stay unchanged.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from .errors import UnsupportedFileError

if TYPE_CHECKING:
    from .translator import Translator

_BOM = "﻿"
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LIST = re.compile(r"^([-*+]|\d+[.)])\s")


def _is_blank(line: str) -> bool:
    return not line.strip()


def _is_indented(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


def split_blocks(text: str, markdown: bool) -> List[Tuple[str, bool]]:
    """Split text into (block, translatable) pairs. Joined, they give the input back."""
    lines = text.splitlines(keepends=True)
    blocks: List[Tuple[str, bool]] = []
    i = 0

    if markdown and lines and lines[0].rstrip("\r\n") == "---":
        for j in range(1, len(lines)):
            if lines[j].rstrip("\r\n") in ("---", "..."):
                blocks.append(("".join(lines[: j + 1]), False))
                i = j + 1
                break

    while i < len(lines):
        line = lines[i]
        if _is_blank(line):
            start = i
            while i < len(lines) and _is_blank(lines[i]):
                i += 1
            blocks.append(("".join(lines[start:i]), False))
            continue

        fence = _FENCE.match(line) if markdown else None
        if fence:
            marker = fence.group(1)
            closing = re.compile(r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*$")
            start = i
            i += 1
            while i < len(lines) and not closing.match(lines[i]):
                i += 1
            i = min(i + 1, len(lines))
            blocks.append(("".join(lines[start:i]), False))
            continue

        start = i
        while i < len(lines) and not _is_blank(lines[i]):
            if markdown and i > start and _FENCE.match(lines[i]):
                break
            i += 1
        block = lines[start:i]
        code = markdown and all(_is_indented(b) for b in block) and not _LIST.match(block[0].strip())
        blocks.append(("".join(block), not code))
    return blocks


def translate_text_file(src: Path, dst: Path, translator: "Translator", markdown: bool) -> None:
    """Translate a Markdown or text file from src and write the result to dst."""
    try:
        text = src.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedFileError(f"{src.name} is not UTF-8 encoded.")
    bom = text.startswith(_BOM)
    if bom:
        text = text[1:]

    blocks = split_blocks(text, markdown)
    sources = [block for block, ok in blocks if ok]
    translated = iter(translator.translate(sources))

    out = []
    for block, ok in blocks:
        if not ok:
            out.append(block)
            continue
        new = next(translated)
        if "\r\n" in block:
            new = re.sub(r"(?<!\r)\n", "\r\n", new)
        out.append(new)

    result = (_BOM if bom else "") + "".join(out)
    dst.write_bytes(result.encode("utf-8"))
