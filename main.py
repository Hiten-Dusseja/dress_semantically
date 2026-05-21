import json
import time
import random
from playwright.sync_api import sync_playwright

SITES = [
    {
        "name": "Bewakoof Men T-Shirts",
        "url": "https://www.bewakoof.com/t-shirts?gender=men&gad_source=1&gad_campaignid=20197529252&gbraid=0AAAAADfG42XKKjEPOk5ajb6Cq2OKgrsYQ&gclid=CjwKCAjwt7XQBhBkEiwAtStpp33ZHPR4d92B7hvPtSyghB0O_2uc8xZc4nuAlsbIP0CZ9t223KViKhoCZMQQAvD_BwE",
        # FIX: actual class used by Vue-rendered product cards
        "product_selector": ".productCard",
        # FIX: product name is in an <h5> tag, not .product-name
        "name_selector": "h5",
        # FIX: price is in .offer, not .price
        "price_selector": ".offer",
        "link_selector": "a",
        "image_selector": "img",
        "brand": "The Souled Store",
        "category": "tshirt"
    }
]


def random_sleep(a=2, b=4):
    time.sleep(random.uniform(a, b))


def close_popups(page):
    popup_selectors = [
        'button[aria-label="Close"]',
        '.close',
        '.popup-close',
        '.modal-close',
        '.modal__close',
        '.btn-close',
        '.close-button'
    ]
    for selector in popup_selectors:
        try:
            popup = page.query_selector(selector)
            if popup:
                popup.click()
                print(f"Closed popup using: {selector}")
                random_sleep(1, 2)
        except:
            pass


def scroll_page(page, scrolls=8):
    for i in range(scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        print(f"Scrolling {i+1}/{scrolls}")
        random_sleep(2, 4)


def scrape_site(page, config):
    scraped = []
    print(f"\nOpening: {config['name']}")

    try:
        page.goto(config["url"], timeout=60000, wait_until="networkidle")
    except Exception as e:
        print("Failed opening site:", e)
        return scraped

    random_sleep(4, 6)
    close_popups(page)
    scroll_page(page)

    # FIX: Wait for Vue to finish rendering product cards
    try:
        page.wait_for_selector(config["product_selector"], timeout=15000)
    except Exception as e:
        print("Timed out waiting for products:", e)

    random_sleep(3, 5)

    products = page.query_selector_all(config["product_selector"])
    print(f"Found {len(products)} products")

    for product in products[:50]:
        try:
            name_el  = product.query_selector(config["name_selector"])
            price_el = product.query_selector(config["price_selector"])
            link_el  = product.query_selector(config["link_selector"])
            image_el = product.query_selector(config["image_selector"])

            name  = name_el.inner_text().strip()  if name_el  else None
            price = price_el.inner_text().strip() if price_el else None
            href  = link_el.get_attribute("href") if link_el  else None

            # FIX: images are lazy-loaded via data-url, not src
            image = None
            if image_el:
                image = (
                    image_el.get_attribute("data-url")
                    or image_el.get_attribute("src")
                )

            if href and href.startswith("/"):
                base = "/".join(config["url"].split("/")[:3])
                href = base + href

            item = {
                "name": name,
                "price": price,
                "product_url": href,
                "image_url": image,
                "brand": config["brand"],
                "category": config["category"]
            }

            if name:
                scraped.append(item)
                print(f"  ✓ {name} — {price}")

        except Exception as e:
            print("Product parsing error:", e)

    return scraped


def main():
    all_products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()

        for site in SITES:
            try:
                products = scrape_site(page, site)
                all_products.extend(products)
            except Exception as e:
                print("SITE FAILED:", e)

        browser.close()

    print(f"\nTOTAL PRODUCTS: {len(all_products)}")

    with open("fashion_data_2.json", "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=4, ensure_ascii=False)

    print("\nSaved to fashion_data.json")


if __name__ == "__main__":
    main()