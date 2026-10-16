"""Sends text segments to an OpenAI-compatible model in batches."""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from openai import OpenAI, OpenAIError

from . import config
from .errors import ConfigError, ModelError
from .glossary import Glossary, load_glossary

_ITEM = re.compile(r'<s id="?(\d+)"?>(.*?)</s>', re.DOTALL)
_STRAY = re.compile(r'</?s(?:\s+id="?\d+"?)?>')
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_LETTER = re.compile(r"[^\W\d_]")


def make_client(settings: config.Settings) -> OpenAI:
    return OpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    )


def _split_space(text: str) -> Tuple[str, str, str]:
    core = text.strip()
    if not core:
        return text, "", ""
    start = text.index(core)
    return text[:start], core, text[start + len(core):]


class Translator:
    """Translates text with a fixed target language, glossary and model.

    Create it once and reuse it for many files.
    """

    def __init__(
        self,
        target_lang: str,
        source_lang: Optional[str] = None,
        glossary: Union[str, Path, Dict[str, str], Glossary, None] = None,
        instructions: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Optional[OpenAI] = None,
        case_sensitive: bool = False,
        **limits,
    ):
        if not target_lang or not target_lang.strip():
            raise ConfigError("target_lang is required, for example 'German' or 'de'.")
        self.target_lang = target_lang.strip()
        self.source_lang = source_lang.strip() if source_lang and source_lang.strip() else None
        self.instructions = instructions.strip() if instructions and instructions.strip() else None
        self.settings = config.resolve(base_url=base_url, model=model, api_key=api_key, **limits)
        self.client = client or make_client(self.settings)
        self.glossary = load_glossary(glossary, case_sensitive)

    def translate_file(self, path: Union[str, Path], output: Union[str, Path, None] = None) -> Path:
        """Translate a file and return the path of the written copy."""
        from .core import process_file

        return process_file(self, Path(path), Path(output) if output is not None else None)

    def translate(self, texts: Sequence[str]) -> List[str]:
        """Translate a list of strings. Order and surrounding whitespace are kept."""
        results = list(texts)
        unique: Dict[str, List[int]] = {}
        parts: List[Tuple[str, str]] = []
        for i, text in enumerate(texts):
            lead, core, trail = _split_space(text)
            parts.append((lead, trail))
            if core and _LETTER.search(core):
                unique.setdefault(core, []).append(i)
        if not unique:
            return results

        cores = list(unique)
        translated = self._translate_unique(cores)
        for core, new in zip(cores, translated):
            for i in unique[core]:
                lead, trail = parts[i]
                results[i] = lead + new + trail
        return results

    def _translate_unique(self, cores: List[str]) -> List[str]:
        items = []
        for core in cores:
            if self.glossary is not None:
                items.append(self.glossary.protect(core))
            else:
                items.append((core, []))

        chunks = self._chunks(items)
        with ThreadPoolExecutor(max_workers=self.settings.concurrency) as pool:
            done = list(pool.map(self._run_chunk, chunks))

        out: List[str] = []
        for chunk_result in done:
            out.extend(chunk_result)
        final = []
        for core, new in zip(cores, out):
            if self.glossary is not None:
                new = self.glossary.restore(new)
            new = new.strip()
            final.append(new if new else core)
        return final

    def _chunks(self, items: List[Tuple[str, List[int]]]) -> List[List[Tuple[str, List[int]]]]:
        chunks: List[List[Tuple[str, List[int]]]] = []
        current: List[Tuple[str, List[int]]] = []
        size = 0
        for item in items:
            length = len(item[0])
            if current and (len(current) >= self.settings.batch_size or size + length > self.settings.batch_chars):
                chunks.append(current)
                current, size = [], 0
            current.append(item)
            size += length
        if current:
            chunks.append(current)
        return chunks

    def _run_chunk(self, chunk: List[Tuple[str, List[int]]]) -> List[str]:
        content, cut = self._ask(chunk)
        if cut:
            if len(chunk) == 1:
                raise ModelError(
                    "The model reply was cut off. Raise the output token limit of the server "
                    "or split the text into smaller parts."
                )
            half = len(chunk) // 2
            return self._run_chunk(chunk[:half]) + self._run_chunk(chunk[half:])

        found = {int(m.group(1)): m.group(2) for m in _ITEM.finditer(content)}
        if len(chunk) == 1 and 0 not in found:
            found[0] = _STRAY.sub("", content)

        result = []
        for i, item in enumerate(chunk):
            if i in found:
                result.append(found[i])
            else:
                result.append(self._run_chunk([item])[0])
        return result

    def _ask(self, chunk: List[Tuple[str, List[int]]]) -> Tuple[str, bool]:
        used: List[int] = []
        for _, indexes in chunk:
            used.extend(indexes)
        user = "\n".join(f'<s id="{i}">{text}</s>' for i, (text, _) in enumerate(chunk))
        messages = [
            {"role": "system", "content": self._system_prompt(used)},
            {"role": "user", "content": user},
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                temperature=self.settings.temperature,
            )
        except OpenAIError as exc:
            raise ModelError(f"Request to {self.settings.base_url} failed: {exc}") from exc
        try:
            choice = response.choices[0]
            content = choice.message.content or ""
            cut = choice.finish_reason == "length"
        except (AttributeError, IndexError, TypeError):
            raise ModelError("The server response has an unexpected format.")
        return _THINK.sub("", content), cut

    def _system_prompt(self, used: List[int]) -> str:
        source = self.source_lang or "the detected source language"
        lines = [
            f"You are a professional translator. Translate each segment from {source} into {self.target_lang}.",
            'Return every segment as <s id="N">translation</s> with the same id, in the same order, and nothing else.',
            "Do not add notes or explanations.",
            "Some segments contain tags like <g1>...</g1>. They mark formatting. "
            "Keep each tag pair around the words it belongs to. Do not add, remove or rename tags.",
            "Keep URLs, e-mail addresses, numbers, code and Markdown syntax unchanged.",
            "If a segment is already in the target language, return it unchanged.",
        ]
        if used and self.glossary is not None:
            lines.append("Keep tokens like __GLOSSARY_0__ exactly as they are. They are glossary terms:")
            lines.append(self.glossary.describe(used))
        if self.instructions:
            lines.append("Additional instructions: " + self.instructions)
        return "\n".join(lines)
