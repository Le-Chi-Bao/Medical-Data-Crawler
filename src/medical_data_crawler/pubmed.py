"""ESearch -> ESummary JSON replay with bounded parsing and field filtering."""

import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime

from .discovery import (
    MAPPING_VERSION,
    MAX_RESPONSE_BYTES,
    PROFILE,
    DisabledMetadataTransport,
    DiscoveryError,
    DiscoveryIssue,
    DiscoveryItem,
    DiscoveryPage,
    DiscoveryPermit,
    DiscoveryRequest,
    MetadataFact,
    MetadataTransport,
    SearchSnapshot,
    authorize,
    digest,
    identifier,
)

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_INPUT_FIELDS = frozenset(
    {"uid", "title", "authors", "fulljournalname", "pubdate", "pubtype", "articleids"}
)
_NOTICES = frozenset(
    {
        "Published Erratum",
        "Retraction of Publication",
        "Retracted Publication",
        "Expression of Concern",
        "Corrected and Republished Article",
    }
)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DiscoveryError("duplicate_json_key")
        result[key] = value
    return result


def parse_json(payload: bytes) -> dict:
    """XML (including DTD/entities) is rejected; no XML parser or URL resolution exists."""
    if type(payload) is not bytes:
        raise DiscoveryError("invalid_payload")
    if len(payload) > MAX_RESPONSE_BYTES:
        raise DiscoveryError("response_too_large")
    try:
        value = json.loads(
            payload, object_pairs_hook=_object, parse_constant=lambda _: _invalid_constant()
        )
    except (ValueError, UnicodeError, RecursionError):
        raise DiscoveryError("invalid_json") from None
    if type(value) is not dict:
        raise DiscoveryError("invalid_payload")
    return value


def _invalid_constant():
    raise DiscoveryError("invalid_json")


def _text(value: object, limit: int = 1024) -> str:
    if type(value) is not str or not value.strip():
        raise DiscoveryError("invalid_metadata")
    try:
        if len(value.encode("utf-8")) > limit or any(
            ord(c) < 32 or 127 <= ord(c) <= 159 for c in value
        ):
            raise DiscoveryError("invalid_metadata")
    except UnicodeError:
        raise DiscoveryError("invalid_metadata") from None
    return value


def _list(value: object, limit: int = 64) -> list:
    if type(value) is not list or len(value) > limit:
        raise DiscoveryError("invalid_metadata")
    return value


def _number(value: object) -> int:
    if type(value) is not str or not value.isascii() or not value.isdigit() or len(value) > 10:
        raise DiscoveryError("response_inconsistent")
    return int(value)


class PubMedMetadataMapper:
    version = MAPPING_VERSION

    def map(self, pmid: str, record: object, permit: DiscoveryPermit) -> tuple[DiscoveryItem, int]:
        if type(record) is not dict or identifier("pmid", record.get("uid")) != pmid:
            raise DiscoveryError("summary_identity_mismatch")
        facts = [MetadataFact("pmid", pmid, "uid")]
        dropped = len(record.keys() - _INPUT_FIELDS)

        def add(name, value, path):
            nonlocal dropped
            if name in permit.fields:
                facts.append(MetadataFact(name, value, path))
            else:
                dropped += 1

        for source, target in (
            ("title", "title"),
            ("fulljournalname", "journal"),
            ("pubdate", "published_on"),
        ):
            # Do not even validate or retain disallowed values.
            if target not in permit.fields:
                dropped += int(source in record)
            else:
                raw = record.get(source)
                add(target, None if raw in (None, "") else _text(raw), source)
        if "authors" in record:
            if "authors" not in permit.fields:
                dropped += 1
            else:
                names = []
                for author in _list(record["authors"]):
                    if type(author) is not dict:
                        raise DiscoveryError("invalid_metadata")
                    names.append(_text(author.get("name"), 512))
                    dropped += len(author.keys() - {"name"})
                add("authors", tuple(names), "authors[].name")
        for article_id in _list(record.get("articleids", []), 32):
            if type(article_id) is not dict:
                raise DiscoveryError("invalid_metadata")
            kind = article_id.get("idtype")
            namespace = {"pubmed": "pmid", "doi": "doi", "pmc": "pmcid"}.get(
                kind if type(kind) is str else ""
            )
            dropped += len(article_id.keys() - {"idtype", "value", "idtypen"})
            if namespace is None or namespace not in permit.fields:
                dropped += 1
                continue
            normalized = identifier(namespace, article_id.get("value"))
            if namespace == "pmid":
                if normalized != pmid:
                    raise DiscoveryError("summary_identity_mismatch")
            else:
                add(namespace, normalized, f"articleids[{kind}].value")
        types = []
        if "publication_type" in permit.fields:
            types = [_text(v, 128) for v in _list(record.get("pubtype", []), 32)]
            for value in dict.fromkeys(types):
                add("publication_type", value, "pubtype")
        else:
            dropped += int("pubtype" in record)
        category = "unknown"
        if "Systematic Review" in types:
            category = "systematic_reviews"
        elif "Journal Article" in types and "Review" not in types:
            category = "research_papers"
        if category != "unknown":
            add("category", category, "pubtype")
        # ESummary publication type supplies an indicator, never a directed relation.
        for notice in sorted(set(types) & _NOTICES):
            add("status", "unresolved_review_candidate: " + notice, "pubtype")
        return DiscoveryItem(pmid, tuple(dict.fromkeys(facts))), dropped


class PubMedDiscoveryConnector:
    """Only two fixed E-utilities endpoints. Injecting transport is a trusted operation."""

    def __init__(
        self,
        snapshot: SearchSnapshot,
        *,
        cursor_key: bytes,
        transport: MetadataTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        if (
            type(snapshot) is not SearchSnapshot
            or type(cursor_key) is not bytes
            or len(cursor_key) < 32
        ):
            raise DiscoveryError("invalid_configuration")
        self.snapshot = snapshot
        self._key = cursor_key
        self._transport = transport if transport is not None else DisabledMetadataTransport()
        self.clock = clock
        self.mapper = PubMedMetadataMapper()

    def authorize(self, request, permit):
        authorize(request, permit, self.snapshot, self.clock())

    def _token(self, offset, request, permit):
        binding = digest(
            self.snapshot.fingerprint,
            request.domain_id,
            request.page_size,
            permit.fingerprint,
            PROFILE,
            MAPPING_VERSION,
            offset,
        )
        signature = hmac.new(self._key, binding.encode(), hashlib.sha256).hexdigest()
        return f"{offset}.{signature}"

    def _offset(self, request, permit):
        if request.cursor is None:
            return 0
        if (
            type(request.cursor) is not str
            or len(request.cursor) > 80
            or not request.cursor.isascii()
        ):
            raise DiscoveryError("invalid_cursor")
        try:
            raw, _ = request.cursor.split(".", 1)
            offset = int(raw)
        except ValueError:
            raise DiscoveryError("invalid_cursor") from None
        if (
            not 0 < offset < len(self.snapshot.pmids)
            or offset % request.page_size
            or not hmac.compare_digest(request.cursor, self._token(offset, request, permit))
        ):
            raise DiscoveryError("invalid_cursor")
        return offset

    def _exchange(self, endpoint, parameters, request, permit):
        self.authorize(request, permit)
        try:
            payload = self._transport.exchange(endpoint, parameters, max_bytes=MAX_RESPONSE_BYTES)
        except DiscoveryError as error:
            if error.code == "network_disabled":
                raise
            raise DiscoveryError("transport_failure") from None
        except Exception:
            raise DiscoveryError("transport_failure") from None
        self.authorize(request, permit)
        decoded = parse_json(payload)
        header = decoded.get("header")
        expected_type = "esearch" if endpoint == ESEARCH else "esummary"
        if (
            type(header) is not dict
            or header.get("type") != expected_type
            or header.get("version") != "0.3"
        ):
            raise DiscoveryError("response_profile_mismatch")
        return decoded

    def discover(self, request: DiscoveryRequest, permit: DiscoveryPermit) -> DiscoveryPage:
        self.authorize(request, permit)
        start = self._offset(request, permit)
        search = self._exchange(
            ESEARCH,
            {
                "db": "pubmed",
                "term": request.query,
                "retmode": "json",
                "retstart": str(start),
                "retmax": str(request.page_size),
                "sort": "pub_date",
            },
            request,
            permit,
        )
        result = search.get("esearchresult")
        if type(result) is not dict or "error" in search or "errorlist" in result:
            raise DiscoveryError("response_inconsistent")
        total = _number(result.get("count"))
        if total > 10000:
            raise DiscoveryError("retrieval_window_exceeded")
        expected = self.snapshot.pmids[start : start + request.page_size]
        ids = result.get("idlist")
        if type(ids) is not list or len(ids) > request.page_size:
            raise DiscoveryError("response_inconsistent")
        ids = tuple(identifier("pmid", value) for value in ids)
        if (
            total != len(self.snapshot.pmids)
            or _number(result.get("retstart")) != start
            or _number(result.get("retmax")) != len(expected)
            or ids != expected
        ):
            raise DiscoveryError("response_inconsistent")
        if not ids:
            return DiscoveryPage(total, start, (), (), 0, None, True)
        summary = self._exchange(
            ESUMMARY,
            {"db": "pubmed", "id": ",".join(ids), "retmode": "json", "version": "2.0"},
            request,
            permit,
        )
        result = summary.get("result")
        if type(result) is not dict or "error" in summary:
            raise DiscoveryError("response_inconsistent")
        uids = result.get("uids")
        if type(uids) is not list or len(uids) > len(ids):
            raise DiscoveryError("response_inconsistent")
        normalized = tuple(identifier("pmid", value) for value in uids)
        if len(set(normalized)) != len(normalized) or not set(normalized) <= set(ids):
            raise DiscoveryError("response_inconsistent")
        if set(result) != {"uids", *uids}:
            raise DiscoveryError("response_inconsistent")
        items, issues, dropped = [], [], 0
        for index, pmid in enumerate(ids):
            if pmid not in uids:
                issues.append(DiscoveryIssue("missing_summary", index))
                continue
            try:
                item, rejected_fields = self.mapper.map(pmid, result[pmid], permit)
                items.append(item)
                dropped += rejected_fields
            except DiscoveryError as error:
                issues.append(DiscoveryIssue(error.code, index))
        end = start + len(ids)
        cursor = self._token(end, request, permit) if end < total and not issues else None
        return DiscoveryPage(
            total, start, tuple(items), tuple(issues), dropped, cursor, end == total and not issues
        )
