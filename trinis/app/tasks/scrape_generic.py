"""
Generic AI-powered scraper using GPT-4o.
Used when scraper_type == "auto" and no dedicated adapter is found.
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from app.core.config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)


def _clean_html(html: str) -> str:
    """Strip scripts, styles, and excess whitespace from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text[:12000]  # GPT-4o context limit safety


def _fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text


def extract_product_links(page_url: str, ctx=None) -> list[dict]:
    """
    Given a listing/category page URL, use GPT-4o to extract product links.
    Returns list of {"title": str, "url": str}
    """
    if ctx:
        ctx.log("info", f"[generic] Fetching listing page: {page_url}")

    html = _fetch_html(page_url)
    soup = BeautifulSoup(html, "html.parser")

    # Extract all links with text
    links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if text and len(text) > 3:
            # Make absolute URL
            if href.startswith("http"):
                links.append({"text": text[:100], "href": href})
            elif href.startswith("/"):
                from urllib.parse import urlparse
                base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
                links.append({"text": text[:100], "href": base + href})

    links_text = "\n".join([f"{l['text']} → {l['href']}" for l in links[:200]])

    prompt = f"""You are analyzing a supplier/vendor website listing page.
Below is a list of links found on the page. Identify which ones are product detail page links.
Return ONLY a JSON array of objects with "title" and "url" fields.
Return at most 50 products. Return only JSON, no explanation.

Links:
{links_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        products = json.loads(raw)
        if ctx:
            ctx.log("info", f"[generic] Found {len(products)} product links")
        return products
    except Exception as e:
        if ctx:
            ctx.log("warning", f"[generic] Failed to parse product links: {e}")
        return []


def extract_product_detail(product_url: str, ctx=None) -> dict | None:
    """
    Given a product detail page URL, use GPT-4o to extract product data.
    Returns dict with title, price, ean, description, image_url or None.
    """
    try:
        html = _fetch_html(product_url)
        cleaned = _clean_html(html)

        prompt = f"""You are extracting product data from a supplier website.
Extract the following fields from the page content below.
Return ONLY a JSON object with these exact keys:
- title (string)
- price (number, without currency symbol, use 0 if not found)
- ean (string barcode/EAN/GTIN, empty string if not found)
- description (string, HTML allowed, max 500 chars)
- image_url (string, full URL of main product image, empty if not found)

Page content:
{cleaned}
"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(raw)
        data["source_url"] = product_url
        return data

    except Exception as e:
        if ctx:
            ctx.log("warning", f"[generic] Failed to extract {product_url}: {e}")
        return None


def scrape_generic(config, ctx, limit: int = 50) -> list[dict]:
    """
    Main entry point for generic scraping.
    Returns list of product dicts ready for the enrich pipeline.
    """
    ctx.log("info", f"[generic] Starting AI-powered scrape of {config.base_url}")

    product_links = extract_product_links(config.base_url, ctx)

    if not product_links:
        ctx.log("warning", "[generic] No product links found on listing page")
        return []

    if limit:
        product_links = product_links[:limit]

    ctx.log("info", f"[generic] Extracting details for {len(product_links)} products")

    results = []
    for i, item in enumerate(product_links):
        ctx.log("info", f"[generic] {i+1}/{len(product_links)} — {item.get('title', item.get('url', ''))}")
        detail = extract_product_detail(item.get("url", ""), ctx)
        if detail:
            # Normalize to match pipeline expectations
            results.append({
                "nome": detail.get("title") or item.get("title", ""),
                "preco": detail.get("price", 0),
                "ean": detail.get("ean", ""),
                "descricao": detail.get("description", ""),
                "imagem_url": detail.get("image_url", ""),
                "link": item.get("url", ""),
            })

    ctx.log("info", f"[generic] Done — {len(results)} products extracted")
    return results
