"""
Fashion Scraper — The Souled Store + Bewakoof
Targets: 50+ tops and 50+ bottoms from each site
Output:  fashion_data.json
"""

import json
import time
import random
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ─── Output directory ────────────────────────────────────────────────────────
OUTPUT_DIR = "scraper_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Site configs ─────────────────────────────────────────────────────────────
# Each entry has a list of candidate selectors per field.
# The scraper tries each in order and uses the first one that returns results.
SITES = [
    # ── The Souled Store ──────────────────────────────────────────────────────
    {
        "brand": "The Souled Store",
        "pages": [
            {
                "url": "https://www.thesouledstore.com/men/t-shirts",
                "category": "tops",
                "gender": "men",
            },
            {
                "url": "https://www.thesouledstore.com/men/joggers-and-track-pants",
                "category": "bottoms",
                "gender": "men",
            },
            {
                "url": "https://www.thesouledstore.com/men/pants",
                "category": "bottoms",
                "gender": "men",
            },
            {
                "url": "https://www.thesouledstore.com/women/t-shirts",
                "category": "tops",
                "gender": "women",
            },
            {
                "url": "https://www.thesouledstore.com/women/joggers-and-track-pants",
                "category": "bottoms",
                "gender": "women",
            },
            {
                "url": "https://www.thesouledstore.com/women/pants",
                "category": "bottoms",
                "gender": "women",
            },
        ],
        # Tried in order; first selector that matches wins
        "product_selectors": [".productCard", ".product-thumb", "[class*='productCard']"],
        "name_selectors":    ["h5", ".product-name", "[class*='product-name']", "h3"],
        "price_selectors":   [".offer", ".price", "[class*='offer']", "[class*='price']"],
        "link_selectors":    ["a"],
        # Bewakoof lazy-loads via data-url; Souled Store also does this
        "image_selectors":   ["img[data-url]", "img[src]", "img"],
        "image_attr":        ["data-url", "src"],
        "desc_selectors":    [".listprice span", "[class*='listprice'] span", "h5 + div span"],
        "scroll_times":      10,
        "page_load_wait":    "networkidle",
    },

    # ── Bewakoof ──────────────────────────────────────────────────────────────
    {
        "brand": "Bewakoof",
        "pages": [
            {
                "url": "https://www.bewakoof.com/men-t-shirts",
                "category": "tops",
                "gender": "men",
            },
            {
                "url": "https://www.bewakoof.com/men-joggers",
                "category": "bottoms",
                "gender": "men",
            },
            {
                "url": "https://www.bewakoof.com/men-pants",
                "category": "bottoms",
                "gender": "men",
            },
            {
                "url": "https://www.bewakoof.com/men-shirts",
                "category": "tops",
                "gender": "men",
            },
            {
                "url": "https://www.bewakoof.com/women-t-shirts",
                "category": "tops",
                "gender": "women",
            },
            {
                "url": "https://www.bewakoof.com/women-joggers",
                "category": "bottoms",
                "gender": "women",
            },
            {
                "url": "https://www.bewakoof.com/women-pants",
                "category": "bottoms",
                "gender": "women",
            },
            {
                "url": "https://www.bewakoof.com/women-shirts",
                "category": "tops",
                "gender": "women",
            },
        ],
        # Bewakoof is Next.js; these cover both old and new DOM shapes
        "product_selectors": [
            "a[href*='/p/']:has(img)",
            "a[href*='/p/']",
            "[class*='product-list-item']",
            "[class*='ProductCard']",
            "[class*='product_card']",
            "[class*='productCard']",
            "[class*='product-card']",
            "[data-testid='product-card']",
            ".product-list-item",
            "li[class*='product']",
        ],
        "name_selectors": [
            "[class*='product-title']",
            "[class*='ProductTitle']",
            "[class*='productTitle']",
            "[class*='product_title']",
            "[class*='product-name']",
            "p[class*='title']",
            "span[class*='title']",
            "h3", "h4",
            "img[alt]",
            "[title]",
        ],
        "price_selectors": [
            "[class*='discountedPrice']",
            "[class*='discounted-price']",
            "[class*='DiscountedPrice']",
            "[class*='selling-price']",
            "[class*='sellingPrice']",
            "[class*='product-price']",
            "[class*='ProductPrice']",
            "[class*='price']",
            "span[class*='price']",
        ],
        "link_selectors": ["a"],
        "image_selectors": [
            "img[src*='bewakoof']",
            "img[data-src]",
            "img[src]",
            "img",
        ],
        "image_attr": ["src", "data-src"],
        "desc_selectors": [
            "[class*='product-type']",
            "[class*='productType']",
            "p[class*='type']",
            "span[class*='type']",
        ],
        "scroll_times":   12,
        "page_load_wait": "domcontentloaded",   # Bewakoof blocks networkidle
    },
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def jitter(lo=2.0, hi=5.0):
    """Human-like random delay."""
    time.sleep(random.uniform(lo, hi))


def close_popups(page):
    """Dismiss any cookie banners or modal overlays."""
    selectors = [
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "[class*='close-button']",
        "[class*='closeButton']",
        "[class*='modal-close']",
        "[class*='popup-close']",
        ".btn-close",
        "#onesignal-slidedown-cancel-button",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                print(f"  ✓ Closed popup: {sel}")
                jitter(0.5, 1.5)
        except Exception:
            pass


def slow_scroll(page, times=10):
    """
    Scroll incrementally (not just to bottom) to trigger lazy-load events
    more reliably — mimics a real user reading down the page.
    """
    for i in range(times):
        page.evaluate("""
            window.scrollBy({
                top: window.innerHeight * 0.8,
                behavior: 'smooth'
            });
        """)
        print(f"  ↓ Scroll {i+1}/{times}")
        jitter(1.5, 3.0)

    # Final jump to bottom to catch any stragglers
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    jitter(2, 3)


def first_match(element, selectors):
    """Return the first child element that matches any selector in the list."""
    for sel in selectors:
        try:
            el = element.query_selector(sel)
            if el:
                return el
        except Exception:
            pass
    return None


def first_attr(element, attrs):
    """Return the first non-empty attribute value from the list."""
    for attr in attrs:
        try:
            val = element.get_attribute(attr)
            if val and val.strip() and "blank" not in val:
                return val.strip()
        except Exception:
            pass
    return None


def resolve_url(href, base_url):
    """Turn relative paths into absolute URLs."""
    if not href:
        return None
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        parts = base_url.split("/")
        return f"{parts[0]}//{parts[2]}{href}"
    return href


def clean_text(value):
    """Normalize text from product cards."""
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def get_card_text_lines(element):
    """Return useful, de-duplicated text lines from a card."""
    try:
        raw = element.inner_text()
    except Exception:
        return []

    lines = []
    seen = set()
    for line in raw.splitlines():
        text = clean_text(line)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(text)
    return lines


def closest_product_card(element):
    """
    Bewakoof often puts the useful text outside the product link itself.
    Climb to the smallest ancestor that contains an image, a product link,
    and enough visible text to parse title/price.
    """
    try:
        handle = element.evaluate_handle("""
            el => {
                let node = el;
                for (let i = 0; node && i < 8; i++, node = node.parentElement) {
                    const text = (node.innerText || '').trim();
                    if (
                        node.querySelector("a[href*='/p/']") &&
                        node.querySelector('img') &&
                        text.length > 20
                    ) {
                        return node;
                    }
                }
                return el;
            }
        """)
        card = handle.as_element()
        return card or element
    except Exception:
        return element


def parse_bewakoof_from_text(lines):
    """Extract Bewakoof name, price, and description from visible card text."""
    price = None
    price_re = re.compile(r"(?:₹|Rs\.?)\s*[\d,]+")

    for line in lines:
        match = price_re.search(line)
        if match:
            price = match.group(0).replace("Rs.", "₹").replace("Rs", "₹")
            break

    skip_prefixes = (
        "₹", "rs", "buy", "tribe", "inclusive", "off", "out of stock",
        "oversized fit", "slim fit", "regular fit", "classic fit",
    )
    candidates = []
    for line in lines:
        lower = line.lower()
        if price_re.search(line):
            continue
        if lower.startswith(skip_prefixes):
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", line):
            continue
        if lower in {"bewakoof", "bewakoof®", "bewakoof air", "bewakoof heavy duty"}:
            continue
        if len(line) >= 6:
            candidates.append(line)

    description = None
    for line in lines:
        lower = line.lower()
        if lower in {"bewakoof", "bewakoof®", "bewakoof air", "bewakoof heavy duty"}:
            description = line
            break

    name = candidates[0] if candidates else None
    return name, price, description


def pick_selector(page, candidates):
    """Return the first selector from candidates that finds at least 1 element."""
    for sel in candidates:
        try:
            els = page.query_selector_all(sel)
            if els:
                print(f"  ✓ Selector matched: '{sel}' → {len(els)} elements")
                return sel, els
        except Exception:
            pass
    return None, []


# ─── Core scrape function ─────────────────────────────────────────────────────

def scrape_page(page, url, category, gender, site_cfg):
    results = []
    brand = site_cfg["brand"]

    print(f"\n{'─'*60}")
    print(f"  Site  : {brand}")
    print(f"  URL   : {url}")
    print(f"  Cat   : {category}")
    print(f"  Gender: {gender}")
    print(f"{'─'*60}")

    # Load the page
    try:
        page.goto(url, timeout=90_000, wait_until=site_cfg["page_load_wait"])
    except PlaywrightTimeout:
        print("  ⚠ Timeout on initial load — trying domcontentloaded fallback")
        try:
            page.goto(url, timeout=60_000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"  ✗ Failed to load: {e}")
            return results

    jitter(4, 7)
    close_popups(page)
    slow_scroll(page, site_cfg["scroll_times"])
    jitter(2, 4)

    # Screenshot for debugging
    shot_path = os.path.join(OUTPUT_DIR, f"debug_{brand.replace(' ', '_')}_{category}.png")
    try:
        page.screenshot(path=shot_path, full_page=True)
        print(f"  📸 Screenshot → {shot_path}")
    except Exception:
        pass

    # Find which product selector works on this live page
    prod_selector, products = pick_selector(page, site_cfg["product_selectors"])

    if not products:
        print(f"  ✗ No products found. Check {shot_path} to inspect the DOM.")
        # Dump raw HTML snippet for debugging
        html_path = os.path.join(OUTPUT_DIR, f"debug_{brand.replace(' ', '_')}_{category}.html")
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content()[:50_000])   # first 50k chars
            print(f"  📄 HTML dump → {html_path}")
        except Exception:
            pass
        return results

    print(f"  Found {len(products)} product cards — parsing up to 60…")

    seen_urls = set()

    for i, card in enumerate(products[:90]):
        try:
            parse_card = closest_product_card(card) if brand == "Bewakoof" else card

            # ── Name ──────────────────────────────────────────────────────────
            name_el = first_match(parse_card, site_cfg["name_selectors"])
            name = None
            if name_el:
                name = (
                    first_attr(name_el, ["title", "alt"])
                    or clean_text(name_el.inner_text())
                )

            # ── Price ─────────────────────────────────────────────────────────
            price_el = first_match(parse_card, site_cfg["price_selectors"])
            price = clean_text(price_el.inner_text()) if price_el else None

            # ── Description (sub-type label, e.g. "Oversized T-Shirts") ──────
            desc_el = first_match(parse_card, site_cfg["desc_selectors"])
            description = clean_text(desc_el.inner_text()) if desc_el else None

            # ── Link ──────────────────────────────────────────────────────────
            link_el = card if brand == "Bewakoof" and card.evaluate("el => el.tagName") == "A" else first_match(parse_card, site_cfg["link_selectors"])
            href = link_el.get_attribute("href") if link_el else None
            product_url = resolve_url(href, url)

            # ── Image ─────────────────────────────────────────────────────────
            img_el = first_match(parse_card, site_cfg["image_selectors"])
            image_url = first_attr(img_el, site_cfg["image_attr"]) if img_el else None

            if brand == "Bewakoof":
                lines = get_card_text_lines(parse_card)
                parsed_name, parsed_price, parsed_description = parse_bewakoof_from_text(lines)
                name = name or parsed_name
                price = price or parsed_price
                description = description or parsed_description

                if not image_url and img_el:
                    image_url = first_attr(img_el, ["data-src", "src", "srcset"])

            # Skip cards with no name (banners, ads, membership tiles)
            if not name:
                continue

            if product_url and product_url in seen_urls:
                continue
            if product_url:
                seen_urls.add(product_url)

            item = {
                "name":        name,
                "price":       price,
                "description": description,
                "category":    category,
                "gender":      gender,
                "brand":       brand,
                "product_url": product_url,
                "image_url":   image_url,
                "scraped_at":  datetime.utcnow().isoformat() + "Z",
            }

            results.append(item)
            print(f"  [{i+1:02d}] {name[:55]:<55} {price or '???'}")

        except Exception as e:
            print(f"  ⚠ Card {i+1} parse error: {e}")

    print(f"\n  ✅ Collected {len(results)} items from {url}")
    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    all_products = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,   # Set True once you've verified it works
            slow_mo=80,
        )

        context = browser.new_context(
            # Rotate through realistic user-agent strings
            user_agent=random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
                "Gecko/20100101 Firefox/125.0",
            ]),
            viewport={"width": 1440, "height": 900},
            # Pretend to be a real browser — passes most bot-detection checks
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
                "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "DNT":             "1",
            },
            # Mask automation flags (navigator.webdriver = false, etc.)
            java_script_enabled=True,
        )

        # Stealth: override navigator.webdriver before any page loads
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()

        for site in SITES:
            for page_cfg in site["pages"]:
                try:
                    items = scrape_page(
                        page,
                        url=page_cfg["url"],
                        category=page_cfg["category"],
                        gender=page_cfg["gender"],
                        site_cfg=site,
                    )
                    all_products.extend(items)
                except Exception as e:
                    print(f"\n✗ SITE FAILED ({site['brand']} / {page_cfg['category']} / {page_cfg['gender']}): {e}")

                # Polite delay between pages — looks human, avoids rate limits
                wait = random.uniform(8, 15)
                print(f"\n⏳ Waiting {wait:.1f}s before next page…")
                time.sleep(wait)

        browser.close()

    # ─── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  TOTAL SCRAPED: {len(all_products)} items")

    tops    = [p for p in all_products if p["category"] == "tops"]
    bottoms = [p for p in all_products if p["category"] == "bottoms"]
    tss     = [p for p in all_products if p["brand"] == "The Souled Store"]
    bwk     = [p for p in all_products if p["brand"] == "Bewakoof"]

    print(f"  Tops   : {len(tops)}")
    print(f"  Bottoms: {len(bottoms)}")
    print(f"  The Souled Store: {len(tss)}")
    print(f"  Bewakoof        : {len(bwk)}")
    print(f"{'='*60}")

    # ─── Save JSON ────────────────────────────────────────────────────────────
    out_path = os.path.join(OUTPUT_DIR, "fashion_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved → {out_path}")

    # Also save per-brand files for easier inspection
    for brand_name, items in [("souledstore", tss), ("bewakoof", bwk)]:
        path = os.path.join(OUTPUT_DIR, f"{brand_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        print(f"   ↳ {path}  ({len(items)} items)")


if __name__ == "__main__":
    main()
