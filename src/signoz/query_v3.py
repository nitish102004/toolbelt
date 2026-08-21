"""Build SignOz v3 ``/api/v3/query_range`` payloads (v0.73.x)."""
from __future__ import annotations

from typing import Any

_RESOURCE = {
    "dataType": "string",
    "type": "resource",
    "isColumn": False,
    "isJSON": False,
}

_TAG = {
    "dataType": "string",
    "type": "tag",
    "isColumn": True,
    "isJSON": False,
}


def _resource_key(name: str) -> dict[str, Any]:
    return {"key": name, **_RESOURCE, "id": f"{name}--string--resource--true"}


def _tag_key(name: str) -> dict[str, Any]:
    return {"key": name, **_TAG, "id": f"{name}--string--tag--true"}


def _filter_item(op: str, key: dict[str, Any], value: Any) -> dict[str, Any]:
    return {"id": f"f-{key['key']}-{op}", "op": op, "key": key, "value": value}


def _noop_attr() -> dict[str, Any]:
    return {
        "id": "------false",
        "dataType": "",
        "key": "",
        "isColumn": False,
        "type": "",
        "isJSON": False,
    }


def _step_ms(start_ms: int, end_ms: int) -> int:
    window_sec = max(1, (end_ms - start_ms) // 1000)
    return max(60, min(240, window_sec // 60))


def logs_list_query(
    start_ms: int,
    end_ms: int,
    *,
    filters: list[dict[str, Any]] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    items = list(filters or [])
    return {
        "start": start_ms,
        "end": end_ms,
        "step": _step_ms(start_ms, end_ms),
        "variables": {},
        "compositeQuery": {
            "queryType": "builder",
            "panelType": "list",
            "fillGaps": False,
            "builderQueries": {
                "A": {
                    "dataSource": "logs",
                    "queryName": "A",
                    "aggregateOperator": "noop",
                    "aggregateAttribute": _noop_attr(),
                    "timeAggregation": "rate",
                    "spaceAggregation": "sum",
                    "functions": [],
                    "filters": {"items": items, "op": "AND"},
                    "expression": "A",
                    "disabled": False,
                    "stepInterval": 60,
                    "having": [],
                    "limit": limit,
                    "orderBy": [{"columnName": "timestamp", "order": "desc"}],
                    "groupBy": [],
                    "legend": "",
                    "reduceTo": "avg",
                    "offset": offset,
                    "pageSize": limit,
                }
            },
        },
    }


def traces_list_query(
    start_ms: int,
    end_ms: int,
    *,
    filters: list[dict[str, Any]] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    items = list(filters or [])
    return {
        "start": start_ms,
        "end": end_ms,
        "step": _step_ms(start_ms, end_ms),
        "variables": {},
        "compositeQuery": {
            "queryType": "builder",
            "panelType": "list",
            "fillGaps": False,
            "builderQueries": {
                "A": {
                    "dataSource": "traces",
                    "queryName": "A",
                    "aggregateOperator": "noop",
                    "aggregateAttribute": _noop_attr(),
                    "timeAggregation": "rate",
                    "spaceAggregation": "sum",
                    "functions": [],
                    "filters": {"items": items, "op": "AND"},
                    "expression": "A",
                    "disabled": False,
                    "stepInterval": 60,
                    "having": [],
                    "limit": limit,
                    "orderBy": [{"columnName": "timestamp", "order": "desc"}],
                    "groupBy": [],
                    "legend": "",
                    "reduceTo": "avg",
                    "offset": offset,
                    "pageSize": limit,
                }
            },
        },
    }


def metrics_graph_query(
    start_ms: int,
    end_ms: int,
    metric_name: str,
    *,
    step_interval: int = 60,
) -> dict[str, Any]:
    return {
        "start": start_ms,
        "end": end_ms,
        "step": step_interval,
        "variables": {},
        "compositeQuery": {
            "queryType": "builder",
            "panelType": "graph",
            "fillGaps": False,
            "builderQueries": {
                "A": {
                    "dataSource": "metrics",
                    "queryName": "A",
                    "aggregateOperator": "count",
                    "aggregateAttribute": {
                        "key": metric_name,
                        "dataType": "float64",
                        "type": "",
                        "isColumn": False,
                        "isJSON": False,
                        "id": f"{metric_name}--float64----false",
                    },
                    "timeAggregation": "rate",
                    "spaceAggregation": "sum",
                    "functions": [],
                    "filters": {"items": [], "op": "AND"},
                    "expression": "A",
                    "disabled": False,
                    "stepInterval": step_interval,
                    "having": [],
                    "limit": None,
                    "orderBy": [],
                    "groupBy": [],
                    "legend": "",
                    "reduceTo": "avg",
                }
            },
        },
    }


def service_equals(name: str) -> dict[str, Any]:
    return _filter_item("=", _resource_key("service.name"), name)


def service_not_in(names: list[str]) -> dict[str, Any]:
    return _filter_item("nin", _resource_key("service.name"), names)


def severity_in(levels: list[str]) -> dict[str, Any]:
    return _filter_item("in", _tag_key("severity_text"), levels)


def body_contains(text: str) -> dict[str, Any]:
    key = {"key": "body", "dataType": "string", "type": "", "isColumn": True, "isJSON": False}
    return _filter_item("contains", key, text)


def trace_id_equals(trace_id: str) -> dict[str, Any]:
    return _filter_item("=", _tag_key("trace_id"), trace_id)


def trace_id_attr_equals(trace_id: str) -> dict[str, Any]:
    key = {"key": "traceId", "dataType": "string", "type": "", "isColumn": True, "isJSON": False}
    return _filter_item("=", key, trace_id)
