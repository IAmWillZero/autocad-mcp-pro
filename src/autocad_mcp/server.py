"""Servidor MCP delgado: cablea el servicio CAD con el transporte stdio.

Implementado sobre la API v2 del SDK ``mcp`` (handlers ``on_*`` en el constructor).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import mcp.server.stdio
from mcp.server import Server, ServerRequestContext
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
)

from autocad_mcp import __version__
from autocad_mcp.config import get_config
from autocad_mcp.obs import configure_logging, log
from autocad_mcp.service import AutoCADService
from autocad_mcp.tools import build_handlers, list_tool_schemas

SERVER_NAME = "autocad-mcp-pro"


class AutoCADMCPServer:
    """Orquesta el servicio CAD y expone sus herramientas por MCP."""

    def __init__(self, service: AutoCADService | None = None) -> None:
        self.service = service or AutoCADService()
        self.handlers = build_handlers(self.service)
        self.server: Server[Any] = Server(
            SERVER_NAME,
            version=__version__,
            on_list_tools=self._handle_list_tools,
            on_call_tool=self._handle_call_tool,
        )

    async def _handle_list_tools(
        self,
        ctx: ServerRequestContext[Any],
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        return ListToolsResult(tools=list_tool_schemas())

    async def _handle_call_tool(
        self, ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        name = params.name
        arguments = params.arguments or {}
        start = time.perf_counter()
        try:
            handler = self.handlers.get(name)
            if handler is None:
                result: dict[str, Any] = {"error": f"Unknown tool: {name}"}
            else:
                result = handler(arguments)
            self.service.metrics.record_call(time.perf_counter() - start)
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(result, indent=2))],
                is_error=False,
            )
        except Exception as exc:  # noqa: BLE001
            self.service.metrics.record_error()
            log.error("tool_call_failed", tool=name, error=str(exc))
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps({"error": f"Error calling tool {name}: {exc}"}),
                    )
                ],
                is_error=True,
            )

    async def serve(self) -> None:
        """Arranca el bucle stdio del servidor MCP."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def main() -> None:
    """Punto de entrada asincrono."""
    configure_logging(get_config().log_level)

    service = AutoCADService()
    if not service.connect():
        log.warning("initial_connection_failed", hint="AutoCAD debe estar abierto")

    server = AutoCADMCPServer(service)
    await server.serve()


def run() -> None:
    """Entrypoint sincrono (console script)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
