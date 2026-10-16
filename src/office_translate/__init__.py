"""Translate DOCX, PPTX, Markdown and text files while keeping the formatting."""

__version__ = "0.1.0"

from .core import SUPPORTED, translate_file, translate_text
from .errors import ConfigError, GlossaryError, ModelError, TranslateError, UnsupportedFileError
from .glossary import Glossary, load_glossary
from .translator import Translator

__all__ = [
    "__version__",
    "SUPPORTED",
    "Translator",
    "translate_file",
    "translate_text",
    "Glossary",
    "load_glossary",
    "TranslateError",
    "ConfigError",
    "GlossaryError",
    "ModelError",
    "UnsupportedFileError",
]
