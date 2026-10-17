"""Servidor MCP delgado: cablea el servicio CAD con el transporte stdio."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

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
        self.server = Server(SERVER_NAME)
        self.handlers = build_handlers(self.service)

    def setup_tools(self) -> None:
        """Registra list_tools y call_tool en el servidor MCP."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            return list_tool_schemas()

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
            start = time.perf_counter()
            try:
                handler = self.handlers.get(name)
                if handler is None:
                    result: dict[str, Any] = {"error": f"Unknown tool: {name}"}
                else:
                    result = handler(arguments or {})
                self.service.metrics.record_call(time.perf_counter() - start)
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as exc:  # noqa: BLE001
                self.service.metrics.record_error()
                log.error("tool_call_failed", tool=name, error=str(exc))
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": f"Error calling tool {name}: {exc}"}),
                    )
                ]

    async def serve(self) -> None:
        """Arranca el bucle stdio del servidor MCP."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=SERVER_NAME,
                    server_version=__version__,
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


async def main() -> None:
    """Punto de entrada asincrono."""
    configure_logging(get_config().log_level)

    service = AutoCADService()
    if not service.connect():
        log.warning("initial_connection_failed", hint="AutoCAD debe estar abierto")

    server = AutoCADMCPServer(service)
    server.setup_tools()
    await server.serve()


def run() -> None:
    """Entrypoint sincrono (console script)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
