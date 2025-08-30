import asyncio
from loguru import logger
from playwright.async_api import async_playwright

from config.settings import settings
from data_ingestion.data_models import SchemeDetails
from data_ingestion.utils.scheme_details_utils import (
    scrape_scheme_details,
    scrape_scheme_faqs,
    scrape_scheme_sources_and_references
)


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

            # for scheme_name, scheme_url in schemes.items():
            #     scheme = await self.scrape_scheme(scheme_name, scheme_url)
            #     save_to_mongo(scheme, collection_name="schemes")

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
            scroll_div = scheme_page.locator("#scrollDiv")
            await scroll_div.wait_for(state='visible')
            logger.info("Scheme page loaded")

            # scheme provider
            scheme_details_header = scroll_div.locator("div.flex-1") # css selector
            scheme_provider = await scheme_details_header.locator("h3").text_content()
            provider_parts = scheme_provider.split(" ")
            level = "central" if len(provider_parts) > 2 else "state"

            # tags
            tags_div = await scroll_div.locator("div.mb-2.md\\:mb-0.w-full").get_by_role("button").all() # css selector
            tags = [await tag.text_content() for tag in tags_div]

            # details, benefits, eligibility, application_process and documents_required
            detail_sections = scroll_div.locator("> div[id]")
            scheme_data = await scrape_scheme_details(detail_sections)

            # faqs
            faqs = await scrape_scheme_faqs(detail_sections)

            # sources and references
            sources = await scrape_scheme_sources_and_references(detail_sections)
           
            return SchemeDetails(
                url=scheme_url,
                name=scheme_name,
                level=level,
                provider=scheme_provider,
                tags=tags,
                details=scheme_data.get("details", ""),
                benefits=scheme_data.get("benefits", ""),
                eligibility=scheme_data.get("eligibility", ""),
                application_process=scheme_data.get("application_process", ""),
                documents_required=scheme_data.get("documents_required", ""),
                faqs=faqs,
                sources=sources
            )


if __name__ == "__main__":
    from rich import print

    SCHEME_NAME = "Prime Minister’s Fellowship for Doctoral Research"
    URL = "https://www.myscheme.gov.in/schemes/pmfdr"
    print(asyncio.run(ScrapeSchemes().scrape_scheme(SCHEME_NAME, URL)))

    # print(asyncio.run(ScrapeSchemes().scrape_all_schemes()))
