import json

import pytest

from medical_data_crawler.catalog import CatalogError, normalize_identifier
from medical_data_crawler.catalog.model import encode_json


@pytest.mark.parametrize(
    ("namespace", "value", "issuer", "normalized"),
    [
        ("doi", "https://doi.org/10.99999/Synthetic.Work", None, "10.99999/synthetic.work"),
        ("pmid", "987654321", None, "987654321"),
        ("pmcid", "pmc987654321", None, "PMC987654321"),
        ("isbn", "978-0-00-000000-2", None, "9780000000002"),
        ("guideline", "synthetic-G1", "fixture-board", "synthetic-G1"),
    ],
)
def test_identifier_normalization_preserves_namespace(namespace, value, issuer, normalized):
    assert normalize_identifier(namespace, value, issuer=issuer) == (
        namespace,
        normalized,
        issuer or "",
    )


@pytest.mark.parametrize(
    ("namespace", "value", "issuer"),
    [
        ("pmid", "PMC987654321", None),
        ("pmcid", "987654321", None),
        ("doi", "https://example.invalid/10.99999/sensitive-test-value", None),
        ("isbn", "9780000000003", None),
        ("guideline", "sensitive-test-value", None),
        ("sensitive-test-value", "x", None),
    ],
)
def test_invalid_identifier_does_not_echo_value(namespace, value, issuer):
    with pytest.raises(CatalogError) as raised:
        normalize_identifier(namespace, value, issuer=issuer)
    assert raised.value.code == "invalid_identifier"
    assert "sensitive-test-value" not in str(raised.value)


def test_json_serialization_is_canonical_and_preserves_unicode():
    first = {"title": "Ấn phẩm giả lập", "values": [True, None, 3]}
    second = {"values": [True, None, 3], "title": "Ấn phẩm giả lập"}
    encoded = encode_json(first)
    assert encoded == encode_json(second)
    assert encoded == '{"title":"Ấn phẩm giả lập","values":[true,null,3]}'
    assert json.loads(encoded) == first
