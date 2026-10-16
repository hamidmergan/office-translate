class TranslateError(Exception):
    """Base class of all errors in this package."""


class ConfigError(TranslateError):
    """A setting is missing or a value is invalid."""


class GlossaryError(TranslateError):
    """The glossary file cannot be read."""


class UnsupportedFileError(TranslateError):
    """The file type is not supported or the file cannot be read."""


class ModelError(TranslateError):
    """The model server did not answer, or the answer was unusable."""
