# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-17

### Changed

- Glossary terms with a target are no longer hidden behind placeholders. The model gets them as required translations and may inflect them or build compounds. Terms with an empty target still use placeholders

### Added

- Check after translation that the glossary terms were used, with one retry and a warning if a term is still missing
- `--strict-glossary` flag and `strict_glossary` option for the old placeholder behaviour

## [0.1.0] - 2026-10-16

### Added

- Translation of DOCX, DOCM, PPTX, PPTM, Markdown and plain text files
- Formatting is kept: runs, links, tables, headers, footers, notes, charts and layouts
- Glossary from CSV, TSV or JSON, with whole word matching and optional case sensitivity
- Batching, deduplication and parallel requests
- Retry of incomplete or cut off model replies
- Command-line tool and Python API
- Works with any OpenAI-compatible server, with or without an API key
