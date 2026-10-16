import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .core import output_path
from .errors import TranslateError
from .translator import Translator


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="office-translate",
        description="Translate DOCX, PPTX, Markdown and text files with any OpenAI-compatible model.",
    )
    p.add_argument("files", nargs="+", help="Files to translate (.docx, .pptx, .md, .txt)")
    p.add_argument("--to", required=True, dest="target", help="Target language, e.g. German or de")
    p.add_argument("--from", dest="source", help="Source language. Default: detected by the model")
    p.add_argument("--glossary", help="Glossary file (.csv, .tsv or .json) with source and target terms")
    p.add_argument("--case-sensitive", action="store_true", help="Match glossary terms case-sensitively")
    p.add_argument("--instructions", help="Extra instructions for the model, e.g. tone or audience")
    p.add_argument(
        "-o",
        "--output",
        help="Output file (one input) or output folder (several inputs). "
        "Default: <name>.<lang>.<ext> next to each input",
    )
    p.add_argument("--base-url", help="URL of the OpenAI-compatible server, e.g. http://localhost:11434/v1")
    p.add_argument("--model", help="Name of the model")
    p.add_argument("--api-key", help="API key, if the server requires one")
    p.add_argument("--max-file-mb", type=float)
    p.add_argument("--batch-size", type=int, help="Segments per request")
    p.add_argument("--concurrency", type=int, help="Requests sent in parallel")
    p.add_argument("--timeout", type=float, help="Seconds per request")
    p.add_argument("--version", action="version", version=f"office-translate {__version__}")
    return p


def _free(path: Path) -> Path:
    """Return path, or 'name-1.ext', 'name-2.ext', ... if it already exists."""
    candidate, n = path, 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1
    return candidate


def _target(src: Path, out: Optional[Path], many: bool, lang: str) -> Path:
    generated = output_path(src, lang)
    if out is None:
        return _free(generated)
    if many or out.is_dir():
        return _free(out / generated.name)
    # an explicitly named output file is overwritten
    return out


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    many = len(args.files) > 1
    out = Path(args.output) if args.output else None

    if many and out is not None and out.exists() and not out.is_dir():
        print("Error: with several files, -o must be a folder.", file=sys.stderr)
        return 2

    try:
        translator = Translator(
            args.target,
            args.source,
            args.glossary,
            args.instructions,
            base_url=args.base_url,
            model=args.model,
            api_key=args.api_key,
            case_sensitive=args.case_sensitive,
            max_file_mb=args.max_file_mb,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
            timeout=args.timeout,
        )
    except TranslateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    failed = 0
    for name in args.files:
        src = Path(name)
        try:
            target = _target(src, out, many, translator.target_lang)
            written = translator.translate_file(src, target)
        except (TranslateError, OSError) as exc:
            failed += 1
            print(f"Error: {name}: {exc}", file=sys.stderr)
            continue
        print(f"Wrote {written}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
