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

import mcp.types as types
from mcp.server import FastMCP
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

# Create FastMCP server with SSE support
server = FastMCP(
    "html-to-image",
    host="0.0.0.0",  # Listen on all interfaces for container deployment
    port=8000
)

def is_valid_url(url: str) -> bool:
    """Validate if the URL is properly formatted and starts with http:// or https://"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False

@server.tool()
async def take_screenshot(
    url: str,
    width: int = 1280,
    height: int = 720,
    fullPage: bool = False
) -> str:
    """
    Take a screenshot of a webpage by providing its URL and upload to Cloudinary.
    
    Args:
        url: URL of the webpage to screenshot. Must be a valid web address starting with https:// or http://
        width: Viewport width in pixels (optional, default: 1280)
        height: Viewport height in pixels (optional, default: 720)
        fullPage: Capture full page height instead of viewport only (optional, default: false)
    
    Returns:
        JSON string with screenshot information including the Cloudinary URL
    """
    # Check Cloudinary configuration
    if not all([os.getenv('CLOUDINARY_CLOUD_NAME'), os.getenv('CLOUDINARY_API_KEY'), os.getenv('CLOUDINARY_API_SECRET')]):
        raise ValueError("Cloudinary credentials not found in environment variables")
    
    # Validate URL
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
            'fullPage': fullPage
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
                    "fullPage": fullPage
                }
            }
            return json.dumps(response, indent=2)
            
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

def main():
    """Main entry point for the server"""
    # Check if we should run in streamable-http mode (default for container) or stdio mode
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    
    if transport == "stdio":
        # Run in stdio mode for local development
        server.run(transport="stdio")
    else:
        # Run in streamable-http mode for HTTP deployments (Smithery-compatible)
        server.run(transport="streamable-http")

if __name__ == "__main__":
    main()
