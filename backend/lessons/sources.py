"""Lesson sources: parse, split into passages, embed, store (SPEC 9.1, ARCHITECTURE section 9)."""

import io
import ipaddress
import re
import socket
from functools import cache
from html.parser import HTMLParser
from typing import ClassVar, Literal
from urllib.parse import urlparse

import httpx2 as httpx
import numpy as np
from fastembed import TextEmbedding
from pypdf import PdfReader

from backend import db
from backend.errors import Conflict
from backend.paths import vcpg_home

Kind = Literal["trusted", "community"]
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_BYTES = 50 * 1024 * 1024  # SECURITY section 8
MIN_WORDS, MAX_WORDS = 200, 400


@cache
def _model() -> TextEmbedding:
    return TextEmbedding(MODEL, cache_dir=str(vcpg_home() / "models"))


def embed(texts: list[str]) -> list[np.ndarray]:
    return [np.asarray(v, dtype=np.float32) for v in _model().embed(texts)]


def split(text: str) -> list[str]:
    """Passages of about 200 to 400 words, cut at heading or paragraph boundaries."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n|\n(?=#)", text) if b.strip()]
    passages: list[str] = []
    current: list[str] = []
    for block in blocks:
        words = block.split()
        while len(words) > MAX_WORDS:  # one huge paragraph: cut it at the word limit
            passages.append(" ".join(words[:MAX_WORDS]))
            words = words[MAX_WORDS:]
        size = sum(len(b.split()) for b in current)
        if current and size + len(words) > MAX_WORDS and size >= MIN_WORDS // 2:
            passages.append("\n\n".join(current))
            current = []
        current.append(" ".join(words))
    if current:
        if passages and sum(len(b.split()) for b in current) < MIN_WORDS // 2:
            passages[-1] += "\n\n" + "\n\n".join(current)  # a short tail joins the last passage
        else:
            passages.append("\n\n".join(current))
    return passages


class _Text(HTMLParser):
    """Visible text, preferring <main> or <article> over page chrome."""

    SKIP: ClassVar = {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg"}
    BLOCK: ClassVar = {
        "p",
        "div",
        "li",
        "br",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "tr",
        "section",
    }

    def __init__(self) -> None:
        super().__init__()
        self.skipping = 0
        self.main_depth = 0
        self.all: list[str] = []
        self.main: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skipping += 1
        if tag in ("main", "article"):
            self.main_depth += 1
        if tag in self.BLOCK:
            self.all.append("\n\n" if tag != "br" else "\n")
            if self.main_depth:
                self.main.append("\n\n")
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            self.all.append("# ")
            if self.main_depth:
                self.main.append("# ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        if tag in ("main", "article") and self.main_depth:
            self.main_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.all.append(data)
            if self.main_depth:
                self.main.append(data)

    def text(self) -> str:
        raw = "".join(self.main) if len("".join(self.main).split()) > 100 else "".join(self.all)
        return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", raw)).strip()


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    return parser.text()


def pdf_to_text(data: bytes) -> str:
    return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)


def _public(url: str) -> None:
    """Only http(s) to public addresses: never this machine or the local network."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise Conflict("Only http and https links can be added.")
    for info in socket.getaddrinfo(parsed.hostname, None):
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
        ):
            raise Conflict("Links to this computer or the local network cannot be added.")


def fetch(url: str) -> str:
    _public(url)
    with httpx.Client(follow_redirects=False, timeout=30) as client:
        reply = client.get(url, headers={"User-Agent": "VCPG lesson sources"})
    if reply.status_code != 200:
        raise Conflict(f"Fetching {url} failed with status {reply.status_code}.")
    if len(reply.content) > MAX_BYTES:
        raise Conflict("That page is larger than 50 MB.")
    if "pdf" in reply.headers.get("content-type", ""):
        return pdf_to_text(reply.content)
    return (
        html_to_text(reply.text) if "html" in reply.headers.get("content-type", "") else reply.text
    )


def add(title: str, text: str, url_or_path: str, kind: Kind, added_by: str) -> int:
    passages = split(text)
    if not passages:
        raise Conflict("No readable text was found in that source.")
    vectors = embed(passages)
    with db.session() as conn:
        source_id = conn.execute(
            "INSERT INTO sources (kind, title, url_or_path, added_by) VALUES (?, ?, ?, ?)",
            (kind, title, url_or_path, added_by),
        ).lastrowid
        conn.executemany(
            "INSERT INTO passages (source_id, text, embedding, position) VALUES (?, ?, ?, ?)",
            [
                (source_id, p, v.tobytes(), i)
                for i, (p, v) in enumerate(zip(passages, vectors, strict=True))
            ],
        )
    assert source_id is not None
    return source_id


def add_upload(filename: str, data: bytes, kind: Kind) -> int:
    if len(data) > MAX_BYTES:
        raise Conflict("Uploads are limited to 50 MB.")
    if filename.lower().endswith(".pdf"):
        text = pdf_to_text(data)
    elif filename.lower().endswith((".md", ".markdown", ".txt")):
        text = data.decode("utf-8", errors="replace")
    else:
        raise Conflict("Upload a PDF, markdown or text file.")
    return add(filename, text, filename, kind, "user")


def known_urls() -> set[str]:
    with db.session() as conn:
        return {r["url_or_path"] for r in conn.execute("SELECT url_or_path FROM sources")}
