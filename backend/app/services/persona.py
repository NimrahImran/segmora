"""Persona writer. Only segment averages reach the LLM, never a customer row."""
from __future__ import annotations

import json
import logging
import time

import httpx

from ..config import get_settings

log = logging.getLogger("segmora.persona")

PLACEHOLDER = "[your offer]"
BUILT_IN = {
    "vip": {"story": "Treats shopping as a pleasure, not a chore. Knows what good quality looks like and is happy to pay for it.",
            "day": "Finishes a busy week, browses the new arrivals with a coffee, and orders what stands out.",
            "likes": ["Early access to new items", "Personal service", "Reliable delivery"],
            "frustrations": ["Being treated like everyone else", "Items out of stock"],
            "offer": {"subject": "A special thank-you for you",
                      "email": "You are one of our most valued customers, so we wanted you to hear this first: [your offer].",
                      "whatsapp": "Hello! You are one of our most valued customers, so this is for you first: [your offer]."}},
    "regular": {"story": "A steady, dependable buyer who has found a store that works and sees little reason to look elsewhere.",
                "day": "Notices stock running low, reorders the usual items, and adds one or two new things.",
                "likes": ["Easy reordering", "Thank-you rewards", "Consistent quality"],
                "frustrations": ["Price changes without notice", "Favourite items disappearing"],
                "offer": {"subject": "A thank-you for coming back",
                          "email": "You keep choosing us, and we noticed. To say thank you: [your offer].",
                          "whatsapp": "Thank you for staying with us! To say thanks: [your offer]."}},
    "deal": {"story": "Careful with money and in no hurry. Compares prices, waits for the right moment, and buys small.",
             "day": "Sees an offer, checks whether it is really a good price, and decides later.",
             "likes": ["Clear discounts", "Free delivery", "Bundles that save money"],
             "frustrations": ["Hidden charges", "Offers that end too soon"],
             "offer": {"subject": "It has been a while",
                       "email": "It has been a while since your last visit, and we would love to see you again: [your offer].",
                       "whatsapp": "We miss you! Something for your next visit: [your offer]."}},
    "new": {"story": "Has just made a first purchase and is still deciding whether to come back. The next few weeks matter most.",
            "day": "Unpacks the first order, judges the quality, and quietly decides on a second visit.",
            "likes": ["A warm welcome", "Simple suggestions", "A reason to order again"],
            "frustrations": ["Too many marketing messages", "Confusing returns"],
            "offer": {"subject": "Thank you for your first order",
                      "email": "Thank you for your first order. We hope you love it. For your next one: [your offer].",
                      "whatsapp": "Thanks for your first order! For your next one: [your offer]."}},
}
SCHEMA_HINT = ('{"story": "2 sentences", "day": "1 sentence: a typical moment with the brand", '
               '"likes": ["3 short items"], "frustrations": ["2 short items"], '
               '"offer": {"subject": "...", "email": "2 sentences with [your offer]", '
               '"whatsapp": "1-2 sentences with [your offer]"}}')


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
            and all(isinstance(offer.get(k), str) for k in ("subject", "email", "whatsapp"))
            and all(PLACEHOLDER in offer[k] for k in ("email", "whatsapp")))


def _ask_gemini(segment: dict, facts: list[dict]) -> dict | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    prompt = (
        f"You write customer personas for a retail marketing team. Segment: {segment['name']}. "
        f"Measured facts: {json.dumps(facts)}. Write in plain, warm English that a non-technical shop owner "
        "understands. Do not invent numbers, ages, names or genders. You know nothing about this shop's current stock, "
        "collections, sales, discounts, gifts or delivery, so never claim any of them exists. In both the email and the "
        "whatsapp text, write the exact placeholder [your offer] where the shop owner will add a real offer. "
        "Return only JSON in this shape: " + SCHEMA_HINT
    )
    deadline = time.monotonic() + 24  # the function limit is 30 seconds; leave room for the built-in profile
    for model in [m.strip() for m in settings.gemini_model.split(",") if m.strip()]:
        left = deadline - time.monotonic()
        if left < 3:
            break
        try:
            res = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": settings.gemini_api_key},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}},
                timeout=min(left, 12),
            )
            res.raise_for_status()
            data = json.loads(res.json()["candidates"][0]["content"]["parts"][0]["text"])
            if _valid(data):
                return data
            log.warning("persona from %s had the wrong shape", model)
        except httpx.HTTPStatusError as exc:  # retired, busy or over quota: try the next model
            log.warning("persona model %s failed: HTTP %s", model, exc.response.status_code)
        except Exception as exc:  # the page must still work if every model is unavailable
            log.warning("persona model %s failed: %s", model, type(exc).__name__)
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
