import os
import asyncio
import io

import requests
from pyppeteer import launch
import cloudinary
import cloudinary.uploader

# 1) Cloudinary konfigürasyonu (env var’lardan)
cloudinary.config( 
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

async def _capture_png_bytes(url: str, width: int = 1280, height: int = 720) -> bytes:
    """
    Pyppeteer ile verilen URL'in 1280×720 screenshot'unu alır ve
    PNG bytes olarak döner.
    """
    browser = await launch(
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--single-process"
        ],
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False
    )
    page = await browser.newPage()
    await page.setViewport({"width": width, "height": height})
    await page.goto(url, {"waitUntil": "networkidle2"})
    img_bytes = await page.screenshot({"type": "png", "fullPage": False})
    await browser.close()
    return img_bytes

def url_to_cloudinary_url(url: str, folder: str = "screenshots") -> str:
    """
    Senkron wrapper:
        >>> url_to_cloudinary_url("https://www.alperenkocyigit.github.io")
    return: Cloudinary üzerindeki public CDN linki
    """
    # 1) Sayfanın 1280×720 ekran görüntüsünü al (bytes)
    img_bytes = asyncio.get_event_loop().run_until_complete(_capture_png_bytes(url))

    # 2) BytesIO'a sar, Cloudinary'a yükle
    byte_stream = io.BytesIO(img_bytes)
    byte_stream.name = "screenshot.png"  # Cloudinary SDK için filename

    upload_result = cloudinary.uploader.upload(
        byte_stream,
        folder=folder,
        resource_type="image",
        use_filename=True,
        unique_filename=True,
        overwrite=False
    )

    # 3) secure_url alanını döndür
    return upload_result["secure_url"]