import time
import trafilatura
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape(url, wait_seconds=10):
    driver = get_driver()
    try:
        print(f"  🌐 {url}")
        driver.get(url)
        time.sleep(wait_seconds)  # wait for JS to render


        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        html = driver.page_source

        not_found_signals = ["էջը գոյություն չունի", "page not found", "404 not found"]
        if any(s in html.lower() for s in not_found_signals):
            print(f"    ⚠️  Page not found")
            return ""

        if len(html) < 5000:
            print(f"    ⚠️  Page too small ({len(html)} chars) — likely blocked")
            return ""

        text = trafilatura.extract(
            html,
            include_tables=True,
            include_links=False,
            no_fallback=False,
            favor_recall=True,
        )
        result = text.strip() if text else ""
        print(f"    ✅ {len(result):,} chars extracted")
        return result

    except Exception as e:
        print(f"    ❌ Error: {e}")
        return ""
    finally:
        driver.quit()


bank_targets = {
    "Mellat Bank": [
        "https://mellatbank.am/hy/pages/consumer-loans",
        "https://mellatbank.am/hy/loans_individual",
        "https://mellatbank.am/hy/Deposits",
        "https://mellatbank.am/hy/pages/current-deposits",
        "https://mellatbank.am/hy/pages/contacts",
    ],
    "Ameriabank": [
        "https://ameriabank.am/",
        "https://ameriabank.am/loans/consumer-loans",
        "https://ameriabank.am/personal/saving/deposits/ameria-deposit",
        "https://ameriabank.am/en/personal/loans",
        "https://ameriabank.am/en/personal/deposits",
    ],
    "Evocabank": [
        "https://www.evoca.am/hy/"
        "https://www.evoca.am/en/loans",
        "https://www.evoca.am/en/deposits",
        "https://www.evoca.am/en/deposits-important-information",
        "https://www.evoca.am/en/branches-and-atms",
        "https://www.evoca.am/hy/loans",
        "https://www.evoca.am/hy/deposits",
        "https://www.evoca.am/hy/branches-and-atms",
    ],
}

full_context = ""

for bank_name, urls in bank_targets.items():
    print(f"\n🏦 Scraping: {bank_name}")
    bank_text = f"\n=== {bank_name.upper()} DATA ===\n"
    scraped_count = 0

    for url in urls:
        content = scrape(url)
        if content and len(content) > 200:
            bank_text += f"\n--- Source: {url} ---\n{content}\n"
            scraped_count += 1
        time.sleep(3)

    full_context += bank_text
    print(f"  → {scraped_count} pages scraped successfully")

with open("bank_data.txt", "w", encoding="utf-8") as f:
    f.write(full_context)

print("\n" + "="*50)
print("DONE! Summary:")
for bank in ["MELLAT BANK", "AMERIABANK", "EVOCABANK"]:
    idx = full_context.upper().find(bank)
    section = full_context[idx:idx+10000] if idx != -1 else ""
    next_bank = section.find("=== ", 10)
    section = section[:next_bank] if next_bank != -1 else section
    print(f"  {bank}: {len(section):,} chars — {'✅ good' if len(section) > 1000 else '⚠️ thin'}")