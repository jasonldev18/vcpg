import logging
import re
from collections.abc import Mapping

MASK = "[redacted]"
KEY_PATTERN = re.compile(r"(?:sk-ant-|github_pat_|ghp_|gho_|ghs_)[A-Za-z0-9_\-]+")
_known: set[str] = set()


def remember(value: str) -> None:
    """Mask this exact value too, even if it does not look like a known key format."""
    _known.add(value)


def forget(value: str) -> None:
    _known.discard(value)


def redact(text: str) -> str:
    for value in sorted(_known, key=len, reverse=True):
        text = text.replace(value, MASK)
    return KEY_PATTERN.sub(MASK, text)


def _clean(arg: object) -> object:
    return arg if isinstance(arg, int | float | None) else redact(str(arg))


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Args are redacted in place, not merged into msg: formatters such as uvicorn's
        # access log unpack record.args themselves.
        record.msg = redact(str(record.msg))
        if isinstance(record.args, Mapping):
            record.args = {k: _clean(v) for k, v in record.args.items()}
        elif record.args:
            record.args = tuple(_clean(a) for a in record.args)
        if record.exc_info:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        if record.stack_info:
            record.stack_info = redact(record.stack_info)
        return True


def install() -> None:
    """Attach the filter to every handler that exists now (root, uvicorn and our own)."""
    loggers = [
        logging.getLogger(),
        *(logging.getLogger(n) for n in logging.root.manager.loggerDict),
    ]
    for handler in {h for lg in loggers for h in lg.handlers}:
        if not any(isinstance(f, RedactFilter) for f in handler.filters):
            handler.addFilter(RedactFilter())
