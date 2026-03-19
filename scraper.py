import time
import trafilatura
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By


def get_local_driver():
    chrome_options = Options()
    # options.add_argument("--headless") # Uncomment if you don't want to see the browser pop up
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def scrape_with_selenium(url):
    driver = get_local_driver()
    try:
        print(f"🌐 Opening browser for: {url}")
        driver.get(url)
        time.sleep(6)  # Give the bank's JavaScript time to load interest rates

        # We grab the HTML and pass it to trafilatura for clean text extraction
        html_content = driver.page_source
        text = trafilatura.extract(html_content, include_tables=True)
        return text if text else ""
    except Exception as e:
        print(f"❌ Selenium Error: {e}")
        return ""
    finally:
        driver.quit()


# Deep-link mapping with Armenian focus
bank_targets = {
    "Mellat Bank": [
        "https://mellatbank.am/hy/pages/consumer-loans",
        "https://mellatbank.am/hy/pages/term-deposits",
        "https://mellatbank.am/hy/pages/contacts"
    ],
    "Ameriabank": [
        "https://ameriabank.am/hy/individual/loans",
        "https://ameriabank.am/hy/individual/deposits",
        "https://ameriabank.am/hy/contact-us/branches-and-atms"
    ],
    "Evocabank": [
        "https://www.evoca.am/hy/loans",
        "https://www.evoca.am/hy/deposits",
        "https://www.evoca.am/hy/branches-and-atms"
    ]
}

full_context = ""

for bank_name, urls in bank_targets.items():
    print(f"\n🏦 Processing {bank_name}...")
    bank_combined_text = f"\n=== {bank_name.upper()} DATA ===\n"

    for url in urls:
        # We use Selenium for all because local environments handle it easily
        content = scrape_with_selenium(url)
        if content:
            bank_combined_text += f"\n--- Source: {url} ---\n{content}\n"
            print(f"  ✅ Successfully Scraped Section")
        else:
            print(f"  ⚠️ Warning: No content found for {url}")
        time.sleep(2)

    full_context += bank_combined_text

# Save the final file locally
with open("bank_data.txt", "w", encoding="utf-8") as f:
    f.write(full_context)

print("\n✨ SUCCESS! Your local 'bank_data.txt' is ready.")