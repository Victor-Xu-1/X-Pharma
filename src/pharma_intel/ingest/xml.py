from __future__ import annotations

from lxml import etree  # type: ignore[import-untyped]

from pharma_intel.ingest.connectors import ConnectorTransportError


def parse_xml(payload: bytes, resource_name: str) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)
    try:
        return etree.fromstring(payload, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ConnectorTransportError(f"{resource_name} returned invalid XML") from exc
