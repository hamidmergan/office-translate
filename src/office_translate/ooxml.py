"""Translation of DOCX and PPTX packages.

The zip is read directly. Only text nodes in selected XML parts change.
Everything else is copied byte for byte.
"""

import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from lxml import etree

from .errors import UnsupportedFileError

if TYPE_CHECKING:
    from .translator import Translator

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

_WML = "application/vnd.openxmlformats-officedocument.wordprocessingml."
_PML = "application/vnd.openxmlformats-officedocument.presentationml."
_DML = "application/vnd.openxmlformats-officedocument.drawingml."

# Content type -> mode. "all" translates every paragraph, "free" skips placeholders.
_TYPES = {
    _WML + "document.main+xml": "all",
    _WML + "template.main+xml": "all",
    "application/vnd.ms-word.document.macroEnabled.main+xml": "all",
    "application/vnd.ms-word.template.macroEnabledTemplate.main+xml": "all",
    _WML + "header+xml": "all",
    _WML + "footer+xml": "all",
    _WML + "footnotes+xml": "all",
    _WML + "endnotes+xml": "all",
    _WML + "comments+xml": "all",
    _PML + "slide+xml": "all",
    _PML + "notesSlide+xml": "all",
    _PML + "slideLayout+xml": "free",
    _PML + "slideMaster+xml": "free",
    _DML + "chart+xml": "all",
    _DML + "diagramData+xml": "all",
    "application/vnd.ms-office.drawingml.diagramDrawing+xml": "all",
}

# Elements inside a Word paragraph that end a text group.
_W_BREAKS = {
    W + name
    for name in (
        "tab", "br", "cr", "ptab", "drawing", "pict", "object", "fldChar",
        "footnoteReference", "endnoteReference", "commentReference", "sym",
        "noBreakHyphen", "separator", "continuationSeparator", "footnoteRef", "endnoteRef",
    )
} | {MC + "AlternateContent"}

# Elements inside a Word paragraph that hold no visible text to translate.
_W_SKIP = {W + name for name in ("rPr", "pPr", "del", "moveFrom", "instrText", "delText", "softHyphen", "p")}

_NOISE_ATTRS = {"lang", "altLang", "dirty", "err", "noProof", "smtClean", "smtId", "bmk"}
_NOISE_CHILDREN = {W + "lang", W + "noProof"}

_TAG = re.compile(r"(</?g\d+>)")
_TAG_PARTS = re.compile(r"<(/?)g(\d+)>")

_BREAK = None


def _parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True)


def _rpr_key(rpr) -> bytes:
    if rpr is None:
        return b""
    rpr = etree.fromstring(etree.tostring(rpr), _parser())
    for el in rpr.iter():
        for attr in list(el.attrib):
            if etree.QName(attr).localname in _NOISE_ATTRS:
                del el.attrib[attr]
    for child in list(rpr):
        if child.tag in _NOISE_CHILDREN:
            rpr.remove(child)
    return etree.tostring(rpr, method="c14n")


def _word_pieces(paragraph) -> list:
    pieces: list = []

    def walk(el, ancestors: tuple) -> None:
        for child in el:
            tag = child.tag
            if not isinstance(tag, str):
                continue
            if tag == W + "t":
                run = child.getparent()
                rpr = run.find(W + "rPr") if run.tag == W + "r" else None
                pieces.append((child, (_rpr_key(rpr), ancestors)))
            elif tag in _W_BREAKS:
                pieces.append(_BREAK)
            elif tag in _W_SKIP:
                continue
            elif tag == W + "r":
                walk(child, ancestors)
            else:
                walk(child, ancestors + (child,))

    walk(paragraph, ())
    return pieces


def _drawing_pieces(paragraph) -> list:
    pieces: list = []
    for child in paragraph:
        tag = child.tag
        if not isinstance(tag, str) or tag in (A + "pPr", A + "endParaRPr"):
            continue
        if tag == A + "r":
            t = child.find(A + "t")
            if t is not None:
                pieces.append((t, (_rpr_key(child.find(A + "rPr")), ())))
        else:
            pieces.append(_BREAK)
    return pieces


def _groups(pieces: list) -> List[list]:
    groups: List[list] = []
    current: Optional[list] = None
    key = None
    for piece in pieces:
        if piece is _BREAK:
            current = None
            continue
        node, node_key = piece
        if current is not None and node_key == key:
            current.append(node)
        else:
            current = [node]
            key = node_key
            groups.append(current)
    return groups


def _text(group: list) -> str:
    return "".join(node.text or "" for node in group)


def _split_space(text: str) -> Tuple[str, str, str]:
    core = text.strip()
    if not core:
        return text, "", ""
    start = text.index(core)
    return text[:start], core, text[start + len(core):]


class _Segment:
    """One paragraph. Its text groups keep their own formatting."""

    def __init__(self, groups: List[list]):
        self.groups = groups
        self.active = [g for g in groups if _text(g).strip()]

    def source(self) -> str:
        if len(self.active) == 1:
            return _text(self.active[0])
        out = []
        number = 0
        for group in self.groups:
            text = _text(group)
            if not text.strip():
                out.append(text)
                continue
            number += 1
            lead, core, trail = _split_space(text)
            out.append(f"{lead}<g{number}>{core}</g{number}>{trail}")
        return "".join(out)

    def apply(self, translated: str) -> bool:
        """Write a translation back. Returns False if the tags are broken."""
        if len(self.active) == 1:
            _write(self.active[0], translated)
            return True
        parsed = _parse_tags(translated, len(self.active))
        if parsed is None:
            return False
        for number, group in enumerate(self.active, start=1):
            lead, _, trail = _split_space(_text(group))
            _write(group, lead + parsed[number].strip() + trail)
        return True

    def group_sources(self) -> List[str]:
        return [_split_space(_text(g))[1] for g in self.active]

    def apply_groups(self, texts: List[str]) -> None:
        for group, new in zip(self.active, texts):
            lead, _, trail = _split_space(_text(group))
            _write(group, lead + new.strip() + trail)


def _parse_tags(text: str, count: int) -> Optional[Dict[int, str]]:
    result: Dict[int, str] = {}
    order: List[int] = []
    current: Optional[int] = None
    prefix = ""
    for token in _TAG.split(text):
        match = _TAG_PARTS.fullmatch(token)
        if match is None:
            if current is not None:
                result[current] += token
            elif order:
                result[order[-1]] += token
            else:
                prefix += token
            continue
        closing, number = match.group(1) == "/", int(match.group(2))
        if closing:
            if current != number:
                return None
            current = None
        else:
            if current is not None or number in result:
                return None
            result[number] = prefix
            prefix = ""
            order.append(number)
            current = number
    if current is not None or set(result) != set(range(1, count + 1)):
        return None
    return result


def _write(group: list, text: str) -> None:
    first = group[0]
    first.text = text
    if first.tag == W + "t":
        first.set(XML_SPACE, "preserve")
    for node in group[1:]:
        node.text = ""


def _in_placeholder(paragraph) -> bool:
    for shape in paragraph.iterancestors(P + "sp"):
        return shape.find(f"{P}nvSpPr/{P}nvPr/{P}ph") is not None
    return False


def _segments(root, mode: str) -> List[_Segment]:
    segments = []
    for el in root.iter(W + "p", A + "p", C + "v"):
        if el.tag == W + "p":
            pieces = _word_pieces(el)
        elif el.tag == A + "p":
            if mode == "free" and _in_placeholder(el):
                continue
            pieces = _drawing_pieces(el)
        else:
            if el.getparent() is None or el.getparent().tag != C + "pt":
                continue
            cache = el.getparent().getparent()
            if cache is None or cache.tag != C + "strCache":
                continue
            pieces = [(el, (b"", ()))]
        segment = _Segment(_groups(pieces))
        if segment.active:
            segments.append(segment)
    return segments


def _content_types(data: bytes) -> Tuple[Dict[str, str], Dict[str, str]]:
    root = etree.fromstring(data, _parser())
    overrides = {}
    defaults = {}
    for el in root:
        if el.tag == CT + "Override":
            overrides[el.get("PartName", "").lstrip("/").lower()] = el.get("ContentType", "")
        elif el.tag == CT + "Default":
            defaults[el.get("Extension", "").lower()] = el.get("ContentType", "")
    return overrides, defaults


def translate_package(src: Path, dst: Path, translator: "Translator") -> None:
    """Translate a DOCX or PPTX file from src and write the result to dst."""
    try:
        with zipfile.ZipFile(src) as zin:
            parts = _load_parts(src, zin)
            segments: List[_Segment] = []
            for root, mode in parts.values():
                segments.extend(_segments(root, mode))
            _translate_segments(segments, translator)
            with zipfile.ZipFile(dst, "w") as zout:
                for info in zin.infolist():
                    if info.filename in parts:
                        root = parts[info.filename][0]
                        data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
                    else:
                        data = zin.read(info)
                    zout.writestr(info, data)
    except zipfile.BadZipFile:
        raise UnsupportedFileError(
            f"{src.name} is not a valid Office Open XML file. Password protected files are not supported."
        )


def _load_parts(src: Path, zin: zipfile.ZipFile) -> Dict[str, Tuple[object, str]]:
    names = zin.namelist()
    if "[Content_Types].xml" not in names:
        raise UnsupportedFileError(f"{src.name} has no [Content_Types].xml and is not an Office Open XML file.")
    try:
        overrides, defaults = _content_types(zin.read("[Content_Types].xml"))
    except etree.XMLSyntaxError as exc:
        raise UnsupportedFileError(f"{src.name}: [Content_Types].xml is not valid XML: {exc}")
    parts = {}
    for name in names:
        key = name.lower()
        content_type = overrides.get(key)
        if content_type is None:
            content_type = defaults.get(key.rsplit(".", 1)[-1], "")
        mode = _TYPES.get(content_type)
        if mode is None:
            continue
        try:
            parts[name] = (etree.fromstring(zin.read(name), _parser()), mode)
        except etree.XMLSyntaxError as exc:
            raise UnsupportedFileError(f"{src.name}: part {name} is not valid XML: {exc}")
    return parts


def _translate_segments(segments: List[_Segment], translator: "Translator") -> None:
    if not segments:
        return
    translated = translator.translate([s.source() for s in segments])
    failed = [s for s, new in zip(segments, translated) if not s.apply(new)]
    if not failed:
        return
    # Fallback for broken tags: each group on its own.
    flat: List[str] = []
    for segment in failed:
        flat.extend(segment.group_sources())
    results = translator.translate(flat)
    pos = 0
    for segment in failed:
        count = len(segment.active)
        segment.apply_groups(results[pos:pos + count])
        pos += count
