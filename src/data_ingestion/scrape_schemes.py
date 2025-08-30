import asyncio
from loguru import logger
from playwright.async_api import async_playwright

MYSCHEME_BASE_URL = "https://www.myscheme.gov.in"
MYSCHEME_SEARCH_URL = MYSCHEME_BASE_URL + "/search"

async def scrape_scheme():
    async with async_playwright() as play:
        browser = await play.chromium.launch()
        logger.info("Browser launched")

        search_page = await browser.new_page()
        await search_page.goto(MYSCHEME_SEARCH_URL)
        
        scheme_div = search_page.locator("//html/body/div[1]/div/main/div[4]/div[2]/div[5]/div[1]/div[1]")
        scheme_title = await scheme_div.get_by_role("heading").text_content()
        logger.info(f"First scheme title: {scheme_title}")

        scheme_url_path = await scheme_div.get_by_role("link").get_attribute("href")
        scheme_url = MYSCHEME_BASE_URL + scheme_url_path
        logger.info(f"First scheme URL: {scheme_url}")

        scheme_page = await browser.new_page()
        await scheme_page.goto(scheme_url)
        scheme_details_base_xpath = "//html/body/div[1]/div/main/div[2]/div[1]/div/div/div[2]/div/"

        # get all tags/keywords
        scheme_tags = await scheme_page.locator(scheme_details_base_xpath + "div[1]/div[7]/div[1]/div/div[2]/div[1]").get_by_role("button").all()
        scheme_tags = [await tag.text_content() for tag in scheme_tags]
        logger.info(f"Scheme details tags: {scheme_tags}")

        # Get scheme details content - look for the details section
        details_div = scheme_page.locator(scheme_details_base_xpath + "div[2]/div")
        details_string = await details_div.text_content()
        logger.success(f"\nDetails: {details_string}")

        benefits_div = scheme_page.locator(scheme_details_base_xpath + "div[3]/div")
        benefits_string = await benefits_div.text_content()
        logger.success(f"\nBenefits: {benefits_string}")

        eligibility_div = scheme_page.locator(scheme_details_base_xpath + "div[4]/div")
        eligibility_string = await eligibility_div.text_content()
        logger.success(f"\nEligibility: {eligibility_string}")

        application_process_div = scheme_page.locator(scheme_details_base_xpath + "div[5]/div")
        application_process_string = await application_process_div.text_content()
        logger.success(f"\nApplication Process: {application_process_string}")

        documents_required_div = scheme_page.locator(scheme_details_base_xpath + "div[6]/div")
        documents_required_string = await documents_required_div.text_content()
        logger.success(f"\nDocuments Required: {documents_required_string}")

if __name__ == "__main__":
    asyncio.run(scrape_scheme())