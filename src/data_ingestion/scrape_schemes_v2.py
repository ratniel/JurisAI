import asyncio
from loguru import logger
from playwright.async_api import async_playwright

from config.settings import settings
# from .data_models import SchemeDetails


class ScrapeSchemes:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.scheme_search_url = settings.base_url + "/search"

        logger.info("Launching browser")

    async def __aenter__(self):
        # Create playwright instance
        self.playwright = await async_playwright().start()

        # Launch browser
        self.browser = await self.playwright.chromium.launch()

        # Create browser context (optional but recommended)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        logger.info("Browser launched")
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # Clean up resources in reverse order
        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed")

    async def scrape_all_schemes(self):
        """
        1. Load search page
        2. Get all scheme urls
        3. Scrape each scheme with scrape_scheme
        4. Return all scraped schemes
        """
        async with self:
            search_page = await self.context.new_page()
            await search_page.goto(self.scheme_search_url)
            container_selector = (
                "div.sm\\:col-span-3.col-span-4.items-center.justify-center"
            )
            await search_page.wait_for_selector(container_selector, state="visible")
            logger.info("Search page loaded")

            scheme_divs = await search_page.get_by_role("article").all()

            schemes = {
                await scheme_div.get_by_role("link").text_content(): settings.base_url + await scheme_div.get_by_role("link").get_attribute("href")
                for scheme_div in scheme_divs
            }

            # for scheme_url in scheme_urls:
            #     await self.scrape_scheme(scheme_url)

            return schemes

    async def scrape_scheme(self, scheme_name: str, scheme_url: str):
        """
        1. Load scheme page
        2. Scrape scheme details
        3. Return scraped scheme
        """
        async with self:
            scheme_page = await self.context.new_page()
            logger.info(f"Scraping scheme: {scheme_name} from {scheme_url}")
            await scheme_page.goto(scheme_url)
            await scheme_page.wait_for_selector("div.scrollDiv")
            logger.info("Scheme page loaded")

            
        # return SchemeDetails()
        pass


if __name__ == "__main__":
    from rich import print

    # URL = ""
    # print(asyncio.run(ScrapeSchemes().scrape_scheme(URL)))

    print(asyncio.run(ScrapeSchemes().scrape_all_schemes()))
