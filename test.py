import asyncio
from playwright.async_api import async_playwright
import os

CLAN_TAG = "MRLN"

async def test_local_file():
    # Find the absolute path to your saved HTML file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "Глобальная карта для кланов World of Tanks.html")
    
    if not os.path.exists(file_path):
        print(f"❌ Error: Cannot find the file at: {file_path}")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Open the local file directly
        print(f"🌐 Opening local file: {file_path}")
        await page.goto(f"file://{file_path}")
        
        expected_tags = [f"[{CLAN_TAG}]", CLAN_TAG]

        # 1. Check Left Side (Base 1)
        left_column = page.locator(".box_part__left")
        if await left_column.count() > 0:
            tags = left_column.locator(".clan-name_tag")
            count = await tags.count()
            for i in range(count):
                text = await tags.nth(i).text_content()
                if text and text.strip().upper() in [t.upper() for t in expected_tags]:
                    print("➡️ RESULT: Spawn 1 (Base 1 / Left Side / North-West)")
                    await browser.close()
                    return

        # 2. Check Right Side (Base 2)
        right_column = page.locator(".box_part__right")
        if await right_column.count() > 0:
            tags = right_column.locator(".clan-name_tag")
            count = await tags.count()
            for i in range(count):
                text = await tags.nth(i).text_content()
                if text and text.strip().upper() in [t.upper() for t in expected_tags]:
                    print("➡️ RESULT: Spawn 2 (Base 2 / Right Side / South-East)")
                    await browser.close()
                    return

        print("❌ RESULT: Clan tag was not found inside either side container.")
        await browser.close()

asyncio.run(test_local_file())