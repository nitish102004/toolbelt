"""SignOz v3 autocomplete API helpers."""
from __future__ import annotations

from typing import Any

from . import api


def attribute_values(
    attribute_key: str,
    *,
    data_source: str = "logs",
    search_text: str = "",
    tag_type: str = "resource",
    data_type: str = "string",
    aggregate_operator: str = "noop",
) -> list[str]:
    """Return string values for an attribute key (e.g. service.name)."""
    params = {
        "aggregateOperator": aggregate_operator,
        "dataSource": data_source,
        "aggregateAttribute": "",
        "attributeKey": attribute_key,
        "searchText": search_text,
        "filterAttributeKeyDataType": data_type,
        "tagType": tag_type,
    }
    resp = api.get("/api/v3/autocomplete/attribute_values", params=params)
    if isinstance(resp, dict) and resp.get("status") == "error":
        raise RuntimeError(str(resp.get("error", resp)))
    data = resp.get("data", resp) if isinstance(resp, dict) else resp
    if not isinstance(data, dict):
        return []
    values = data.get("stringAttributeValues") or []
    return [str(v) for v in values if v is not None]
