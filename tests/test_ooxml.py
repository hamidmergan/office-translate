import zipfile

import pytest

from helpers import read_part
from office_translate import UnsupportedFileError, translate_file
from office_translate.ooxml import _parse_tags

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
LAYOUT = "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"


def package(path, parts, types):
    overrides = "".join(f'<Override PartName="/{n}" ContentType="{t}"/>' for n, t in types.items())
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", f'<?xml version="1.0"?><Types xmlns="{CT}">{overrides}</Types>')
        for name, data in parts.items():
            z.writestr(name, data)


def word(body):
    return f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'


def test_parse_tags():
    assert _parse_tags("<g1>A</g1> b <g2>C</g2>", 2) == {1: "A b ", 2: "C"}
    assert _parse_tags("x <g2>C</g2> <g1>A</g1>", 2) == {2: "x C ", 1: "A"}
    assert _parse_tags("<g1>A</g1>", 2) is None
    assert _parse_tags("<g1>A<g2>B</g2></g1>", 2) is None


def test_drop_tags_fallback(tmp_path, server, opts):
    server.mode = "drop_tags"
    body = (
        "<w:p><w:r><w:t xml:space=\"preserve\">plain </w:t></w:r>"
        "<w:r><w:rPr><w:b/></w:rPr><w:t>bold</w:t></w:r></w:p>"
    )
    src = tmp_path / "a.docx"
    package(src, {"word/document.xml": word(body)}, {"word/document.xml": MAIN})
    out = translate_file(src, tmp_path / "b.docx", target_lang="German", **opts)
    xml = read_part(out, "word/document.xml")
    assert ">PLAIN <" in xml
    assert ">BOLD<" in xml
    assert len(server.requests) == 2


def test_tab_splits_groups(tmp_path, server, opts):
    body = "<w:p><w:r><w:t>left</w:t><w:tab/><w:t>right</w:t></w:r></w:p>"
    src = tmp_path / "a.docx"
    package(src, {"word/document.xml": word(body)}, {"word/document.xml": MAIN})
    out = translate_file(src, tmp_path / "b.docx", target_lang="German", **opts)
    xml = read_part(out, "word/document.xml")
    assert "<w:t xml:space=\"preserve\">LEFT</w:t><w:tab/>" in xml
    assert "<g1>left</g1>" in server.user_messages()[0]


def test_deleted_text_and_fields_untouched(tmp_path, opts):
    body = (
        "<w:p><w:del><w:r><w:delText>gone</w:delText></w:r></w:del>"
        "<w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:t>kept</w:t></w:r></w:p>"
    )
    src = tmp_path / "a.docx"
    package(src, {"word/document.xml": word(body)}, {"word/document.xml": MAIN})
    out = translate_file(src, tmp_path / "b.docx", target_lang="German", **opts)
    xml = read_part(out, "word/document.xml")
    assert "gone" in xml
    assert " PAGE " in xml
    assert "KEPT" in xml


def test_layout_free_text_only(tmp_path, opts):
    layout = (
        f'<?xml version="1.0"?><p:sldLayout xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
        "<p:sp><p:nvSpPr><p:cNvPr id=\"2\" name=\"t\"/><p:cNvSpPr/><p:nvPr><p:ph type=\"title\"/></p:nvPr></p:nvSpPr>"
        "<p:txBody><a:p><a:r><a:t>Click to edit</a:t></a:r></a:p></p:txBody></p:sp>"
        "<p:sp><p:nvSpPr><p:cNvPr id=\"3\" name=\"f\"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        "<p:txBody><a:p><a:r><a:t>Confidential</a:t></a:r></a:p></p:txBody></p:sp>"
        "</p:spTree></p:cSld></p:sldLayout>"
    )
    src = tmp_path / "a.pptx"
    package(src, {"ppt/slideLayouts/slideLayout1.xml": layout}, {"ppt/slideLayouts/slideLayout1.xml": LAYOUT})
    out = translate_file(src, tmp_path / "b.pptx", target_lang="German", **opts)
    xml = read_part(out, "ppt/slideLayouts/slideLayout1.xml")
    assert "Click to edit" in xml
    assert "CONFIDENTIAL" in xml


def test_not_a_zip(tmp_path, opts):
    src = tmp_path / "fake.docx"
    src.write_bytes(b"not a zip")
    with pytest.raises(UnsupportedFileError, match="Password"):
        translate_file(src, target_lang="German", **opts)
    assert list(tmp_path.iterdir()) == [src]


def test_invalid_xml(tmp_path, opts):
    src = tmp_path / "bad.docx"
    package(src, {"word/document.xml": "<w:document"}, {"word/document.xml": MAIN})
    with pytest.raises(UnsupportedFileError, match="not valid XML"):
        translate_file(src, target_lang="German", **opts)
