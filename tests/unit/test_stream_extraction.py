from io import BytesIO

import pytest

from medical_data_crawler.html_extraction import HTMLExtractor
from medical_data_crawler.pdf_extraction import PDFExtractor
from medical_data_crawler.pipeline import detect_media_type


@pytest.mark.parametrize(
    ("data", "html_type", "unknown_type"),
    [
        (b"", "text/html", "application/octet-stream"),
        (b"<p>text</p>", "text/html", "application/octet-stream"),
        (b"%PDF-1.4", "application/pdf", "application/pdf"),
        (b" " * 65535 + b"%PDF-1.4", "application/pdf", "application/pdf"),
        (b"\t\r\n " * 40000 + b"%PDF-1.4", "application/pdf", "application/pdf"),
        (b"\v%PDF-1.4", "text/html", "application/octet-stream"),
        (b"a" * 131072 + b"\x00", "application/octet-stream", "application/octet-stream"),
        (b"GIF89a-synthetic", "application/octet-stream", "application/octet-stream"),
        (b"\x89PNG-synthetic", "application/octet-stream", "application/octet-stream"),
        (b"PK\x03\x04-synthetic", "application/octet-stream", "application/octet-stream"),
        (b"\xff\xd8\xff-synthetic", "application/octet-stream", "application/octet-stream"),
        (b"\xff\xfe<\x00p\x00>\x00", "text/html", "application/octet-stream"),
        (b"\x00\x00\xfe\xff\x00", "text/html", "application/octet-stream"),
    ],
)
def test_stream_format_detection_preserves_routing_and_position(data, html_type, unknown_type):
    class BoundedReader(BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 65536
            return super().read(size)

    for hint, expected in [
        ("text/html", html_type),
        (None, unknown_type),
        ("application/pdf", "application/pdf"),
    ]:
        assert detect_media_type(data, hint) == expected
        with BoundedReader(b"offset" + data) as stream:
            stream.seek(6)
            assert detect_media_type(stream, hint) == expected
            assert stream.tell() == 6


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"<p>one<p>two &amp; three",
        b"<meta charset='utf-8'><p>\xc4\x91</p>",
        "<meta charset='utf-16'><p>Tiếng Việt</p>".encode("utf-16"),
    ],
)
def test_html_stream_and_bytes_have_identical_results(data):
    extractor = HTMLExtractor()
    with BytesIO(data) as stream:
        assert extractor.extract(stream) == extractor.extract(data)
        assert not stream.closed


@pytest.mark.parametrize("case", ["text", "partial", "broken", "no_text"])
def test_pdf_stream_and_bytes_have_identical_results(pdf_bytes, case):
    pages = {
        "text": [[(72, 720, "First")], [(72, 720, "Last")]],
        "partial": [[(72, 720, "First")], b"BT (unterminated"],
        "no_text": [None],
    }
    data = b"%PDF-broken" if case == "broken" else pdf_bytes(pages[case])
    extractor = PDFExtractor()
    with BytesIO(data) as stream:
        assert extractor.extract(stream) == extractor.extract(data)
        assert not stream.closed
