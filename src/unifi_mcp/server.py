"""MCP server implementation for UniFi."""

from mcp.server import Server

server = Server("unifi-mcp")


def main() -> None:
    """Run the MCP server."""
    import asyncio

    from mcp.server.stdio import stdio_server

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
