# office-translate

A lightweight Python utility for translating Office documents and text files with a model of your choice. Only the text is translated. Fonts, bold and italic, links, tables, layouts and images stay as they are. A glossary keeps fixed terms consistent.

office-translate currently supports:

- Word (DOCX, DOCM)
- PowerPoint (PPTX, PPTM)
- Markdown (MD)
- Plain text (TXT)

## Prerequisites

- Python 3.9 or newer
- A server with an OpenAI-compatible API and a text model (for example Ollama, vLLM, LM Studio, a university server or a cloud provider). A vision model is not needed.
- An API key is optional. Many self-hosted servers do not need one.

If you run your own model, your documents stay on your own network. Nothing leaves your machine or data center.

## Installation

```bash
pip install office-translate
```

Alternatively, you can install it from the source:

```bash
git clone https://github.com/hamidmergan/office-translate.git
cd office-translate
pip install .
```

## Usage

### Command-Line

Translate a file into German:

```bash
office-translate report.docx --to German --base-url http://localhost:11434/v1 --model your-model
```

This writes `report.german.docx` next to `report.docx`. The language can be a name or a code (`--to de` gives `report.de.docx`). Several files work the same way:

```bash
office-translate report.docx slides.pptx notes.md --to German --base-url http://localhost:11434/v1 --model your-model
```

Use a glossary, set the source language or add instructions for the model:

```bash
office-translate slides.pptx --to French --from English --glossary terms.csv \
  --instructions "Formal tone, audience is engineers" \
  --base-url http://localhost:11434/v1 --model your-model
```

Use `-o` to choose the output. For one file it is a file, for several files it is a folder:

```bash
office-translate report.docx -o out/bericht.docx --to German --base-url http://localhost:11434/v1 --model your-model
office-translate a.docx b.pptx -o out/ --to German --base-url http://localhost:11434/v1 --model your-model
```

If the target already exists, a number is added (`report.german-1.docx`). A file named explicitly with `-o` is overwritten. The input file is never changed. Errors appear on stderr. The exit code is 1 if at least one file failed.

### Python API

```python
from office_translate import translate_file

out = translate_file(
    "report.docx",
    target_lang="German",
    glossary="terms.csv",
    base_url="http://localhost:11434/v1",
    model="your-model",
)
print(out)  # report.german.docx
```

For many files, create a `Translator` once and reuse it:

```python
from office_translate import Translator

translator = Translator("German", glossary={"invoice": "Rechnung"}, base_url=..., model=...)
for name in ["a.docx", "b.pptx"]:
    translator.translate_file(name)
```

Plain strings work too:

```python
from office_translate import translate_text

translate_text(["Good morning", "Thank you"], target_lang="Spanish", base_url=..., model=...)
```

### Glossary

A glossary is a file with two columns, source term and target term:

```csv
source,target
invoice,Rechnung
machine learning,maschinelles Lernen
Acme Cloud,
```

- CSV with comma or semicolon, TSV, or JSON (`{"invoice": "Rechnung"}` or a list of `{"source": ..., "target": ...}`)
- A header row (`source,target` or `term,translation`) and lines starting with `#` are ignored
- An empty target keeps the term unchanged, which is useful for product names
- Matching ignores case and only matches whole words. Use `--case-sensitive` to match exact case

The model gets the glossary terms as required translations. It may inflect them and build compounds, so "maschinelles Lernen" can become "des maschinellen Lernens" and "Rechnung" can become "Rechnungsprozess". Terms with an empty target are replaced by placeholders, so the model cannot change them.

After translation, each paragraph is checked for its glossary terms. If a term is missing, the paragraph is translated once more with a reminder. If it is still missing, a warning is printed.

Use `--strict-glossary` (`strict_glossary=True` in Python) to replace all terms with placeholders. The terms then appear exactly as written, but they are not inflected.

### Settings

Order: argument, then environment variable, then default.

| Argument / flag | Environment variable | Default |
| --- | --- | --- |
| `base_url` / `--base-url` | `OFFICE_TRANSLATE_BASE_URL` | none, required |
| `model` / `--model` | `OFFICE_TRANSLATE_MODEL` | none, required |
| `api_key` / `--api-key` | `OFFICE_TRANSLATE_API_KEY` (then `OPENAI_API_KEY`) | optional |
| `max_file_mb` / `--max-file-mb` | `OFFICE_TRANSLATE_MAX_FILE_MB` | 100 |
| `batch_size` / `--batch-size` | `OFFICE_TRANSLATE_BATCH_SIZE` | 20 segments |
| `batch_chars` | `OFFICE_TRANSLATE_BATCH_CHARS` | 4000 characters |
| `concurrency` / `--concurrency` | `OFFICE_TRANSLATE_CONCURRENCY` | 4 |
| `timeout` / `--timeout` | `OFFICE_TRANSLATE_TIMEOUT` | 120 seconds |
| `max_retries` | `OFFICE_TRANSLATE_MAX_RETRIES` | 2 |
| `temperature` | `OFFICE_TRANSLATE_TEMPERATURE` | 0.1 |

Paragraphs are sent in batches. Repeated text is translated only once. If a reply is cut off or incomplete, the batch is split and the missing parts are sent again.

## What gets translated

- Word: body, tables, headers, footers, footnotes, endnotes, comments, text boxes and SmartArt
- PowerPoint: slides, tables, grouped shapes, speaker notes, chart labels, SmartArt and free text on layouts and masters (placeholder prompts stay as they are)
- Markdown: text, headings, lists and tables. Front matter, code blocks and indented code stay unchanged

Text that contains no letters, such as numbers or dates, is not sent.

## Limitations

- Quality depends on the chosen model. Check important results.
- Within a paragraph, parts with different formatting are marked for the model. If the model moves them around, the formatting may end up on different words. If the marks come back broken, each part is translated on its own.
- Field codes, equations and tracked deletions are not translated.
- Chart labels are updated in the slide, but the embedded spreadsheet behind the chart is not.
- Excel files are not supported.
- Password protected files are not supported.
- Markdown and text files must be UTF-8.

## Running Tests

```bash
pip install -e ".[test]"
pytest
```

The tests run against a local fake server and need no real model.

## License

MIT
