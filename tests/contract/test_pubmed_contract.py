"""Pinned synthetic E-utilities contracts, including the retrieval-window boundary."""

import json
from dataclasses import asdict, replace

import pytest
from pubmed_helpers import FIXTURES, Transport, configuration, connector, load

from medical_data_crawler.discovery import DiscoveryError
from medical_data_crawler.pubmed import ESEARCH, ESUMMARY, parse_json


class PinnedReplay:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.exchanges = []

    def exchange(self, endpoint, parameters, *, max_bytes):
        self.exchanges.append((endpoint, parameters))
        assert parameters["db"] == "pubmed" and parameters["retmode"] == "json"
        if endpoint == ESEARCH:
            assert set(parameters) == {"db", "term", "retmode", "retstart", "retmax", "sort"}
            assert parameters["term"] == self.snapshot.query and parameters["sort"] == "pub_date"
            start, size = int(parameters["retstart"]), int(parameters["retmax"])
            ids = self.snapshot.pmids[start : start + size]
            result = {
                "header": {"type": "esearch", "version": "0.3"},
                "esearchresult": {
                    "count": str(len(self.snapshot.pmids)),
                    "retstart": str(start),
                    "retmax": str(len(ids)),
                    "idlist": ids,
                },
            }
        else:
            assert endpoint == ESUMMARY
            assert set(parameters) == {"db", "id", "retmode", "version"}
            assert parameters["version"] == "2.0"
            # Summary order must not override the approved search snapshot order.
            ids = parameters["id"].split(",")[::-1]
            result = {
                "header": {"type": "esummary", "version": "0.3"},
                "result": {"uids": ids, **{pmid: {"uid": pmid} for pmid in ids}},
            }
        payload = json.dumps(result).encode()
        assert len(payload) <= max_bytes
        return payload


@pytest.mark.parametrize("count,size", [(0, 3), (5, 2), (6, 4), (6, 100), (10000, 100)])
def test_all_pages_respect_pinned_order_and_stop_at_supported_window(count, size):
    snapshot, request, permit = configuration()
    snapshot = replace(snapshot, pmids=tuple(str(i) for i in range(count, 0, -1)))
    request = replace(request, page_size=size)
    replay = PinnedReplay(snapshot)
    service = connector(replay, snapshot)
    observed = []
    while True:
        page = service.discover(request, permit)
        assert page.retstart == len(observed)
        observed.extend(item.pmid for item in page.items)
        if page.next_cursor is None:
            assert page.complete
            break
        assert not page.complete
        request = replace(request, cursor=page.next_cursor)
    assert tuple(observed) == snapshot.pmids
    assert len(set(observed)) == count
    assert all(int(p["retstart"]) < 10000 for e, p in replay.exchanges if e == ESEARCH)
    assert len(replay.exchanges) == (1 if count == 0 else 2 * ((count + size - 1) // size))


@pytest.mark.parametrize("query", [" ", "x\x7f", "x\x85", "\ud800", "é" * 257, "x" * 513])
def test_invalid_pinned_query_is_rejected_without_echo(query):
    snapshot, _, _ = configuration()
    with pytest.raises(DiscoveryError, match="^invalid_snapshot$"):
        replace(snapshot, query=query)


@pytest.mark.parametrize("field", ["abstract", "fulltext", "pdf", "publisher_url", "license_hint"])
def test_unapproved_fields_cannot_expand_retention_authority(field):
    _, request, permit = configuration()
    transport = Transport()
    with pytest.raises(DiscoveryError, match="^unauthorized$"):
        connector(transport).discover(request, replace(permit, fields=permit.fields | {field}))
    assert transport.calls == []


def test_malformed_and_duplicate_id_fixtures_are_controlled():
    with pytest.raises(DiscoveryError, match="^invalid_json$"):
        parse_json((FIXTURES / "malformed.json").read_bytes())
    _, request, permit = configuration()
    transport = Transport(search=load("esearch-duplicate.json"))
    with pytest.raises(DiscoveryError, match="^response_inconsistent$"):
        connector(transport).discover(request, permit)
    assert len(transport.calls) == 1


def test_page_and_report_contain_no_raw_response_or_submitted_query():
    _, request, permit = configuration()
    page = connector(Transport()).discover(request, permit)
    serialized = json.dumps(asdict(page))
    for forbidden in (request.query, "UNAUTHORIZED_", "DROP_UNKNOWN_", "publisher_url", "abstract"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    "types",
    [
        ["Published Erratum"],
        ["Retraction of Publication"],
        ["Retracted Publication"],
        ["Expression of Concern"],
    ],
)
def test_notice_evidence_is_unresolved_even_when_related_ids_are_present(types):
    _, request, permit = configuration()
    summary = load("esummary-0.json")
    record = summary["result"]["990000006"]
    record["pubtype"] = types
    record["related"] = {"retracts": "990000005"}  # Not an approved ESummary field.
    page = connector(Transport(summary=summary)).discover(request, permit)
    facts = page.items[0].facts
    status = [fact for fact in facts if fact.field == "status"]
    assert len(status) == 1
    assert status[0].path == "pubtype" and status[0].value.endswith(types[0])
    assert status[0].value.startswith("unresolved_review_candidate:")
    assert all(fact.field != "related" for fact in facts)
