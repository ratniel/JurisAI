from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from src.data_ingestion.scrape_schemes import ScrapeSchemes
from src.scheme_contracts import RawSchemeData


class FakeLink:
    def __init__(
        self,
        *,
        name: str,
        href: str | None = None,
        raise_on_href: bool = False,
    ) -> None:
        self.name = name
        self.href = href
        self.raise_on_href = raise_on_href

    async def text_content(self) -> str:
        return self.name

    async def get_attribute(self, attribute: str) -> str | None:
        if attribute != "href":
            return None
        if self.raise_on_href:
            raise RuntimeError("href read failed")
        return self.href


class FakeArticle:
    def __init__(self, link: FakeLink) -> None:
        self.link = link

    def get_by_role(self, role: str) -> FakeLink:
        if role != "link":
            raise AssertionError(f"Unexpected role: {role}")
        return self.link


class FakeArticleLocator:
    def __init__(self, articles: list[FakeArticle]) -> None:
        self.articles = articles

    async def all(self) -> list[FakeArticle]:
        return self.articles


class FakeNextButton:
    def __init__(
        self,
        *,
        class_name: str = "",
        fail_get_attribute: bool = False,
    ) -> None:
        self.class_name = class_name
        self.fail_get_attribute = fail_get_attribute

    async def get_attribute(self, attribute: str) -> str:
        if attribute != "class":
            return ""
        if self.fail_get_attribute:
            raise RuntimeError("pagination class lookup failed")
        return self.class_name

    async def click(self) -> None:
        return None


class FakeSvgLocator:
    def __init__(self, next_button: FakeNextButton) -> None:
        self.last = next_button


class FakePaginationLocator:
    def __init__(self, next_button: FakeNextButton) -> None:
        self.next_button = next_button

    def locator(self, selector: str) -> FakeSvgLocator:
        if selector != "svg":
            raise AssertionError(f"Unexpected selector: {selector}")
        return FakeSvgLocator(self.next_button)


class FakeSearchPage:
    def __init__(
        self,
        *,
        articles: list[FakeArticle],
        next_button: FakeNextButton,
    ) -> None:
        self.articles = articles
        self.next_button = next_button
        self.closed = False

    async def goto(self, url: str) -> None:
        return None

    async def wait_for_selector(self, selector: str, state: str | None = None) -> None:
        return None

    def get_by_role(self, role: str) -> FakeArticleLocator:
        if role != "article":
            raise AssertionError(f"Unexpected role: {role}")
        return FakeArticleLocator(self.articles)

    def locator(self, selector: str) -> FakePaginationLocator:
        if selector != "ul.list-none.flex.flex-wrap":
            raise AssertionError(f"Unexpected selector: {selector}")
        return FakePaginationLocator(self.next_button)

    async def wait_for_load_state(self, state: str) -> None:
        return None

    async def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, search_page: FakeSearchPage) -> None:
        self.search_page = search_page

    async def new_page(self) -> FakeSearchPage:
        return self.search_page


class StubScraper(ScrapeSchemes):
    def __init__(self, search_page: FakeSearchPage) -> None:
        super().__init__()
        self._search_page = search_page

    async def __aenter__(self) -> "StubScraper":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def _require_context(self) -> FakeContext:
        return FakeContext(self._search_page)


def make_scheme(name: str, url: str) -> RawSchemeData:
    return RawSchemeData(
        url=url,
        name=name,
        level="state",
        provider="Government of Maharashtra",
        tags=["Agriculture"],
        details="details",
        benefits="benefits",
        eligibility="eligibility",
        application_process="apply",
        documents_required="documents",
        faq="faq",
        sources=[],
    )


class ScrapeSchemesTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_schemes_on_page_skips_unreadable_cards(self) -> None:
        scraper = StubScraper(
            FakeSearchPage(
                articles=[
                    FakeArticle(FakeLink(name="Readable", href="/schemes/readable")),
                    FakeArticle(FakeLink(name="Broken", raise_on_href=True)),
                ],
                next_button=FakeNextButton(class_name="cursor-not-allowed"),
            )
        )

        schemes_on_page = await scraper._collect_schemes_on_page(
            scraper._search_page,
            page_num=0,
        )

        self.assertEqual(
            schemes_on_page,
            {"Readable": "https://www.myscheme.gov.in/schemes/readable"},
        )

    async def test_scrape_all_schemes_flushes_pending_batch_on_pagination_failure(
        self,
    ) -> None:
        search_page = FakeSearchPage(
            articles=[FakeArticle(FakeLink(name="Scheme A", href="/schemes/a"))],
            next_button=FakeNextButton(fail_get_attribute=True),
        )
        scraper = StubScraper(search_page)
        scraped_scheme = make_scheme(
            "Scheme A",
            "https://www.myscheme.gov.in/schemes/a",
        )
        persisted_batches: list[list[RawSchemeData]] = []

        async def record_bulk_upsert(batch: list[RawSchemeData]) -> int:
            persisted_batches.append(list(batch))
            return len(batch)

        with (
            patch.object(
                scraper,
                "_find_existing_schemes",
                AsyncMock(return_value=(set(), {})),
            ),
            patch.object(
                scraper,
                "_scrape_scheme_safe",
                AsyncMock(return_value=scraped_scheme),
            ),
            patch.object(
                scraper,
                "_bulk_upsert_schemes",
                AsyncMock(side_effect=record_bulk_upsert),
            ) as bulk_upsert,
        ):
            scraped_count = await scraper.scrape_all_schemes()

        self.assertEqual(scraped_count, 1)
        self.assertEqual(bulk_upsert.await_count, 1)
        self.assertEqual(len(persisted_batches), 1)
        persisted_batch = persisted_batches[0]
        self.assertEqual(len(persisted_batch), 1)
        self.assertEqual(persisted_batch[0].url, "https://www.myscheme.gov.in/schemes/a")
        self.assertTrue(search_page.closed)


if __name__ == "__main__":
    unittest.main()
