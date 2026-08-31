from __future__ import annotations

import io
import zipfile

import pytest

from engine.extract import assert_public_http_url, docx_to_text, html_to_text


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "http://localhost/admin",
        "http://127.0.0.1/",
        "https://192.168.1.20/page",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/",
        "http://[::1]/",
        "https://user:pass@example.com/",
    ],
)
def test_blocks_private_and_local_urls(url: str):
    with pytest.raises(ValueError):
        assert_public_http_url(url)


def test_html_to_text_strips_scripts():
    text = html_to_text("<html><script>steal()</script><h1>RASA</h1><p>Score copy.</p></html>")
    assert "steal" not in text
    assert "RASA" in text
    assert "Score copy" in text


def test_docx_to_text_reads_paragraphs():
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>RASA scores AI-native discoverability for marketing teams.</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document)
    text = docx_to_text(buf.getvalue())
    assert "RASA scores" in text
