from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from app import url_to_cloudinary_url

# Initialize MCP server
mcp = FastMCP("html-to-image-mcp")

@mcp.tool()
async def take_screenshot(url: str) -> Dict[str, Any]:
    """Returns a screenshot cdn url of the given website URL."""
    return url_to_cloudinary_url(url)

if __name__ == "__main__":
    mcp.run(transport="stdio")
