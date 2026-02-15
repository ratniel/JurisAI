import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from pymongo import ReplaceOne
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.mongo_client import AsyncMongoClient

# Ensure `src.*` imports work when this file is executed directly by path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.data_ingestion.data_models import SchemeDetails
from src.data_ingestion.utils.scheme_details_utils import (
    scrape_scheme_details,
    scrape_scheme_faqs,
    scrape_scheme_sources_and_references,
)
from src.db.mongodb_setup import close_database_connection, init_database


class ScrapeSchemes:
    def __init__(self) -> None:
        self.settings = settings
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.client: AsyncMongoClient[dict[str, Any]] | None = None
        self.scheme_search_url = self.settings.base_url + "/search"
        base_url = urlparse(self.settings.base_url)
        if not base_url.scheme or not base_url.netloc:
            raise ValueError("settings.base_url must include scheme and host.")
        self.base_url_scheme = base_url.scheme
        self.base_url_netloc = base_url.netloc
        self.batch_size = 100
        self.max_concurrency = 6

        logger.info("Launching browser")

    async def __aenter__(self) -> "ScrapeSchemes":
        # Create playwright instance
        self.playwright = await async_playwright().start()

        # Launch browser
        self.browser = await self.playwright.chromium.launch()

        # Create browser context (optional but recommended)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        logger.info("Browser launched")

        # Initialize database connection
        self.client = await init_database()
        logger.info("Database connection initialized")

        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        # Clean up resources in reverse order
        if self.context is not None:
            await self.context.close()

        if self.browser is not None:
            await self.browser.close()

        if self.playwright is not None:
            await self.playwright.stop()
        logger.info("Browser closed")

        # Close database connection
        await close_database_connection(self.client)
        logger.info("Database connection closed")

    def _require_context(self) -> BrowserContext:
        if self.context is None:
            raise RuntimeError("Browser context is not initialized.")
        return self.context

    def _resolve_scheme_url(self, href: str) -> str | None:
        normalized_url = urljoin(f"{self.settings.base_url.rstrip('/')}/", href.strip())
        parsed_url = urlparse(normalized_url)
        if (
            parsed_url.scheme != self.base_url_scheme
            or parsed_url.netloc != self.base_url_netloc
        ):
            logger.warning(f"Skipping external scheme URL: {href}")
            return None
        return normalized_url

    async def _bulk_upsert_schemes(self, schemes: Sequence[SchemeDetails]) -> int:
        if not schemes:
            return 0

        collection: AsyncCollection[dict[str, Any]] = (
            SchemeDetails.get_pymongo_collection()
        )
        operations = [
            ReplaceOne(
                filter={"url": scheme.url},
                replacement=scheme.model_dump(exclude_none=True),
                upsert=True,
            )
            for scheme in schemes
        ]
        result = await collection.bulk_write(operations, ordered=False)
        return result.upserted_count + result.matched_count

    async def _find_existing_schemes(
        self,
        schemes_on_page: dict[str, str],
    ) -> tuple[set[str], set[str]]:
        if not schemes_on_page:
            return set(), set()

        collection: AsyncCollection[dict[str, Any]] = (
            SchemeDetails.get_pymongo_collection()
        )
        query = {
            "$or": [
                {"url": {"$in": list(set(schemes_on_page.values()))}},
                {"name": {"$in": list(set(schemes_on_page.keys()))}},
            ]
        }
        docs = await collection.find(query, {"_id": 0, "url": 1, "name": 1}).to_list(
            length=None
        )

        existing_urls = {doc["url"] for doc in docs if isinstance(doc.get("url"), str)}
        existing_names = {
            doc["name"] for doc in docs if isinstance(doc.get("name"), str)
        }
        return existing_urls, existing_names

    async def _scrape_scheme_safe(
        self,
        scheme_name: str,
        scheme_url: str,
        semaphore: asyncio.Semaphore,
    ) -> SchemeDetails | None:
        async with semaphore:
            try:
                return await self.scrape_scheme(scheme_name, scheme_url)
            except Exception as e:
                logger.error(f"Error scraping scheme: {scheme_name}. Error: {e}")
                return None

    async def scrape_all_schemes(self) -> int:
        """
        1. Load search page
        2. Get all scheme urls
        3. Scrape each scheme with scrape_scheme
        4. Return all scraped schemes
        """
        try:
            async with self:
                # Load search page
                search_page: Page = await self._require_context().new_page()
                await search_page.goto(self.scheme_search_url)
                container_selector = (
                    "div.sm\\:col-span-3.col-span-4.items-center.justify-center"
                )
                await search_page.wait_for_selector(container_selector, state="visible")

                saved_count = 0
                scraped_count = 0
                scheme_batch: list[SchemeDetails] = []
                page_num = 0
                while True:
                    scheme_divs = await search_page.get_by_role("article").all()
                    schemes_on_page: dict[str, str] = {}
                    for scheme_div in scheme_divs:
                        link_locator = scheme_div.get_by_role("link")
                        scheme_name = (await link_locator.text_content() or "").strip()
                        href = await link_locator.get_attribute("href")
                        if not scheme_name or not href:
                            continue

                        scheme_url = self._resolve_scheme_url(href)
                        if scheme_url is None:
                            continue
                        schemes_on_page[scheme_name] = scheme_url

                    existing_urls, existing_names = await self._find_existing_schemes(
                        schemes_on_page
                    )
                    schemes_to_scrape = [
                        (scheme_name, scheme_url)
                        for scheme_name, scheme_url in schemes_on_page.items()
                        if scheme_url not in existing_urls
                        and scheme_name not in existing_names
                    ]
                    skipped_existing_count = len(schemes_on_page) - len(
                        schemes_to_scrape
                    )
                    if skipped_existing_count > 0:
                        logger.info(
                            f"Skipping {skipped_existing_count} already-known schemes (url or name match)."
                        )

                    semaphore = asyncio.Semaphore(self.max_concurrency)
                    scrape_tasks = [
                        self._scrape_scheme_safe(scheme_name, scheme_url, semaphore)
                        for scheme_name, scheme_url in schemes_to_scrape
                    ]
                    scraped_schemes = await asyncio.gather(*scrape_tasks)
                    for scheme in scraped_schemes:
                        if scheme is None:
                            continue

                        scheme_batch.append(scheme)
                        scraped_count += 1

                        if len(scheme_batch) >= self.batch_size:
                            saved_count += await self._bulk_upsert_schemes(scheme_batch)
                            logger.info(
                                f"Persisted batch of {len(scheme_batch)} schemes in MongoDB"
                            )
                            scheme_batch.clear()

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
                    logger.success(
                        (
                            f"Page {page_num} scraped. "
                            f"Scraped {scraped_count}, persisted {saved_count}."
                        )
                    )

                if scheme_batch:
                    saved_count += await self._bulk_upsert_schemes(scheme_batch)
                    logger.info(
                        f"Persisted final batch of {len(scheme_batch)} schemes in MongoDB"
                    )

                logger.success(
                    f"Scraping complete. Scraped {scraped_count}, persisted {saved_count}."
                )
                return scraped_count
        except Exception as e:
            logger.error(f"Error in scrape_all_schemes: {e}")
            raise

    async def scrape_scheme(self, scheme_name: str, scheme_url: str) -> SchemeDetails:
        """
        1. Load scheme page in a new tab.
        2. Scrape scheme details.
        3. Close the tab and return the scraped scheme.
        NOTE: This method assumes the browser context is already managed.
        """
        scheme_page = await self._require_context().new_page()
        try:
            logger.info(f"Scraping scheme: {scheme_name} from {scheme_url}")
            await scheme_page.goto(scheme_url)
            scroll_div = scheme_page.locator("#scrollDiv")
            await scroll_div.wait_for(state="visible")

            # scheme provider
            scheme_details_header = scroll_div.locator("div.flex-1")
            provider_text = await scheme_details_header.locator(
                "h3"
            ).first.text_content()
            scheme_provider = (provider_text or "").strip() or "Unknown provider"
            provider_parts = scheme_provider.split(" ")
            is_central = provider_parts[0].lower() == "ministry"
            level = "central" if is_central else "state"

            # tags
            tags_div = (
                await scroll_div.locator("div.mb-2.md\\:mb-0.w-full")
                .get_by_role("button")
                .all()
            )
            tags: list[str] = []
            for tag in tags_div:
                tag_text = (await tag.text_content() or "").strip()
                if tag_text:
                    tags.append(tag_text)

            # details, benefits, eligibility, etc.
            detail_sections = scroll_div.locator("> div[id]")
            scheme_data = await scrape_scheme_details(detail_sections)
            faqs = await scrape_scheme_faqs(detail_sections)
            sources = await scrape_scheme_sources_and_references(detail_sections)
            logger.success(f"{scheme_name} scraped successfully")

            return SchemeDetails(
                url=scheme_url,
                name=scheme_name,
                level=level,
                provider=scheme_provider,
                tags=tags,
                details=scheme_data.get("details", ""),
                benefits=scheme_data.get("benefits", ""),
                eligibility=scheme_data.get("eligibility", ""),
                application_process=scheme_data.get("application-process", ""),
                documents_required=scheme_data.get("documents-required", ""),
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
    asyncio.run(ScrapeSchemes().scrape_all_schemes())

    # # TESTING SINGLE SCHEME SCRAPER
    # from rich import print
    # async def main():
    #     scraper = ScrapeSchemes()
    #     async with scraper:
    #         SCHEME_NAME = "Prime Minister’s Fellowship for Doctoral Research"
    #         URL = "https://www.myscheme.gov.in/schemes/pmfdr"
    #         print(await scraper.scrape_scheme(SCHEME_NAME, URL))

    # asyncio.run(main())
