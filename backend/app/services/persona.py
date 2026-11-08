"""Persona writer. Only segment averages reach the LLM, never a customer row."""
from __future__ import annotations

import json
import logging

import httpx

from ..config import get_settings

log = logging.getLogger("segmora.persona")

BUILT_IN = {
    "vip": {"story": "Treats shopping as a pleasure, not a chore. Knows what good quality looks like and is happy to pay for it.",
            "day": "Finishes a busy week, browses the new arrivals with a coffee, and orders what stands out.",
            "likes": ["Early access to new items", "Personal service", "Reliable delivery"],
            "frustrations": ["Being treated like everyone else", "Items out of stock"],
            "offer": {"subject": "Something new, for you first",
                      "email": "You are one of our most valued customers, so you get first look at our new collection before anyone else.",
                      "whatsapp": "Hello! Our new collection is here and you get first access before anyone else. Want a preview?"}},
    "regular": {"story": "A steady, dependable buyer who has found a store that works and sees little reason to look elsewhere.",
                "day": "Notices stock running low, reorders the usual items, and adds one or two new things.",
                "likes": ["Easy reordering", "Thank-you rewards", "Consistent quality"],
                "frustrations": ["Price changes without notice", "Favourite items disappearing"],
                "offer": {"subject": "A thank-you for coming back",
                          "email": "You keep choosing us, and we noticed. Here is a small reward on your next order.",
                          "whatsapp": "Thank you for staying with us! Here is a small reward on your next order."}},
    "deal": {"story": "Careful with money and in no hurry. Compares prices, waits for the right moment, and buys small.",
             "day": "Sees an offer, checks whether it is really a good price, and decides later.",
             "likes": ["Clear discounts", "Free delivery", "Bundles that save money"],
             "frustrations": ["Hidden charges", "Offers that end too soon"],
             "offer": {"subject": "We saved this offer for you",
                       "email": "It has been a while. Here is a limited offer on the items customers like you choose most.",
                       "whatsapp": "We miss you! Here is a limited offer picked for you. It ends this week."}},
    "new": {"story": "Has just made a first purchase and is still deciding whether to come back. The next few weeks matter most.",
            "day": "Unpacks the first order, judges the quality, and quietly decides on a second visit.",
            "likes": ["A warm welcome", "Simple suggestions", "A reason to order again"],
            "frustrations": ["Too many marketing messages", "Confusing returns"],
            "offer": {"subject": "Welcome. Here is what to try next",
                      "email": "Thank you for your first order. Here are a few items that go well with it, and a small welcome gift.",
                      "whatsapp": "Thanks for your first order! Here is a small welcome gift for your next one."}},
}
SCHEMA_HINT = ('{"story": "2 sentences", "day": "1 sentence: a typical moment with the brand", '
               '"likes": ["3 short items"], "frustrations": ["2 short items"], '
               '"offer": {"subject": "...", "email": "2 sentences", "whatsapp": "1-2 sentences"}}')


def observed(segment: dict, currency: str) -> list[dict]:
    m = segment["medians"]
    return [
        {"label": "Share of customers", "value": f"{segment['customer_share'] * 100:.0f}%"},
        {"label": "Share of revenue", "value": f"{segment['revenue_share'] * 100:.0f}%"},
        {"label": "Typical orders", "value": f"{m.get('orders', 0):.0f}"},
        {"label": "Typical order value", "value": f"{currency}{m.get('avg_order_value', 0):,.0f}"},
        {"label": "Last purchase", "value": f"{m.get('recency_days', 0):.0f} days ago"},
    ]


def _valid(data: dict) -> bool:
    offer = data.get("offer") or {}
    return (isinstance(data.get("story"), str) and isinstance(data.get("day"), str)
            and isinstance(data.get("likes"), list) and isinstance(data.get("frustrations"), list)
            and all(isinstance(offer.get(k), str) for k in ("subject", "email", "whatsapp")))


def _ask_gemini(segment: dict, facts: list[dict]) -> dict | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    prompt = (
        f"You write customer personas for a retail marketing team. Segment: {segment['name']}. "
        f"Measured facts: {json.dumps(facts)}. Write in plain, warm English that a non-technical shop owner "
        "understands. Do not invent numbers, ages, names or genders. Return only JSON in this shape: " + SCHEMA_HINT
    )
    try:
        res = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7,
                                       "maxOutputTokens": 900, "thinkingConfig": {"thinkingBudget": 0}}},
            timeout=20,  # stays under the 30 second function limit, so the built-in profile can still be returned
        )
        res.raise_for_status()
        data = json.loads(res.json()["candidates"][0]["content"]["parts"][0]["text"])
        return data if _valid(data) else None
    except httpx.HTTPStatusError as exc:
        log.warning("persona generation failed: HTTP %s", exc.response.status_code)
        return None
    except Exception as exc:  # the page must still work when the free quota runs out
        log.warning("persona generation failed: %s", type(exc).__name__)
        return None


_cache: dict[str, dict] = {}  # per warm instance, saves free-tier quota


def make(segment: dict, currency: str) -> dict:
    facts = observed(segment, currency)
    cache_key = json.dumps([segment["key"], facts])
    generated = _cache.get(cache_key) or _ask_gemini(segment, facts)
    if generated:
        _cache[cache_key] = generated
    return {"key": segment["key"], "name": segment["name"], "tagline": segment["tagline"], "observed": facts,
            **(generated or BUILT_IN[segment["key"]]), "source": "gemini" if generated else "built_in"}
