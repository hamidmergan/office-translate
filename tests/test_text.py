import pytest

from office_translate import UnsupportedFileError, translate_file
from office_translate.text import split_blocks

MD = """---
title: Report
---

# Heading

Some *text* with a [link](https://example.org).

```python
print("code stays")
```

    indented code

- item one
- item two
"""


def test_split_roundtrip():
    blocks = split_blocks(MD, markdown=True)
    assert "".join(b for b, _ in blocks) == MD
    raw = [b for b, ok in blocks if not ok and b.strip()]
    assert raw[0].startswith("---")
    assert any("code stays" in b for b in raw)
    assert any("indented code" in b for b in raw)


def test_markdown(tmp_path, opts):
    src = tmp_path / "readme.md"
    src.write_text(MD, encoding="utf-8")
    out = translate_file(src, target_lang="German", **opts)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("---\ntitle: Report\n---\n")
    assert "# HEADING" in text
    assert "SOME *TEXT* WITH A [LINK](HTTPS://EXAMPLE.ORG)." in text
    assert 'print("code stays")' in text
    assert "    indented code" in text
    assert "- ITEM ONE\n- ITEM TWO\n" in text


def test_plain_text_bom_and_crlf(tmp_path, opts):
    src = tmp_path / "notes.txt"
    src.write_bytes("﻿line one\r\nline two\r\n\r\n```not code```\r\n".encode("utf-8"))
    out = translate_file(src, target_lang="German", **opts)
    assert out.read_bytes() == "﻿LINE ONE\r\nLINE TWO\r\n\r\n```NOT CODE```\r\n".encode("utf-8")


def test_not_utf8(tmp_path, opts):
    src = tmp_path / "latin.txt"
    src.write_bytes("caf\xe9".encode("latin-1"))
    with pytest.raises(UnsupportedFileError, match="UTF-8"):
        translate_file(src, target_lang="German", **opts)


def test_unsupported_type(tmp_path, opts):
    src = tmp_path / "data.xlsx"
    src.write_bytes(b"x")
    with pytest.raises(UnsupportedFileError, match="Unsupported"):
        translate_file(src, target_lang="German", **opts)


def test_size_limit(tmp_path, opts):
    src = tmp_path / "big.txt"
    src.write_text("x" * 2_000_000, encoding="utf-8")
    with pytest.raises(UnsupportedFileError, match="limit"):
        translate_file(src, target_lang="German", max_file_mb=1, **opts)


def test_output_must_differ(tmp_path, opts):
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    with pytest.raises(UnsupportedFileError, match="must not be the input"):
        translate_file(src, src, target_lang="German", **opts)


def test_failure_leaves_no_files(tmp_path, server, opts):
    server.mode = "fail"
    src = tmp_path / "a.txt"
    src.write_text("hello", encoding="utf-8")
    with pytest.raises(Exception):
        translate_file(src, target_lang="German", **opts)
    assert list(tmp_path.iterdir()) == [src]
