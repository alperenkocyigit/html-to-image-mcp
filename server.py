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
    """Validate if the URL is properly formatted"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False

def is_valid_html(content: str) -> bool:
    """Basic HTML validation"""
    return isinstance(content, str) and len(content.strip()) > 0

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="take_screenshot",
            description="Take a screenshot of a webpage or HTML content and upload to Cloudinary",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the webpage to screenshot"
                    },
                    "html": {
                        "type": "string",
                        "description": "HTML content to render and screenshot"
                    },
                    "width": {
                        "type": "integer",
                        "description": "Viewport width in pixels",
                        "default": 1280
                    },
                    "height": {
                        "type": "integer",
                        "description": "Viewport height in pixels",
                        "default": 720
                    },
                    "fullPage": {
                        "type": "boolean",
                        "description": "Capture full page height",
                        "default": False
                    }
                },
                "oneOf": [
                    {"required": ["url"]},
                    {"required": ["html"]}
                ]
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
    html = arguments.get("html")
    width = arguments.get("width", 1280)
    height = arguments.get("height", 720)
    full_page = arguments.get("fullPage", False)
    
    # Validate input
    if not url and not html:
        raise ValueError("Either 'url' or 'html' parameter is required")
    
    if url and html:
        raise ValueError("Cannot specify both 'url' and 'html' parameters")
    
    if url and not is_valid_url(url):
        raise ValueError(f"Invalid URL format: {url}")
    
    if html and not is_valid_html(html):
        raise ValueError("Invalid HTML content provided")
    
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
        
        # Navigate to URL or set HTML content
        if url:
            try:
                await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})
            except Exception as e:
                raise ValueError(f"Failed to navigate to URL: {str(e)}")
        else:
            await page.setContent(html, {'waitUntil': 'networkidle2'})
        
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
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Screenshot uploaded successfully!\nURL: {upload_result['secure_url']}\nPublic ID: {upload_result['public_id']}"
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
        raise ValueError(f"Screenshot failed: {str(e)}")

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
