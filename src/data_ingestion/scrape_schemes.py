import asyncio
from loguru import logger
from playwright.async_api import async_playwright

from config.settings import settings
from data_ingestion.data_models import SchemeDetails
from data_ingestion.utils.scheme_details_utils import (
    scrape_scheme_details,
    scrape_scheme_faqs,
    scrape_scheme_sources_and_references,
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
        try:
            async with self:
                search_page = await self.context.new_page()
                await search_page.goto(self.scheme_search_url)
                container_selector = (
                    "div.sm\\:col-span-3.col-span-4.items-center.justify-center"
                )
                await search_page.wait_for_selector(container_selector, state="visible")

                all_scraped_schemes = []
                page_num = 0
                while True:
                    # TODO: Remove after testing
                    if page_num == 3:
                        break
                    scheme_divs = await search_page.get_by_role("article").all()
                    schemes_on_page = {}
                    for scheme_div in scheme_divs:
                        link_locator = scheme_div.get_by_role("link")
                        scheme_name = await link_locator.text_content()
                        scheme_url = (
                            settings.base_url + await link_locator.get_attribute("href")
                        )
                        schemes_on_page[scheme_name] = scheme_url

                    for scheme_name, scheme_url in schemes_on_page.items():
                        try:
                            scheme = await self.scrape_scheme(scheme_name, scheme_url)
                            all_scraped_schemes.append(scheme)
                        except Exception as e:
                            logger.error(
                                f"Error scraping scheme: {scheme_name}. Error: {e}"
                            )
                            pass

                    # pagination container
                    pagination_ul = search_page.locator("ul.list-none.flex.flex-wrap")
                    next_page_button = pagination_ul.locator("svg").last

                    # check if button is active
                    button_class = await next_page_button.get_attribute("class") or ""
                    if "cursor-not-allowed" in button_class:
                        logger.success("All pages scraped!")
                        break

                    await next_page_button.click()
                    await search_page.wait_for_load_state("networkidle")

                    page_num += 1
                    logger.info(f"Page {page_num} scraped")

                return all_scraped_schemes
        except Exception as e:
            logger.error(f"Error in scrape_all_schemes: {e}")
            raise

    async def scrape_scheme(self, scheme_name: str, scheme_url: str):
        """
        1. Load scheme page in a new tab.
        2. Scrape scheme details.
        3. Close the tab and return the scraped scheme.
        NOTE: This method assumes the browser context is already managed.
        """
        scheme_page = await self.context.new_page()
        try:
            logger.info(f"Scraping scheme: {scheme_name} from {scheme_url}")
            await scheme_page.goto(scheme_url)
            scroll_div = scheme_page.locator("#scrollDiv")
            await scroll_div.wait_for(state="visible")

            # scheme provider
            scheme_details_header = scroll_div.locator("div.flex-1")
            scheme_provider = await scheme_details_header.locator(
                "h3"
            ).first.text_content()
            provider_parts = scheme_provider.split(" ")
            # Heuristic: Assume "central" if provider name has > 2 words, else "state".
            level = "central" if len(provider_parts) > 2 else "state"

            # tags
            tags_div = (
                await scroll_div.locator("div.mb-2.md\\:mb-0.w-full")
                .get_by_role("button")
                .all()
            )
            tags = [await tag.text_content() for tag in tags_div]

            # details, benefits, eligibility, etc.
            detail_sections = scroll_div.locator("> div[id]")
            scheme_data = await scrape_scheme_details(detail_sections)
            faqs = await scrape_scheme_faqs(detail_sections)
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
                sources=sources,
            )
        except Exception as e:
            logger.error(f"Error scraping scheme: {scheme_name}. Error: {e}")
            raise
        finally:
            # avoid memory leaks
            logger.info(f"Scraped {scheme_name}. Closing scheme page...")
            await scheme_page.close()


if __name__ == "__main__":
    from rich import print

    # SCHEME_NAME = "Prime Minister’s Fellowship for Doctoral Research"
    # URL = "https://www.myscheme.gov.in/schemes/pmfdr"
    # print(asyncio.run(ScrapeSchemes().scrape_scheme(SCHEME_NAME, URL)))

    print(asyncio.run(ScrapeSchemes().scrape_all_schemes()))
