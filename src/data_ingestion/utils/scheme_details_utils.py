from loguru import logger
from typing import Dict, List
from playwright.async_api import Locator


async def scrape_scheme_details(detail_sections: Locator) -> Dict[str, str]:
    try:
        target_section_id = ["details", "benefits", "eligibility", "exclusions", "application-process", "documents-required"]
        scheme_data = {}
        section_id = ""
        for section in await detail_sections.all():
            if section_id == "faqs":
                break

            # Get the id of the section to use as the key
            section_id = await section.get_attribute("id")
            
            if section_id and section_id in target_section_id:
                if section_id == "application-process":
                    section_text = await get_application_process_text(section)
                    scheme_data[section_id] = section_text
                    continue
                else:
                    section_text = await section.inner_text()
                # Get the entire inner text, preserving formatting

                # clean string from "Details\nPrime Minister's Fellowship for Do..."
                # to "Prime Minister's Fellowship for Do..."
                section_text_parts = section_text.split("\n")
                section_text = "\n".join(section_text_parts[1:])
                scheme_data[section_id] = section_text

        return scheme_data
    except Exception as e:
        logger.error(f"Error in scrape_scheme_details: {e}")
        raise

async def get_application_process_text(section: Locator) -> str:
    try:
        section_text = await section.inner_text()
        section_text_parts = section_text.split("\n")
        section_text = "\n".join(section_text_parts[1:])

        if section_text.startswith("Online\nOffline"):
            online_process_text = section_text.split("Online\nOffline")[1]

            offline_process_locator = section.locator("div.px-4.py-2.flex.items-start.justify-center.capitalize.hover\\:cursor-pointer").last
            await offline_process_locator.click()
            await offline_process_locator.wait_for(state="visible", timeout=5000)

            # offline_process_text_locator = offline_process_locator.locator("div.markdown-options")
            # offline_process_text = await offline_process_text_locator.inner_text()
            section_text = await section.inner_text()
            offline_process_text = section_text.split("Online\nOffline")[1]

        else:
            return section_text
        return {
            "online": online_process_text,
            "offline": offline_process_text
        }
    except Exception as e:
        logger.error(f"Error in get_application_process_text: {e}")
        raise

async def scrape_scheme_faqs(detail_sections: Locator) -> Dict[str, str]:
    """
    Scrapes all Frequently Asked Questions from the scheme details page.
    It iterates through each question, clicks it to reveal the answer,
    and stores the Q&A pair.
    """
    try:
        faqs_data = {}
        page = detail_sections.page

        faqs_section = page.locator("#faqs")
        faq_items = faqs_section.locator('div[class^="py-4"]')

        for item in await faq_items.all():
            try:
                question_locator = item.locator('p[class*="font-bold"]')
                question_text = await question_locator.text_content()

                if not question_text:
                    continue

                await question_locator.click()

                answer_locator = item.locator('div[class*="rounded-b"] p')
                await answer_locator.wait_for(state="visible", timeout=5000)
                answer_text = await answer_locator.text_content()

                faqs_data[question_text.strip()] = (answer_text or "").strip()

            except Exception as e:
                logger.warning(f"Could not scrape a FAQ item. Error: {e}")
                pass

        return faqs_data
    except Exception as e:
        logger.error(f"Error in scrape_scheme_faqs: {e}")
        raise


async def scrape_scheme_sources_and_references(
    detail_sections: Locator,
) -> List[Dict[str, str]]:
    """
    Scrapes all sources and references from the scheme details page,
    returning them as a list of dictionaries.
    """
    try:
        sources_list = []
        page = detail_sections.page

        sources_section = page.locator("#sources")
        link_items = sources_section.locator("a")

        for link in await link_items.all():
            try:
                link_text = await link.locator("p").text_content()
                link_url = await link.get_attribute("href")

                if link_text and link_url:
                    sources_list.append(
                        {"text": link_text.strip(), "url": link_url.strip()}
                    )

            except Exception as e:
                logger.warning(f"Could not scrape a source link. Error: {e}")
                pass

        return sources_list
    except Exception as e:
        logger.error(f"Error in scrape_scheme_sources_and_references: {e}")
        raise
