"""Glossary: fixed translations for terms.

Terms with a target are given to the model as required translations, so it
can inflect them or build compounds. Terms with an empty target, or all terms
in strict mode, are replaced by tokens and restored after translation.
"""

import csv
import io
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from .errors import GlossaryError

TOKEN = "__GLOSSARY_{}__"
_RESTORE = re.compile(r"_{1,2}GLOSSARY_(\d+)_{0,2}", re.IGNORECASE)
_HEADERS = {("source", "target"), ("term", "translation"), ("src", "tgt")}


class Glossary:
    """Pairs of source term and target term."""

    def __init__(self, pairs: Union[Dict[str, str], Iterable[Tuple[str, str]]], case_sensitive: bool = False):
        items = pairs.items() if isinstance(pairs, dict) else pairs
        clean: Dict[str, str] = {}
        for source, target in items:
            source = str(source).strip()
            target = str(target).strip() if target is not None else ""
            if not source:
                continue
            clean[source] = target
        # Longest first, so "machine learning" wins over "machine".
        self.terms: List[Tuple[str, str]] = sorted(clean.items(), key=lambda p: (-len(p[0]), p[0]))
        self.case_sensitive = case_sensitive
        self._pattern = self._compile()

    def __len__(self) -> int:
        return len(self.terms)

    def _compile(self) -> Optional["re.Pattern"]:
        if not self.terms:
            return None
        parts = []
        for i, (source, _) in enumerate(self.terms):
            body = re.escape(source)
            if re.match(r"\w", source[0]):
                body = r"(?<!\w)" + body
            if re.match(r"\w", source[-1]):
                body = body + r"(?!\w)"
            parts.append(f"(?P<t{i}>{body})")
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile("|".join(parts), flags)

    def target(self, index: int) -> str:
        """Target term, or the source term if it stays unchanged."""
        source, target = self.terms[index]
        return target or source

    def protect(self, text: str, strict: bool = False) -> Tuple[str, List[int], List[int]]:
        """Prepare text for translation.

        Terms that stay unchanged (or all terms if strict) are replaced with tokens.
        Returns the new text, the token indexes and the indexes of the other found terms.
        """
        if self._pattern is None:
            return text, [], []
        tokens: List[int] = []
        found: List[int] = []

        def repl(match: "re.Match") -> str:
            index = int(match.lastgroup[1:])
            if strict or not self.terms[index][1]:
                if index not in tokens:
                    tokens.append(index)
                return TOKEN.format(index)
            if index not in found:
                found.append(index)
            return match.group(0)

        return self._pattern.sub(repl, text), tokens, found

    def restore(self, text: str) -> str:
        """Replace tokens with the target terms."""
        if not self.terms:
            return text

        def repl(match: "re.Match") -> str:
            index = int(match.group(1))
            if index < len(self.terms):
                return self.target(index)
            return match.group(0)

        return _RESTORE.sub(repl, text)

    def describe(self, indexes: Iterable[int]) -> str:
        """Prompt lines for the tokens used in a request."""
        lines = []
        for i in sorted(set(indexes)):
            source = self.terms[i][0]
            lines.append(f"{TOKEN.format(i)} stands for '{source}' and will be replaced with '{self.target(i)}'.")
        return "\n".join(lines)

    def describe_terms(self, indexes: Iterable[int]) -> str:
        """Prompt lines for the required translations used in a request."""
        return "\n".join(f"'{self.terms[i][0]}' -> '{self.terms[i][1]}'" for i in sorted(set(indexes)))

    def missing(self, text: str, indexes: Iterable[int]) -> List[int]:
        """Indexes of terms whose target does not appear in the text.

        The check is lenient. Each word of the target only has to appear with its
        last letters cut off, so inflected forms and compounds count as found.
        """
        haystack = text.casefold()
        result = []
        for i in indexes:
            words = self.terms[i][1].casefold().split()
            if not all(_stem(word) in haystack for word in words):
                result.append(i)
        return result


def _stem(word: str) -> str:
    if len(word) >= 6:
        return word[:-2]
    if len(word) == 5:
        return word[:-1]
    return word


def load_glossary(source: Union[str, Path, Dict[str, str], "Glossary", None], case_sensitive: bool = False) -> Optional[Glossary]:
    """Build a glossary from a path, a dict or an existing glossary."""
    if source is None:
        return None
    if isinstance(source, Glossary):
        return source
    if isinstance(source, dict):
        return Glossary(source, case_sensitive)
    path = Path(source)
    if not path.is_file():
        raise GlossaryError(f"Glossary file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise GlossaryError(f"Glossary file is not UTF-8: {path}")
    if path.suffix.lower() == ".json":
        pairs = _from_json(text, path)
    else:
        pairs = _from_table(text, path)
    return Glossary(pairs, case_sensitive)


def _from_json(text: str, path: Path) -> List[Tuple[str, str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GlossaryError(f"Glossary file {path} is not valid JSON: {exc}")
    if isinstance(data, dict):
        return [(str(k), "" if v is None else str(v)) for k, v in data.items()]
    if isinstance(data, list):
        pairs = []
        for entry in data:
            if isinstance(entry, dict) and "source" in entry:
                pairs.append((str(entry["source"]), str(entry.get("target") or "")))
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                pairs.append((str(entry[0]), str(entry[1] or "")))
            else:
                raise GlossaryError(f"Glossary file {path} has an invalid entry: {entry!r}")
        return pairs
    raise GlossaryError(f"Glossary file {path} must contain an object or a list.")


def _from_table(text: str, path: Path) -> List[Tuple[str, str]]:
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return []
    if path.suffix.lower() == ".tsv":
        delimiter = "\t"
    else:
        try:
            delimiter = csv.Sniffer().sniff(lines[0], delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","
    pairs = []
    for row in csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter):
        if not row or not row[0].strip():
            continue
        if len(row) > 2:
            raise GlossaryError(f"Glossary file {path} has a row with more than two columns: {row!r}")
        pairs.append((row[0], row[1] if len(row) > 1 else ""))
    if pairs and (pairs[0][0].strip().lower(), pairs[0][1].strip().lower()) in _HEADERS:
        pairs = pairs[1:]
    return pairs
