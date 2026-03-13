"""Search agent: finds the best product image using DuckDuckGo Images."""

import time
from duckduckgo_search import DDGS


# Keywords added to the query to bias toward clean product photos
_QUERY_SUFFIX = "produto foto fundo branco"

# Domains known to have clean product photos (preference order)
_PREFERRED_DOMAINS = [
    "mercadolivre.com.br",
    "americanas.com.br",
    "shopee.com.br",
    "amazon.com.br",
    "magazineluiza.com.br",
    "submarino.com.br",
    "aliexpress.com",
]


def build_query(description: str, reference: str = "") -> str:
    base = description
    # Use only first ~60 chars of description to keep query focused
    words = base.split()
    short = " ".join(words[:10])
    if reference and reference.upper() != "S/N":
        short = f"{reference} {short}"
    return f"{short} {_QUERY_SUFFIX}"


def search_product_image(description: str, reference: str = "", max_results: int = 10):
    """Return the best image URL found for the product, or None."""
    query = build_query(description, reference)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(
                query,
                max_results=max_results,
                safesearch="moderate",
            ))
    except Exception as exc:
        print(f"  [search] Error for '{query[:40]}...': {exc}")
        return None

    if not results:
        return None

    # Prefer results from known e-commerce domains
    for domain in _PREFERRED_DOMAINS:
        for r in results:
            if domain in r.get("url", ""):
                return r["image"]

    # Fallback: first result with a usable image extension
    for r in results:
        img = r.get("image", "")
        if any(img.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
            return img

    # Last resort: whatever the first result has
    return results[0].get("image") if results else None
