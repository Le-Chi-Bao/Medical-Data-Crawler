import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from secure_api_helpers import response, setup_transport

from medical_data_crawler.catalog import Catalog, Document, Observation, Rendition, SourceItem
from medical_data_crawler.catalog.discovery import CatalogDiscoveryWriter
from medical_data_crawler.discovery import DiscoveryError, DiscoveryRequest
from medical_data_crawler.pubmed import PubMedDiscoveryConnector, capture_live_snapshot
from medical_data_crawler.pubmed_cli import main
from medical_data_crawler.pubmed_pilot import (
    METADATA_OPERATIONS,
    SEARCH_PROFILES,
    FileDecisionProvider,
    operator_transport,
    run_pilot,
)
from medical_data_crawler.secure_api_demo import IDS, NOW, demo_transport


def request(permit, page_size=2):
    return DiscoveryRequest(permit.domain_id, permit.profile_id, permit.query, page_size)


def test_provider_order_pinned_summaries_reversed_and_cursor_replay(tmp_path):
    permit, _, _, transport = demo_transport()
    output = run_pilot(
        tmp_path, "pilot-test", permit, transport, limit=2, page_size=1, clock=lambda: NOW
    )
    assert output["accepted"] == 2 and output["rejected"] == 0
    snapshot = json.loads((tmp_path / "runs/pilot-test/snapshot.json").read_text())
    assert snapshot["pmids"] == list(IDS)  # Preserve actual ESearch order.
    assert transport.attempts == 5  # One ESearch + two summaries + two simulated retries.
    assert (
        run_pilot(
            tmp_path, "pilot-test", permit, transport, resume=True, page_size=1, clock=lambda: NOW
        )
        == output
    )
    assert transport.attempts == 5  # Completed resume does not request anything.
    second = run_pilot(tmp_path, "another-run", permit, transport, limit=2, clock=lambda: NOW)
    assert second["accepted"] == 0 and second["already_known"] == 2
    with Catalog(tmp_path / "catalog") as catalog:
        scope = catalog.domain(permit.domain_id)
        assert len(scope.list(Document)) == 2 and scope.list(Rendition) == ()
        assert "UNAUTHORIZED_" not in "\n".join(catalog._connection.iterdump())
        catalog.verify()


@pytest.mark.parametrize(
    "changes",
    [
        {"count": "3"},
        {"idlist": ["2", "2"]},
        {"retstart": "1"},
        {"retmax": "3"},
        {"idlist": ["1"]},
        {"idlist": ["0", "2"]},
        {"warninglist": {"ignoredphrases": ["unrecognized"]}},
    ],
)
def test_capture_refuses_missing_duplicate_or_drifting_inventory(tmp_path, changes):
    result = {"count": "2", "retstart": "0", "retmax": "2", "idlist": ["1", "2"], **changes}
    # Count 3 with a cap of 3 is incomplete, never silently publish the shorter inventory.
    transport, _, _, _, _ = setup_transport(
        response(
            {
                "header": {"type": "esearch", "version": "0.3"},
                "esearchresult": result,
            }
        )
    )
    with pytest.raises(DiscoveryError):
        run_pilot(tmp_path, "bad", transport.permit, transport, limit=3, clock=lambda: NOW)
    assert not (tmp_path / "catalog").exists()


def test_large_search_only_captures_explicit_bounded_prefix_and_never_traverses_window(tmp_path):
    transport, wire, _, _, params = setup_transport(
        response(
            {
                "header": {"type": "esearch", "version": "0.3"},
                "esearchresult": {
                    "count": "10001",
                    "retstart": "0",
                    "retmax": "2",
                    "idlist": ["1", "2"],
                },
            }
        )
    )
    snapshot = capture_live_snapshot(
        request(transport.permit), transport.permit, transport, limit=2, clock=lambda: NOW
    )
    assert snapshot.pmids == ("1", "2") and snapshot.total_results == 10001
    with pytest.raises(DiscoveryError, match="^retrieval_window_exceeded$"):
        transport.exchange(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {**params, "retstart": "9999"},
            max_bytes=1024,
        )
    for limit in (0, 51, 10000):
        with pytest.raises(DiscoveryError):
            capture_live_snapshot(
                request(transport.permit), transport.permit, transport, limit=limit
            )
    assert len(wire.calls) == 1


def test_revocation_during_transaction_rolls_back_publication(tmp_path, monkeypatch):
    from medical_data_crawler.catalog import AccessDomain

    permit, authority, _, transport = demo_transport()
    req = request(permit)
    snapshot = capture_live_snapshot(req, permit, transport, limit=2, clock=lambda: NOW)
    service = PubMedDiscoveryConnector(
        snapshot, cursor_key=b"x" * 32, transport=transport, clock=lambda: NOW
    )
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain(permit.domain_id))
        scope = catalog.domain(permit.domain_id)
        put = scope._put

        def revoke_after_insert(record):
            put(record)
            if isinstance(record, SourceItem):
                authority.revoke(permit.id + ":retain_metadata")

        monkeypatch.setattr(scope, "_put", revoke_after_insert)
        outcome = CatalogDiscoveryWriter(scope, service).run(req, permit)
        assert outcome.report.accepted == 0 and outcome.next_cursor is None
        assert outcome.report.issues[0].code == "permission_revoked"
        assert scope.list(Document) == scope.list(Observation) == ()


def test_partial_failure_resume_does_not_rerun_esearch_or_advance_cursor(tmp_path):
    permit, _, _, transport = demo_transport()
    original = transport._wire

    class Missing:
        def post(self, *args, **kwargs):
            if args[1].endswith("esearch.fcgi"):
                return original.post(*args, **kwargs)
            from secure_api_helpers import Wire

            return Wire(
                response({"header": {"type": "esummary", "version": "0.3"}, "result": {"uids": []}})
            ).post(*args, **kwargs)

    transport._wire = Missing()
    first = run_pilot(tmp_path, "recover", permit, transport, limit=2, clock=lambda: NOW)
    assert first["status"] == "incomplete" and first["rejected"] == 2
    pinned = (tmp_path / "runs/recover/snapshot.json").read_bytes()

    # Resume uses ESummary only; a moving live search is never repeated.
    class SummaryOnly:
        def post(self, *args, **kwargs):
            assert args[1].endswith("esummary.fcgi")
            return original.post(*args, **kwargs)

    transport._wire = SummaryOnly()
    final = run_pilot(tmp_path, "recover", permit, transport, resume=True, clock=lambda: NOW)
    assert final["status"] == "complete" and final["accepted"] == 2
    assert (tmp_path / "runs/recover/snapshot.json").read_bytes() == pinned
    with pytest.raises(DiscoveryError, match="^permission_denied$"):
        run_pilot(
            tmp_path,
            "recover",
            replace(permit, id="other"),
            transport,
            resume=True,
            clock=lambda: NOW,
        )


def approval_file(tmp_path):
    path = tmp_path / "approval.json"
    value = {
        "approval_id": "operator-test",
        "domain_id": "public-metadata",
        "profile_id": "melanoma-v1",
        "approved_query": SEARCH_PROFILES["melanoma-v1"],
        "fields": [
            "pmid",
            "doi",
            "pmcid",
            "title",
            "authors",
            "journal",
            "published_on",
            "publication_type",
            "category",
            "status",
        ],
        "valid_from": "2020-01-01T00:00:00+00:00",
        "valid_until": "2099-01-01T00:00:00+00:00",
        "operations": list(METADATA_OPERATIONS),
        "revoked": False,
        "source_terms_reviewed": True,
        "network_approved": True,
        "exclusive_provider_ip": True,
        "output_dir": str(tmp_path / "output"),
    }
    path.write_text(json.dumps(value))
    return path, value


def test_file_authority_revocation_and_edit_and_missing_retention(tmp_path):
    path, value = approval_file(tmp_path)
    permit, _, transport = operator_transport(path)
    assert transport.settings.api_key is None and not transport.settings.enabled
    value["revoked"] = True
    path.write_text(json.dumps(value))
    with pytest.raises(DiscoveryError, match="^permission_revoked$"):
        transport.authorize()
    value["revoked"] = False
    value["fields"] = ["pmid"]
    path.write_text(json.dumps(value))
    with pytest.raises(DiscoveryError, match="^permission_denied$"):
        transport.authorize()
    value["operations"] = ["discover_metadata"]
    path.write_text(json.dumps(value))
    with pytest.raises(DiscoveryError):
        FileDecisionProvider(path)


def test_corrupt_checkpoint_cannot_claim_completion(tmp_path):
    permit, _, _, transport = demo_transport()
    run_pilot(tmp_path, "corrupt", permit, transport, limit=2, clock=lambda: NOW)
    path = tmp_path / "runs/corrupt/checkpoint.json"
    state = json.loads(path.read_text())
    state["complete"] = "true"
    path.write_text(json.dumps(state))
    attempts = transport.attempts
    with pytest.raises(DiscoveryError, match="^invalid_checkpoint$"):
        run_pilot(tmp_path, "corrupt", permit, transport, resume=True, clock=lambda: NOW)
    assert transport.attempts == attempts


def test_cli_profiles_preview_default_network_off_and_sanitized_errors(tmp_path, capsys):
    assert main(["profiles"]) == 0
    assert "melanoma-v1" in capsys.readouterr().out
    assert main(["preview"]) == 0
    assert json.loads(capsys.readouterr().out)["network_enabled"] is False
    assert main(["preview", "--limit", "51"]) == 2
    capsys.readouterr()
    path, _ = approval_file(tmp_path)
    assert main(["pilot", "--approval", str(path)]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "network_disabled"
    assert main(["--SECRET-TOKEN"]) == 2
    assert "SECRET-TOKEN" not in capsys.readouterr().err
    assert not (tmp_path / "output").exists()


def test_secure_demo_twice_in_subprocess_with_network_guard(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/demo_secure_api_transport.py"
    code = """
import runpy, socket, sys
def blocked(*args, **kwargs):
    raise AssertionError('Demo must remain offline')
socket.socket.connect = socket.socket.connect_ex = blocked
socket.create_connection = socket.getaddrinfo = blocked
runpy.run_path(sys.argv[1], run_name='__main__')
"""
    results = []
    for _ in range(2):
        process = subprocess.run(
            [sys.executable, "-c", code, str(script)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        results.append(json.loads(process.stdout))
    assert results[0] == results[1]
    assert results[0]["network_requests"] == results[0]["full_text_downloads"] == 0
    assert results[0]["retries"] == 2 and results[0]["documents"] == 2
