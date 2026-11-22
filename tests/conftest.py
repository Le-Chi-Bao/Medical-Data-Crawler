"""Synthetic fixtures only; all tests reject network connections and DNS."""

import socket
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must run offline")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture
def pdf_bytes():
    """Generate real PDF objects/xref in memory, without downloaded files or fonts.

    Each page is a sequence of (x, y, text) fragments, or None for a blank page.
    A bytes entry supplies a deliberately malformed stream for error testing.
    """

    def build(pages, *, metadata=None, encrypt=False):
        writer = PdfWriter()
        if metadata:
            writer.add_metadata(metadata)
        for fragments in pages:
            page = writer.add_blank_page(width=612, height=792)
            if fragments is None:
                continue
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            if isinstance(fragments, bytes):
                content = fragments
            else:
                commands = []
                for x, y, text in fragments:
                    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                    commands.append(f"BT /F1 12 Tf 1 0 0 1 {x} {y} Tm ({escaped}) Tj ET")
                content = "\n".join(commands).encode("ascii")
            stream = DecodedStreamObject()
            stream.set_data(content)
            page[NameObject("/Contents")] = writer._add_object(stream)
        if encrypt:
            writer.encrypt("synthetic-test-password")
        output = BytesIO()
        writer.write(output)
        return output.getvalue()

    return build


@pytest.fixture
def image_only_pdf():
    """A synthetic one-pixel image, drawn onto a PDF page with no text operators."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    image = DecodedStreamObject()
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/ColorSpace"): NameObject("/DeviceGray"),
        }
    )
    for key, value in [("/Width", 1), ("/Height", 1), ("/BitsPerComponent", 8)]:
        image[NameObject(key)] = NumberObject(value)
    image.set_data(b"\x80")
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): writer._add_object(image)})}
    )
    content = DecodedStreamObject()
    content.set_data(b"q 100 0 0 100 72 600 cm /Im0 Do Q")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
