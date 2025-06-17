import asyncio
import sys
from pyppeteer import launch

async def download_chromium():
    """Download Chromium browser during setup"""
    print("Downloading Chromium...")
    try:
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
        
        # Test basic functionality
        page = await browser.newPage()
        await page.goto('data:text/html,<h1>Test</h1>')
        await page.screenshot({'type': 'png'})
        
        await browser.close()
        print("Chromium download and test completed successfully!")
        
    except Exception as e:
        print(f"Error downloading Chromium: {e}")
        print("This might be due to missing dependencies or network issues.")
        print("Try installing: sudo apt-get install -y gconf-service libasound2 libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 ca-certificates fonts-liberation libappindicator1 libnss3 lsb-release xdg-utils wget")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(download_chromium())
