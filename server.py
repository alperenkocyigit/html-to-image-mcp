import asyncio
import base64
import json
import sys
import os
from urllib.parse import urlparse
from typing import Any, Sequence
import tempfile
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
from pydantic import AnyUrl
from pyppeteer import launch
import json

# Load environment variables
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

server = Server("html-to-image")

def is_valid_url(url: str) -> bool:
    """Validate if the URL is properly formatted and starts with http:// or https://"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="take_screenshot",
            description="Take a screenshot of a webpage by providing its URL and upload to Cloudinary. The URL must be a valid web address starting with https:// or http://",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the webpage to screenshot. Must be a valid web address starting with https:// or http://"
                    },
                    "width": {
                        "type": "integer",
                        "description": "Viewport width in pixels (optional, default: 1280)",
                        "default": 1280
                    },
                    "height": {
                        "type": "integer",
                        "description": "Viewport height in pixels (optional, default: 720)",
                        "default": 720
                    },
                    "fullPage": {
                        "type": "boolean",
                        "description": "Capture full page height instead of viewport only (optional, default: false)",
                        "default": False
                    }
                },
                "required": ["url"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""
    if name != "take_screenshot":
        raise ValueError(f"Unknown tool: {name}")
    
    if not arguments:
        raise ValueError("No arguments provided")
    
    # Check Cloudinary configuration
    if not all([os.getenv('CLOUDINARY_CLOUD_NAME'), os.getenv('CLOUDINARY_API_KEY'), os.getenv('CLOUDINARY_API_SECRET')]):
        raise ValueError("Cloudinary credentials not found in environment variables")
    
    # Extract parameters
    url = arguments.get("url")
    width = arguments.get("width", 1280)
    height = arguments.get("height", 720)
    full_page = arguments.get("fullPage", False)
    
    # Validate required URL parameter
    if not url:
        raise ValueError("The 'url' parameter is required and must be provided")
    
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL format: {url}. URL must be a valid web address starting with https:// or http://")
    
    browser = None
    try:
        # Launch browser
        browser = await launch(
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ],
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False
        )
        
        page = await browser.newPage()
        await page.setViewport({'width': width, 'height': height})
        
        # Navigate to URL
        try:
            await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})
        except Exception as e:
            raise ValueError(f"Failed to navigate to URL '{url}': {str(e)}. Please ensure the URL is accessible and starts with https:// or http://")
        
        # Take screenshot
        screenshot_options = {
            'type': 'png',
            'fullPage': full_page
        }
        
        screenshot_bytes = await page.screenshot(screenshot_options)
        await browser.close()
        browser = None
        
        # Upload to Cloudinary
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_file.write(screenshot_bytes)
                temp_file_path = temp_file.name
            
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                temp_file_path,
                folder="screenshots",
                resource_type="image"
            )
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            response = {
                "status": 200,
                "message": "Screenshot captured and uploaded successfully",
                "url": upload_result['secure_url'],
                "public_id": upload_result['public_id'],
                "dimensions": {
                    "width": width,
                    "height": height,
                    "fullPage": full_page
                }
            }
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(response, indent=2)
                )
            ]
            
        except Exception as e:
            raise ValueError(f"Failed to upload screenshot to Cloudinary: {str(e)}")
        
    except Exception as e:
        # Ensure browser is closed on error
        if browser:
            try:
                await browser.close()
            except:
                pass
        raise ValueError(f"Screenshot operation failed: {str(e)}")

async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="html-to-image",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
