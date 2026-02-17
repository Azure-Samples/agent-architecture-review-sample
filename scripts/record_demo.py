"""Record a demo video of the Architecture Review Agent using the microservices banking scenario."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SCENARIO_FILE = Path(__file__).resolve().parent.parent / "scenarios" / "microservices_banking.yaml"
VIDEO_DIR = Path(__file__).resolve().parent.parent / "screenshots"

async def main():
    scenario_content = SCENARIO_FILE.read_text(encoding="utf-8")
    VIDEO_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        # 1. Navigate to the app
        print("1. Opening app...")
        await page.goto("http://localhost:5173")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 2. Paste the microservices banking scenario
        print("2. Pasting microservices banking scenario...")
        textarea = page.locator("textarea")
        await textarea.click()
        await textarea.fill(scenario_content)
        await page.wait_for_timeout(1500)

        # 3. Click Review Architecture
        print("3. Clicking Review Architecture...")
        await page.get_by_role("button", name="Review Architecture").click()

        # 4. Wait for results
        print("4. Waiting for results...")
        await page.wait_for_selector("text=Executive Summary", timeout=30000)
        await page.wait_for_timeout(2000)

        # 5. Scroll to Executive Summary
        print("5. Showing Executive Summary...")
        await page.evaluate("window.scrollTo({ top: 450, behavior: 'smooth' })")
        await page.wait_for_timeout(2500)

        # 6. Diagram tab
        print("6. Diagram tab...")
        await page.get_by_role("button", name="Diagram").click()
        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollTo({ top: 650, behavior: 'smooth' })")
        await page.wait_for_timeout(2500)

        # 7. Risks tab
        print("7. Risks tab...")
        await page.get_by_role("button", name="Risks").click()
        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollTo({ top: 550, behavior: 'smooth' })")
        await page.wait_for_timeout(2500)

        # Scroll further to show more risks
        await page.evaluate("window.scrollTo({ top: 900, behavior: 'smooth' })")
        await page.wait_for_timeout(2000)

        # 8. Components tab
        print("8. Components tab...")
        await page.get_by_role("button", name="Components").click()
        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollTo({ top: 550, behavior: 'smooth' })")
        await page.wait_for_timeout(2500)

        # Scroll further to show more components
        await page.evaluate("window.scrollTo({ top: 900, behavior: 'smooth' })")
        await page.wait_for_timeout(2000)

        # 9. Recommendations tab
        print("9. Recommendations tab...")
        await page.get_by_role("button", name="Recommendations").click()
        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollTo({ top: 550, behavior: 'smooth' })")
        await page.wait_for_timeout(2500)

        # 10. Scroll back to top
        print("10. Scrolling back to top...")
        await page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        await page.wait_for_timeout(2000)

        # Close to finalize the video
        video_path = await page.video.path()
        print(f"Video recording path: {video_path}")
        await context.close()
        await browser.close()

        print(f"Done! Video saved at: {video_path}")
        return video_path

if __name__ == "__main__":
    asyncio.run(main())
