"""
MCP servers (FastMCP / the official Python SDK): a receipt for every tool call.

    from sebbi.integrations.mcp import sealed

    @mcp.tool()
    @sealed("lookup_customer")
    def lookup_customer(customer_id: str) -> dict:
        ...

The function's signature is preserved, so the MCP schema is unchanged.
"""
import sebbi

sealed = sebbi.receipt
