"""Bounded UTF-8 JATS/OAI parsing without external resource resolution."""

import re
import xml.etree.ElementTree as ET

from .discovery import DiscoveryError
from .extraction import ContentBlock, empty_metadata, extraction_result

MAX_XML_BYTES = 4 * 1024**2
OAI = "{http://www.openarchives.org/OAI/2.0/}"


def safe_xml(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES:
        raise DiscoveryError("xml_size_denied")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        raise DiscoveryError("xml_encoding_denied") from None
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?xml-stylesheet", text, re.I):
        raise DiscoveryError("unsafe_xml")
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError):
        raise DiscoveryError("malformed_xml") from None
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > 64 or count > 50000:
            raise DiscoveryError("xml_structure_denied")
        if node.tag.startswith("{http://www.w3.org/2001/XInclude}"):
            raise DiscoveryError("unsafe_xml")
        stack.extend((child, depth + 1) for child in node)
    return root


def text_of(node):
    return "" if node is None else "".join(node.itertext()).strip()


def parse_record(data, pmcid):
    root = safe_xml(data)
    if root.tag != OAI + "OAI-PMH":
        raise DiscoveryError("unexpected_xml_profile")
    if root.find(OAI + "error") is not None:
        raise DiscoveryError("article_unavailable")
    records = root.findall(OAI + "GetRecord/" + OAI + "record")
    if len(records) != 1:
        raise DiscoveryError("unexpected_xml_profile")
    record = records[0]
    header = record.find(OAI + "header")
    if header is None or header.get("status") == "deleted":
        raise DiscoveryError("article_unavailable")
    if text_of(header.find(OAI + "identifier")) != "oai:pubmedcentral.nih.gov:" + pmcid[3:]:
        raise DiscoveryError("identifier_mismatch")
    if "pmc-open" not in [text_of(n) for n in header.findall(OAI + "setSpec")]:
        raise DiscoveryError("not_pmc_open")
    articles = record.findall(OAI + "metadata/article")
    if len(articles) != 1:
        raise DiscoveryError("unsupported_jats_profile")
    article = articles[0]
    ids = {}
    for node in article.findall("./front/article-meta/article-id"):
        kind, value = node.get("pub-id-type"), text_of(node)
        if kind in {"pmc", "pmcid", "pmid", "doi"}:
            if kind in ids and ids[kind] != value:
                raise DiscoveryError("identifier_mismatch")
            ids[kind] = value
    native = ids.get("pmc", ids.get("pmcid", ""))
    if native.removeprefix("PMC") != pmcid[3:]:
        raise DiscoveryError("identifier_mismatch")
    licenses = article.findall("./front/article-meta/permissions/license")
    uris = {n.get("{http://www.w3.org/1999/xlink}href", "") for n in licenses}
    if len(uris) != 1 or not next(iter(uris), ""):
        raise DiscoveryError("missing_or_ambiguous_license")
    return (
        article,
        ids,
        {
            "uri": next(iter(uris)),
            "statement": "\n".join(text_of(n) for n in licenses),
            "locator": "front/article-meta/permissions/license",
            "third_party": "Separate review; no linked resources retrieved",
        },
    )


def extract_jats(article):
    blocks, locators, warnings = [], [], []
    kinds = {
        "article-title": "heading",
        "title": "heading",
        "p": "paragraph",
        "list-item": "list_item",
        "table": "table",
        "ref": "paragraph",
    }
    unsupported = {
        "graphic",
        "inline-graphic",
        "media",
        "supplementary-material",
        "disp-formula",
        "inline-formula",
        "tex-math",
    }
    containers = {
        "title-group",
        "abstract",
        "body",
        "back",
        "sec",
        "list",
        "table-wrap",
        "caption",
        "ref-list",
        "ack",
        "fn-group",
        "fn",
        "notes",
        "label",
    }

    def walk(node, path, level=1):
        tag = node.tag
        if tag in unsupported or tag.startswith("{"):
            warnings.append("unsupported_jats_element")
            return
        kind = kinds.get(tag)
        if kind:
            value = text_of(node)
            if tag == "table":
                value = "\n".join(
                    "\t".join(text_of(c) for c in row if c.tag in {"td", "th"})
                    for row in node.iter("tr")
                ).strip()
            if value:
                blocks.append(ContentBlock(kind, level if kind == "heading" else None, value))
                locators.append(path)
            if any(n.tag in unsupported for n in node.iter()):
                warnings.append("unsupported_jats_element")
            if tag == "list-item" and node.find(".//list") is not None:
                warnings.append("nested_list_flattened")
            return
        if tag not in containers:
            warnings.append("unverified_jats_element")
        counts = {}
        for child in node:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            walk(child, f"{path}/{child.tag}[{counts[child.tag]}]", level + (tag == "sec"))

    for child in article:
        if child.tag == "front":
            for path in ("article-meta/title-group", "article-meta/abstract"):
                for number, node in enumerate(child.findall(path), 1):
                    walk(node, f"/article/front/{path}[{number}]")
        elif child.tag in {"body", "back"}:
            walk(child, f"/article/{child.tag}[1]")
    metadata = empty_metadata()
    metadata["title"] = (
        text_of(article.find("./front/article-meta/title-group/article-title")) or None
    )
    metadata["language"] = article.get("{http://www.w3.org/XML/1998/namespace}lang")
    authors = [
        " ".join(text_of(part) for part in n.findall("name/*"))
        for n in article.findall("./front/article-meta/contrib-group/contrib")
        if n.get("contrib-type") == "author"
    ]
    metadata["authors"] = [a for a in authors if a] or None
    if article.find("body") is None:
        warnings.append("missing_body")
    result = extraction_result(
        document_type="xml",
        method="jats",
        version="1.0",
        profile="pmc-jats-utf8-v1",
        blocks=blocks,
        warnings=tuple(dict.fromkeys(warnings)),
        incomplete=bool(warnings),
        metadata=metadata,
    )
    return result, locators
