# server.py
import os
from typing import Annotated
from pydantic import Field

from mcp.server.fastmcp import FastMCP

port = os.environ.get("PORT", 8000)
mcp = FastMCP("calculator", port=port)


@mcp.tool()
def subtract(a: int, b: Annotated[int, Field(description="The second number to subtract")]) -> int:
    """Substract two numbers.

    Args:
        a: The first number to subtract.
        b: The second number to subtract.
    """
    return a - b


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
