import logging
import re

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


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg, record.args = redact(record.getMessage()), None
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
