"""Invented article; never count this payload as live medical content."""

FIXTURE = b"""<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
<GetRecord><record><header><identifier>oai:pubmedcentral.nih.gov:1</identifier>
<setSpec>pmc-open</setSpec></header><metadata><article xmlns="" article-type="research-article">
<front><article-meta><article-id pub-id-type="pmc">1</article-id>
<title-group><article-title>Synthetic skin lesion fixture</article-title></title-group>
<permissions><license xmlns:xlink="http://www.w3.org/1999/xlink"
xlink:href="https://creativecommons.org/licenses/by/4.0/">
<license-p>Synthetic permission evidence only.</license-p></license></permissions>
<abstract><p>Synthetic abstract.</p></abstract></article-meta></front>
<body><sec><title>Fixture heading</title><p>First paragraph.</p>
<list list-type="order"><list-item><p>First item.</p></list-item></list>
<table-wrap><caption><p>Fixture caption.</p></caption>
<table><tr><td>Cell A</td><td>Cell B</td></tr></table></table-wrap>
</sec></body><back><ref-list><ref><mixed-citation>Synthetic reference.</mixed-citation>
</ref></ref-list></back></article></metadata></record></GetRecord></OAI-PMH>"""
