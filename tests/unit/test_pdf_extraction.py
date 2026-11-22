import pytest
from pypdf._page import PageObject

from medical_data_crawler.pdf_extraction import PDFExtractor


def test_real_text_layer_and_metadata(pdf_bytes):
    data = pdf_bytes(
        [[(72, 720, "Synthetic text (one)."), (72, 700, "Second line.")]],
        metadata={"/Title": "Fixture", "/Author": "Fixture Author", "/CreationDate": "D:20260101"},
    )
    result = PDFExtractor().extract(data)
    assert result.status == "success"
    assert "Synthetic text (one)." in result.blocks[0].text
    assert result.blocks[0].text.index("Synthetic") < result.blocks[0].text.index("Second")
    assert result.metadata == dict(
        title="Fixture", language=None, authors=["Fixture Author"], published_on=None
    )
    assert result.page_count == 1
    assert result.pages[0].page_number == 1
    assert (result.pages[0].block_start, result.pages[0].block_end) == (0, len(result.blocks))
    assert "pdf_layout_unverified" in result.warnings
    assert result.errors == ()


def test_multiple_pages_and_repeated_content_keep_boundaries(pdf_bytes):
    data = pdf_bytes([[(72, 720, "Same")], [(72, 720, "Same")], [(72, 720, "Last")]])
    result = PDFExtractor().extract(data)
    assert result.status == "success"
    assert [b.text for b in result.blocks] == ["Same", "Same", "Last"]
    assert [(p.page_number, p.block_start, p.block_end) for p in result.pages] == [
        (1, 0, 1),
        (2, 1, 2),
        (3, 2, 3),
    ]


def test_no_extractable_text_never_invents_scan_content(pdf_bytes):
    result = PDFExtractor().extract(pdf_bytes([None, None]))
    assert result.status == "failed"
    assert result.blocks == ()
    assert result.errors == ("no_extractable_text",)
    assert [p.status for p in result.pages] == ["no_text", "no_text"]
    assert "pdf_page_2_no_text" in result.warnings


def test_text_and_empty_pages_are_partial(pdf_bytes):
    result = PDFExtractor().extract(pdf_bytes([[(72, 720, "First")], None, [(72, 720, "Third")]]))
    assert result.status == "partial"
    assert [b.text for b in result.blocks] == ["First", "Third"]
    assert [(p.block_start, p.block_end) for p in result.pages] == [(0, 1), (1, 1), (1, 2)]
    assert "pdf_page_2_no_text" in result.warnings


@pytest.mark.parametrize("data", [b"", b"not a PDF", b"%PDF-1.4\ncorrupt\n%%EOF"])
def test_corrupt_pdf_fails_safely(data):
    result = PDFExtractor().extract(data)
    assert result.status == "failed"
    assert result.blocks == ()
    assert result.errors == ("pdf_read_error",)


def test_real_damaged_page_does_not_hide_other_pages(pdf_bytes):
    data = pdf_bytes([[(72, 720, "First")], b"BT /F1 12 Tf (unterminated", [(72, 720, "Third")]])
    result = PDFExtractor().extract(data)
    assert result.status == "partial"
    assert [b.text for b in result.blocks] == ["First", "Third"]
    assert [p.status for p in result.pages] == ["success", "failed", "success"]
    assert result.errors == ("pdf_page_2_error",)
    assert "pdf_page_2_incomplete" in result.warnings


def test_page_access_failure_is_isolated(pdf_bytes, monkeypatch):
    original = PageObject.extract_text

    def fail_second(self, *args, **kwargs):
        if self.page_number == 1:
            raise ValueError("secret page content")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PageObject, "extract_text", fail_second)
    result = PDFExtractor().extract(pdf_bytes([[(72, 720, "First")], [(72, 720, "Second")]]))
    assert result.status == "partial"
    assert result.errors == ("pdf_page_2_error",)
    assert "secret" not in repr(result)


def test_encrypted_pdf_is_explicitly_rejected(pdf_bytes):
    result = PDFExtractor().extract(pdf_bytes([[(72, 720, "Hidden")]], encrypt=True))
    assert result.status == "failed"
    assert result.errors == ("pdf_encrypted",)


def test_columns_or_table_origins_are_warned_without_reordering(pdf_bytes):
    result = PDFExtractor().extract(pdf_bytes([[(72, 720, "Left"), (320, 720, "Right")]]))
    assert result.status == "partial"
    assert "pdf_page_1_complex_layout" in result.warnings
    assert result.pages[0].status == "partial"
    assert "Left" in result.blocks[0].text and "Right" in result.blocks[0].text


def test_paragraph_boundaries_do_not_join_pages(pdf_bytes, monkeypatch):
    monkeypatch.setattr(
        PageObject, "extract_text", lambda *a, **k: "One\nline.\n\nTwo.\r\n\r\nThree."
    )
    result = PDFExtractor().extract(pdf_bytes([None, None]))
    assert [b.text for b in result.blocks] == ["One\nline.", "Two.", "Three."] * 2
    assert [(p.block_start, p.block_end) for p in result.pages] == [(0, 3), (3, 6)]
