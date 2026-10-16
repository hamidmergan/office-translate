"""File handling and the simple module level API."""

import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union

from .errors import UnsupportedFileError
from .glossary import Glossary
from .ooxml import translate_package
from .text import translate_text_file
from .translator import Translator

OFFICE = {".docx", ".docm", ".pptx", ".pptm"}
MARKDOWN = {".md", ".markdown"}
TEXT = {".txt"}
SUPPORTED = OFFICE | MARKDOWN | TEXT


def output_path(src: Union[str, Path], target_lang: str) -> Path:
    """Default output name, for example report.de.docx."""
    src = Path(src)
    slug = re.sub(r"[^a-z0-9]+", "-", target_lang.lower()).strip("-") or "translated"
    return src.with_name(f"{src.stem}.{slug}{src.suffix}")


def process_file(translator: Translator, path: Path, output: Optional[Path] = None) -> Path:
    """Translate one file and write it atomically. Returns the output path."""
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise UnsupportedFileError(
            f"Unsupported file type {path.suffix or '(none)'}. Supported: {', '.join(sorted(SUPPORTED))}"
        )
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > translator.settings.max_file_mb:
        raise UnsupportedFileError(
            f"{path.name} is {size_mb:.1f} MB. The limit is {translator.settings.max_file_mb:g} MB."
        )

    output = output or output_path(path, translator.target_lang)
    if output.resolve() == path.resolve():
        raise UnsupportedFileError("The output file must not be the input file.")
    output.parent.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(dir=output.parent, prefix=".tmp-", suffix=output.suffix, delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)
    try:
        if suffix in OFFICE:
            translate_package(path, tmp_path, translator)
        else:
            translate_text_file(path, tmp_path, translator, markdown=suffix in MARKDOWN)
        os.replace(tmp_path, output)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return output


def translate_file(
    path: Union[str, Path],
    output: Union[str, Path, None] = None,
    *,
    target_lang: str,
    source_lang: Optional[str] = None,
    glossary: Union[str, Path, Dict[str, str], Glossary, None] = None,
    instructions: Optional[str] = None,
    **options,
) -> Path:
    """Translate a DOCX, PPTX, Markdown or text file. Returns the output path."""
    translator = Translator(target_lang, source_lang, glossary, instructions, **options)
    return translator.translate_file(path, output)


def translate_text(
    text: Union[str, List[str]],
    *,
    target_lang: str,
    source_lang: Optional[str] = None,
    glossary: Union[str, Path, Dict[str, str], Glossary, None] = None,
    instructions: Optional[str] = None,
    **options,
) -> Union[str, List[str]]:
    """Translate a string or a list of strings."""
    translator = Translator(target_lang, source_lang, glossary, instructions, **options)
    if isinstance(text, str):
        return translator.translate([text])[0]
    return translator.translate(list(text))
