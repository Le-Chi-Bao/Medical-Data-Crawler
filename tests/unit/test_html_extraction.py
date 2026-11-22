from pathlib import Path

import pytest

from medical_data_crawler.html_extraction import HTMLExtractor


def extract(html):
    return HTMLExtractor().extract(html.encode("utf-8"))


def test_fixture_reading_order_metadata_and_unicode():
    data = (Path(__file__).parents[1] / "fixtures" / "synthetic.html").read_bytes()
    result = HTMLExtractor().extract(data)
    assert result.status == "success"
    assert [(b.kind, b.level, b.text) for b in result.blocks] == [
        ("heading", 1, "Tổn thương da — văn bản tổng hợp"),
        ("paragraph", None, "Đây là dữ liệu kiểm thử & không phải tài liệu y khoa."),
        ("heading", 2, "Danh sách"),
        ("list_item", 1, "Mục một"),
        ("list_item", 2, "Mục lồng nhau"),
        ("list_item", 1, "Phần sau mục con"),
        ("list_item", 1, "Mục hai"),
        ("table", None, "Bảng tổng hợp\nCột A\tCột B\nGiá trị 1\tGiá trị 2"),
        ("paragraph", None, "Kết thúc."),
    ]
    assert result.metadata == dict(
        title="Tài liệu tổng hợp cho kiểm thử",
        language="vi",
        authors=["Synthetic Fixture Author"],
        published_on="2026-01",
    )
    assert result.warnings == ("html_table_text_only",)
    assert result.errors == ()
    assert result.source_encoding.lower() == "utf-8"


def test_all_heading_levels_and_entities():
    result = extract("".join(f"<h{i}>Cấp {i} &lt; &gt; &#273;</h{i}>" for i in range(1, 7)))
    assert [b.level for b in result.blocks] == list(range(1, 7))
    assert result.blocks[0].text == "Cấp 1 < > đ"


def test_nested_inline_text_and_block_boundaries_do_not_duplicate():
    result = extract("Trước<div><p>Văn <b>bản <em>lồng</em></b>.</p>Sau</div>Cuối")
    assert [b.text for b in result.blocks] == ["Trước", "Văn bản lồng.", "Sau", "Cuối"]
    assert extract("<p>foo<b>bar</b>baz</p>").blocks[0].text == "foobarbaz"


def test_paragraphs_inside_nested_lists_retain_item_depth():
    result = extract("<ol><li><p>A</p><ul><li>B</li></ul><p>C</p></li><li>D</li></ol>")
    assert [(b.kind, b.level, b.text) for b in result.blocks] == [
        ("list_item", 1, "A"),
        ("list_item", 2, "B"),
        ("list_item", 1, "C"),
        ("list_item", 1, "D"),
    ]


def test_script_style_interface_and_comments_are_excluded():
    result = extract(
        "<title>Title</title><script>bad</script><style>bad</style><!-- bad -->"
        '<nav>bad</nav><div role="navigation">bad</div><button>bad</button>'
        '<div hidden>bad</div><div aria-hidden="true">bad</div><template>bad</template>'
        "<p>keep</p><header><p>Document header</p></header><footer>Document footer</footer>"
    )
    assert [b.text for b in result.blocks] == ["keep", "Document header", "Document footer"]
    assert result.metadata["title"] == "Title"


def test_malformed_html_retains_text_in_source_order():
    result = extract("<div><h2>Tiêu đề</h2><p>Đoạn một<p>Đoạn hai<b> đậm")
    assert [b.text for b in result.blocks] == ["Tiêu đề", "Đoạn một", "Đoạn hai đậm"]
    assert result.status == "success"


def test_repeated_paragraphs_are_not_deduplicated():
    assert [b.text for b in extract("<p>Same</p><p>Same</p>").blocks] == ["Same", "Same"]


@pytest.mark.parametrize("html", ["", " \n ", "<html><body></body></html>", "<script>x</script>"])
def test_empty_document_is_failed(html):
    result = extract(html)
    assert result.status == "failed"
    assert result.blocks == ()
    assert "no_extractable_text" in result.errors


@pytest.mark.parametrize(
    "html",
    [
        '<table><tr><td colspan="2">A</td></tr><tr><td>B</td><td>C</td></tr></table>',
        '<table><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table>',
        "<table><tr><td>A<table><tr><td>B</td></tr></table>C</td></tr></table>",
        "<table>A<tr><td>B</td></tr>C</table>",
        "<table><td>A</td><td>B</td>C</table>",
    ],
)
def test_complex_tables_retain_text_with_warning(html):
    result = extract(html)
    text = " ".join(b.text for b in result.blocks)
    assert all(text.count(value) == 1 for value in "ABC")
    assert text.index("A") < text.index("B") < text.index("C")
    assert result.status == "partial"
    assert "html_table_structure_lost" in result.warnings


def test_br_and_preformatted_text():
    result = extract("<p>A<br>B</p><pre>one\n  two</pre>")
    assert [b.text for b in result.blocks] == ["A\nB", "one\n  two"]


def test_empty_table_cells_retain_column_separators():
    result = extract("<table><tr><td></td><td>B</td><td></td></tr></table>")
    assert result.blocks[0].text == "\tB\t"


def test_declared_non_utf8_encoding_is_respected():
    result = HTMLExtractor().extract('<meta charset="windows-1252"><p>Café</p>'.encode("cp1252"))
    assert result.blocks[0].text == "Café"
    assert "html_non_utf8_encoding_detected" in result.warnings


def test_nontext_content_is_an_explicit_limitation():
    result = extract('<p>A</p><img src="https://unused.invalid/fixture.png"><svg>shape</svg>')
    assert result.status == "partial"
    assert result.blocks[0].text == "A"
    assert "html_nontext_content_omitted" in result.warnings


def test_parser_failure_retains_safe_error(monkeypatch):
    def fail(*args):
        raise ValueError("secret document text")

    monkeypatch.setattr("medical_data_crawler.html_extraction.BeautifulSoup", fail)
    result = extract("fixture")
    assert result.status == "failed"
    assert result.errors == ("html_parser_error",)
    assert "secret" not in repr(result)
