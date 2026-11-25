from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pubmed_helpers import KEY, NOW, Transport, configuration, connector, load

from medical_data_crawler.discovery import (
    ALLOWED_FIELDS,
    MAX_RESPONSE_BYTES,
    DiscoveryError,
)
from medical_data_crawler.pubmed import (
    ESEARCH,
    ESUMMARY,
    PubMedDiscoveryConnector,
    PubMedMetadataMapper,
    parse_json,
)


def test_search_summary_contract_and_pagination():
    snapshot, request, permit = configuration()
    transport = Transport()
    service = connector(transport)
    pages = []
    while True:
        page = service.discover(request, permit)
        pages.append(page)
        if page.next_cursor is None:
            break
        request = replace(request, cursor=page.next_cursor)
    assert tuple(item.pmid for p in pages for item in p.items) == snapshot.pmids
    assert [p.retstart for p in pages] == [0, 2, 4]
    assert all(p.total == 6 for p in pages)
    assert pages[-1].complete and not pages[0].complete
    assert [c[0] for c in transport.calls] == [ESEARCH, ESUMMARY] * 3
    for endpoint, params, bound in transport.calls:
        assert bound == MAX_RESPONSE_BYTES and params["db"] == "pubmed"
        assert params["retmode"] == "json"
        if endpoint == ESUMMARY:
            assert params["version"] == "2.0"
    first_request = configuration()[1]
    assert (
        connector(Transport()).discover(first_request, permit).next_cursor == pages[0].next_cursor
    )


def test_mapping_allowed_fields_missing_values_and_namespace_normalization():
    _, _, permit = configuration()
    record = load("esummary-0.json")["result"]["990000006"]
    item, dropped = PubMedMetadataMapper().map("990000006", record, permit)
    facts = {f.field: f.value for f in item.facts}
    assert facts["doi"] == "10.99999/fictional-skin-0"
    assert facts["pmid"] == "990000006" and facts["pmcid"] == "PMC990000006"
    assert facts["authors"] == ("Fable Q", "Imaginary R")
    assert facts["published_on"] == "2026 Nov 24"
    assert facts["category"] == "research_papers"
    assert dropped == 6
    assert set(facts) <= ALLOWED_FIELDS
    assert "abstract" not in facts and "openaccess" not in facts
    other = load("esummary-0.json")["result"]["990000005"]
    item, _ = PubMedMetadataMapper().map("990000005", other, permit)
    assert not any(f.field == "doi" for f in item.facts)
    record = {"uid": "990000006"}
    item, _ = PubMedMetadataMapper().map("990000006", record, permit)
    assert {f.field: f.value for f in item.facts}["published_on"] is None
    assert not any(f.field == "category" for f in item.facts)


@pytest.mark.parametrize(
    "types,category",
    [
        (["Systematic Review"], "systematic_reviews"),
        (["Journal Article", "Systematic Review"], "systematic_reviews"),
        (["Review"], None),
        (["Journal Article", "Review"], None),
        ([], None),
        (["Journal Article"], "research_papers"),
    ],
)
def test_category_requires_explicit_publication_type(types, category):
    _, _, permit = configuration()
    item, _ = PubMedMetadataMapper().map(
        "1",
        {
            "uid": "1",
            "pubtype": types,
            "title": "Systematic review keyword is not classification evidence",
        },
        permit,
    )
    assert next((f.value for f in item.facts if f.field == "category"), None) == category


def test_disallowed_publication_type_cannot_leak_into_derived_category_or_status():
    _, _, permit = configuration()
    permit = replace(permit, fields=frozenset({"pmid", "category", "status"}))
    item, dropped = PubMedMetadataMapper().map(
        "1",
        {
            "uid": "1",
            "pubtype": ["Systematic Review", "Retracted Publication"],
            "title": "forbidden",
        },
        permit,
    )
    assert [f.field for f in item.facts] == ["pmid"]
    assert dropped == 2


@pytest.mark.parametrize(
    "change",
    [
        {"allow_discovery": False},
        {"allow_retention": False},
        {"source": "pmc"},
        {"domain_id": "other"},
        {"profile_id": "other"},
        {"query": "unapproved"},
        {"operation": "fetch"},
        {"retention_purpose": "ai_use"},
        {"fields": frozenset({"pmid", "abstract"})},
        {"fields": frozenset({"title"})},
        {"fields": ["pmid"]},
        {"valid_until": NOW},
        {"valid_from": datetime(2027, 1, 1, tzinfo=UTC)},
        {"valid_from": datetime(2026, 1, 1)},
        {"field_policy_version": "other"},
    ],
)
def test_permit_denied_before_transport(change):
    _, request, permit = configuration()
    transport = Transport()
    with pytest.raises(DiscoveryError, match="^unauthorized$"):
        connector(transport).discover(request, replace(permit, **change))
    assert transport.calls == []


@pytest.mark.parametrize("size", [0, -1, 101, True, "2", None])
def test_invalid_page_size(size):
    _, request, permit = configuration()
    with pytest.raises(DiscoveryError, match="^invalid_request$"):
        connector(Transport()).discover(replace(request, page_size=size), permit)


@pytest.mark.parametrize(
    "cursor", ["2.bad", "0.bad", "10000.bad", "-2.bad", "x.y", "2.é", "2." + "x" * 90, [], "2"]
)
def test_cursor_tampering(cursor):
    _, request, permit = configuration()
    transport = Transport()
    with pytest.raises(DiscoveryError, match="^invalid_cursor$"):
        connector(transport).discover(replace(request, cursor=cursor), permit)
    assert transport.calls == []


def test_cursor_bound_to_domain_size_permit_snapshot_and_key():
    snapshot, request, permit = configuration()
    token = connector(Transport()).discover(request, permit).next_cursor
    request = replace(request, cursor=token)
    variants = [
        (connector(Transport()), replace(request, page_size=3), permit),
        (connector(Transport()), request, replace(permit, id="another")),
        (
            connector(Transport()),
            replace(request, domain_id="other"),
            replace(permit, domain_id="other"),
        ),
        (connector(Transport(), replace(snapshot, id="another")), request, permit),
        (
            PubMedDiscoveryConnector(
                snapshot, cursor_key=KEY + b"x", transport=Transport(), clock=lambda: NOW
            ),
            request,
            permit,
        ),
    ]
    for service, req, grant in variants:
        with pytest.raises(DiscoveryError, match="^invalid_cursor$"):
            service.discover(req, grant)


@pytest.mark.parametrize(
    "body,code",
    [
        (b"{", "invalid_json"),
        (b"<xml/>", "invalid_json"),
        (b'<!DOCTYPE a [<!ENTITY e SYSTEM "file:///secret">]><a>&e;</a>', "invalid_json"),
        (b"[]", "invalid_payload"),
        (b"null", "invalid_payload"),
        (b"true", "invalid_payload"),
        (b"1", "invalid_payload"),
        (b'{"x":NaN}', "invalid_json"),
        (b'{"x":1,"x":2}', "duplicate_json_key"),
        (b"\xff", "invalid_json"),
        (b"[" * 2000, "invalid_json"),
        (b"x" * (MAX_RESPONSE_BYTES + 1), "response_too_large"),
        ("text", "invalid_payload"),
    ],
)
def test_safe_parser(body, code):
    with pytest.raises(DiscoveryError, match=f"^{code}$"):
        parse_json(body)


@pytest.mark.parametrize(
    "change",
    [
        {"count": "5"},
        {"count": 6},
        {"retstart": "2"},
        {"retmax": "3"},
        {"idlist": ["990000006", "990000006"]},
        {"idlist": ["990000005", "990000006"]},
        {"idlist": []},
        {"idlist": [None]},
        {"idlist": {}},
        {"count": True},
        {"idlist": ["990000006", "990000005", "1"]},
        {"errorlist": {}},
    ],
)
def test_search_response_inconsistencies(change):
    _, request, permit = configuration()
    search = load("esearch-0.json")
    search["esearchresult"].update(change)
    with pytest.raises(DiscoveryError):
        connector(Transport(search=search)).discover(request, permit)


def test_boundary_10000_and_empty_search():
    snapshot, request, permit = configuration()
    search = load("esearch-0.json")
    search["esearchresult"]["count"] = "10001"
    with pytest.raises(DiscoveryError, match="^retrieval_window_exceeded$"):
        connector(Transport(search=search)).discover(request, permit)
    for count in (0, 10000):
        ids = tuple(str(i) for i in range(count, 0, -1))
        pinned = replace(snapshot, pmids=ids)
        # Retmax is the number actually returned, including short last/empty pages.
        search["esearchresult"] = {
            "count": str(count),
            "retstart": "0",
            "retmax": str(min(count, 2)),
            "idlist": list(ids[:2]),
        }
        summary = {
            "header": {"type": "esummary", "version": "0.3"},
            "result": {"uids": list(ids[:2]), **{i: {"uid": i} for i in ids[:2]}},
        }
        page = connector(Transport(search, summary), pinned).discover(request, permit)
        assert page.total == count and len(page.items) == min(count, 2)
        assert page.complete == (count == 0)
    with pytest.raises(DiscoveryError, match="^invalid_snapshot$"):
        replace(snapshot, pmids=tuple(str(i) for i in range(10001, 0, -1)))


@pytest.mark.parametrize("uids", [["990000006", "990000006"], ["1"], None, [None]])
def test_summary_bad_uids(uids):
    _, request, permit = configuration()
    summary = load("esummary-0.json")
    summary["result"]["uids"] = uids
    with pytest.raises(DiscoveryError):
        connector(Transport(summary=summary)).discover(request, permit)


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", []),
        ("title", "x" * 1025),
        ("title", "bad\x00text"),
        ("title", "bad\ud800"),
        ("authors", ["not-object"]),
        ("authors", [{}]),
        ("authors", [{"name": "x"}] * 65),
        ("pubtype", {}),
        ("pubtype", [1]),
        ("articleids", [None]),
        ("articleids", [{"idtype": "doi", "value": "bad"}]),
        ("uid", "1"),
    ],
)
def test_bad_item_isolated_and_cursor_withheld(field, value):
    _, request, permit = configuration()
    summary = load("esummary-0.json")
    summary["result"]["990000006"][field] = value
    page = connector(Transport(summary=summary)).discover(request, permit)
    assert len(page.items) == 1 and page.items[0].pmid == "990000005"
    assert page.issues[0].index == 0 and page.next_cursor is None and not page.complete


def test_missing_summary_is_incomplete_not_silently_skipped():
    _, request, permit = configuration()
    page = connector(Transport(summary=load("esummary-missing.json"))).discover(request, permit)
    assert len(page.items) == 1 and page.next_cursor is None
    assert page.issues[0].code == "missing_summary"


def test_default_disabled_transport_and_temporary_errors_redacted():
    _, request, permit = configuration()
    with pytest.raises(DiscoveryError, match="^network_disabled$"):
        connector().discover(request, permit)
    transport = Transport()
    transport.failure = TimeoutError("secret token and query text")
    with pytest.raises(DiscoveryError, match="^transport_failure$"):
        connector(transport).discover(request, permit)
    assert request.query not in repr(request) and permit.query not in repr(permit)


def test_expiry_after_exchange_stops_summary():
    _, request, permit = configuration()
    now = [NOW]
    transport = Transport()
    transport.after_exchange = lambda: now.__setitem__(0, permit.valid_until)
    with pytest.raises(DiscoveryError, match="^unauthorized$"):
        connector(transport, clock=lambda: now[0]).discover(request, permit)
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "header", [None, {}, {"type": "efetch", "version": "0.3"}, {"type": "esearch", "version": "2"}]
)
def test_strict_response_profile(header):
    _, request, permit = configuration()
    search = load("esearch-0.json")
    search["header"] = header
    with pytest.raises(DiscoveryError, match="^response_profile_mismatch$"):
        connector(Transport(search=search)).discover(request, permit)
