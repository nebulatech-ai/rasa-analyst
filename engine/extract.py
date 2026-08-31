from __future__ import annotations

import html
import io
import ipaddress
import re
import socket
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

MAX_CHARS = 12000
MAX_REDIRECTS = 5
BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.google.com",
}

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class _TextParser(HTMLParser):
    skip = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.skip:
            self._skip += 1
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "br", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = html.unescape(data)
        if text.strip():
            self.parts.append(text)


def html_to_text(markup: str) -> str:
    parser = _TextParser()
    parser.feed(markup)
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def docx_to_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml = zf.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ValueError("That file is not a readable Word document.") from e
    root = ET.fromstring(xml)
    paras: list[str] = []
    for p in root.iter(f"{W_NS}p"):
        line = "".join(t.text or "" for t in p.iter(f"{W_NS}t")).strip()
        if line:
            paras.append(line)
    text = "\n".join(paras).strip()
    if len(text) < 20:
        raise ValueError("Word file did not contain enough text.")
    return text


def _ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must start with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("URL must not include credentials.")
    host = parsed.hostname
    if not host:
        raise ValueError("URL is missing a host.")
    lowered = host.strip("[]").lower().rstrip(".")
    if lowered in BLOCKED_HOSTS or lowered.endswith(".localhost"):
        raise ValueError("That URL is not a public page. Paste the text instead.")
    try:
        literal = ipaddress.ip_address(lowered)
    except ValueError:
        literal = None
    if literal is not None and _ip_blocked(literal):
        raise ValueError("That URL is not a public page. Paste the text instead.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError("Could not resolve that host.") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ip_blocked(ip):
            raise ValueError("That URL resolves to a private or local address.")


def _trim(text: str) -> str:
    text = text.strip()
    if len(text) < 40:
        raise ValueError("That URL did not contain enough readable text.")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[truncated for scoring]"
    return text


async def fetch_url(url: str) -> str:
    current = url.strip()
    headers = {"User-Agent": "NebulaRASAAnalyst/0.2 (local GEO workbench)"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False, headers=headers) as client:
        response = None
        for _ in range(MAX_REDIRECTS):
            assert_public_http_url(current)
            response = await client.get(current)
            if response.is_redirect:
                loc = response.headers.get("location")
                if not loc:
                    raise ValueError("Redirect was missing a Location header.")
                current = urljoin(str(response.url), loc)
                continue
            break
        else:
            raise ValueError("Too many redirects.")
        assert response is not None
        response.raise_for_status()
        ctype = response.headers.get("content-type", "")
        body = response.text
        if "html" in ctype or current.endswith((".html", ".htm")) or "<html" in body[:400].lower():
            text = html_to_text(body)
        else:
            text = body
    return _trim(text)
