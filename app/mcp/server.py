from __future__ import annotations

import json
import sys
from typing import Any

from app.mcp.tool_layer import MCPToolLayer


def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(layer: MCPToolLayer, request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("id")
    method = request.get("method")

    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "pet-medical-records", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        )
    if method == "tools/list":
        return _response(request_id, {"tools": layer.list_tools()})
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            return _error(request_id, -32602, "tools/call requires params.name")
        result = layer.call_tool(name, arguments)
        return _response(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False),
                    }
                ]
            },
        )

    return _error(request_id, -32601, f"Unknown method: {method}")


def main() -> None:
    layer = MCPToolLayer()
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            response = handle_request(layer, request)
        except Exception as exc:  # noqa: BLE001 - stdio servers must return structured errors.
            response = _error(request_id, -32000, str(exc))
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
