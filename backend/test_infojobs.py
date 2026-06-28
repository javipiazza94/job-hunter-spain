import asyncio
import shutil
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        executable_path = shutil.which("chromium") or shutil.which("chromium-browser")
        browser = await p.chromium.launch(headless=True, executable_path=executable_path)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        print("Navigating...")
        await page.goto("https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword=python")
        await page.wait_for_timeout(3000)
        
        # Get elements
        results = await page.evaluate('''() => {
            const cards = Array.from(document.querySelectorAll('li.sui-AtomCard'));
            return cards.map(c => {
                const a = c.querySelector('a');
                return {
                    title: a ? a.innerText : null,
                    url: a ? a.href : null,
                    text: c.innerText
                }
            }).slice(0, 3);
        }''')
        print(results)
        
        await browser.close()

asyncio.run(run())
