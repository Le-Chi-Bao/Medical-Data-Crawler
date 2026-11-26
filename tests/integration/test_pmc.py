"""Synthetic end-to-end PMC with real disk/catalog and no network."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from medical_data_crawler.catalog.model import Document, Rendition
from medical_data_crawler.catalog.store import Catalog
from medical_data_crawler.contract import validate_record
from medical_data_crawler.discovery import DiscoveryError
from medical_data_crawler.jats import MAX_XML_BYTES, extract_jats, parse_record, safe_xml
from medical_data_crawler.multisource import SOURCES
from medical_data_crawler.multisource_cli import demo, main
from medical_data_crawler.operation_policy import (
    OperationGrant,
    OperationPolicyGate,
    OperatorPolicyAuthority,
)
from medical_data_crawler.pmc import candidates, run, scope
from medical_data_crawler.pmc_demo import FIXTURE
from medical_data_crawler.pmc_transport import PMCTransport
from medical_data_crawler.pmc_verification import verify_corpus

NOW = datetime(2026, 11, 26, tzinfo=UTC)
OPS = ("fetch_document", "retain_metadata", "store_original", "extract_content")
RIGHTS = {
    "PMC1": {
        "license_uri": "https://creativecommons.org/licenses/by/4.0/",
        "retain_original": True,
        "extract_text": True,
        "third_party_reviewed": True,
        "evidence": "synthetic-operator-review",
    }
}


class Replay:
    is_live = False
    calls = 0

    def __init__(self, data=FIXTURE, callback=lambda: None):
        self.data, self.callback = data, callback

    def fetch(self, pmcid, authorize):
        authorize()
        self.calls += 1
        self.callback()
        return self.data


def authority(ops=OPS):
    return OperatorPolicyAuthority(
        tuple(
            OperationGrant(
                "PMC1:" + op, scope("PMC1", op), NOW - timedelta(days=1), NOW + timedelta(days=1)
            )
            for op in ops
        )
    )


def execute(tmp_path, *, auth=None, transport=None, rights=None):
    return run(
        ["PMC1"],
        gate=OperationPolicyGate(auth or authority()),
        transport=transport or Replay(),
        rights=RIGHTS if rights is None else rights,
        output=tmp_path,
        clock=lambda: NOW,
    )


def test_e2e_replay_bytes_catalog_and_trace(tmp_path):
    first, folder = execute(tmp_path)
    second, _ = execute(tmp_path)
    assert first["execution"] == "simulated"
    assert first["extracted_documents"] == second["extracted_documents"] == 1
    assert second["duplicates"] == 1
    checksum = hashlib.sha256(FIXTURE).hexdigest()
    assert (tmp_path / "originals" / checksum).read_bytes() == FIXTURE
    record = json.loads((folder / "PMC1.json").read_text())
    validate_record(record)
    assert record["scope"] == "unknown"
    event = json.loads(
        (tmp_path / "events" / (first["items"][0]["event_id"] + ".json")).read_text()
    )
    assert event["sha256"] == record["original"]["sha256"] == checksum
    assert len(first["items"][0]["locators"]) == len(record["content"])
    with Catalog(tmp_path / "catalog") as catalog:
        domain = catalog.domain("pmc-pilot")
        assert len(domain.list(Document)) == len(domain.list(Rendition)) == 1
        catalog.verify()


@pytest.mark.parametrize(
    "ids",
    [
        [],
        ["PMC1"] * 2,
        ["PMC1", "PMC2", "PMC3", "PMC4"],
        ["1"],
        ["PMC0"],
        ["PMC1/../../"],
        ["PMC1?x=1"],
    ],
)
def test_candidate_limits(ids):
    with pytest.raises(DiscoveryError):
        candidates(ids)


@pytest.mark.parametrize("op", OPS)
def test_separate_operation_grants(tmp_path, op):
    transport = Replay()
    report, folder = execute(
        tmp_path, auth=authority(tuple(x for x in OPS if x != op)), transport=transport
    )
    assert report["extracted_documents"] == 0
    assert not (folder / "PMC1.txt").exists()
    if op == "fetch_document":
        assert transport.calls == 0
    if op == "extract_content":
        assert report["downloaded_originals"] == 1
    else:
        assert report["downloaded_originals"] == 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("license_uri", "https://example.org/other"),
        ("third_party_reviewed", False),
        ("retain_original", False),
        ("evidence", ""),
    ],
)
def test_ambiguous_rights_discard_before_storage(tmp_path, key, value):
    rights = {"PMC1": {**RIGHTS["PMC1"], key: value}}
    report, _ = execute(tmp_path, rights=rights)
    assert report["downloaded_originals"] == 0
    assert not list((tmp_path / "originals").iterdir())


def test_revoke_during_inspection(tmp_path):
    auth = authority()
    report, _ = execute(
        tmp_path, auth=auth, transport=Replay(callback=lambda: auth.revoke("PMC1:store_original"))
    )
    assert report["downloaded_originals"] == 0
    assert report["items"][0]["error"] == "permission_revoked"


@pytest.mark.parametrize(
    "data,code",
    [
        (b"<!DOCTYPE x [<!ENTITY x SYSTEM 'file:///secret'>]><x/>", "unsafe_xml"),
        (b"<x>", "malformed_xml"),
        (b"x" * (MAX_XML_BYTES + 1), "xml_size_denied"),
        ("<x/>".encode("utf-16"), "xml_encoding_denied"),
        (b"<x>" * 70 + b"</x>" * 70, "xml_structure_denied"),
        (b'<x xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="x"/></x>', "unsafe_xml"),
    ],
)
def test_unsafe_xml(data, code):
    with pytest.raises(DiscoveryError, match=code):
        safe_xml(data)


@pytest.mark.parametrize(
    "old,new,code",
    [
        (b"pmc-open", b"closed", "not_pmc_open"),
        (b'pub-id-type="pmc">1', b'pub-id-type="pmc">2', "identifier_mismatch"),
        (b"<GetRecord>", b"<ListRecords>", "malformed_xml"),
        (b'<article xmlns=""', b'<article xmlns="urn:unexpected"', "unsupported_jats_profile"),
        (b"https://creativecommons.org/licenses/by/4.0/", b"", "missing_or_ambiguous_license"),
    ],
)
def test_provider_profile_rejection(old, new, code):
    with pytest.raises(DiscoveryError, match=code):
        parse_record(FIXTURE.replace(old, new), "PMC1")


def test_order_and_partial_extraction():
    article, _, _ = parse_record(FIXTURE, "PMC1")
    result, _ = extract_jats(article)
    assert [b.text for b in result.blocks] == [
        "Synthetic skin lesion fixture",
        "Synthetic abstract.",
        "Fixture heading",
        "First paragraph.",
        "First item.",
        "Fixture caption.",
        "Cell A\tCell B",
        "Synthetic reference.",
    ]
    article, _, _ = parse_record(FIXTURE.replace(b"</sec>", b"<graphic/></sec>"), "PMC1")
    assert extract_jats(article)[0].status == "partial"
    article, _, _ = parse_record(
        FIXTURE.replace(b"<body>", b"<other>").replace(b"</body>", b"</other>"), "PMC1"
    )
    assert extract_jats(article)[0].status == "partial"


def test_no_network_by_default_and_endpoint_binding():
    transport = PMCTransport()
    with pytest.raises(DiscoveryError, match="network_disabled"):
        transport.fetch("PMC1", lambda: None)
    with pytest.raises(DiscoveryError, match="endpoint_denied"):
        transport.fetch("PMC1", lambda: None, endpoint="https://localhost/")
    assert SOURCES["pubmed"].status == SOURCES["pmc"].status == "implemented"
    assert all(s.status != "implemented" for k, s in SOURCES.items() if k not in {"pmc", "pubmed"})


def test_cli_offline_demo_twice(tmp_path):
    first, _ = demo(tmp_path)
    second, _ = demo(tmp_path)
    assert first["downloaded_originals"] == second["duplicates"] == 1
    assert main(["pmc", "pilot"]) == 1
    assert verify_corpus(tmp_path)["verified_original_references"] == 2


def test_integrity_detects_changed_derived_text(tmp_path):
    _, folder = execute(tmp_path)
    (folder / "PMC1.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(DiscoveryError, match="text_mismatch"):
        verify_corpus(tmp_path)


def test_expiry_before_network(tmp_path):
    auth = OperatorPolicyAuthority(
        tuple(
            OperationGrant(
                "PMC1:" + op, scope("PMC1", op), NOW - timedelta(days=2), NOW - timedelta(days=1)
            )
            for op in OPS
        )
    )
    transport = Replay()
    report, _ = execute(tmp_path, auth=auth, transport=transport)
    assert transport.calls == 0
    assert report["items"][0]["error"] == "permission_expired"
