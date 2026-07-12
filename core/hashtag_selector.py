from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Iterable

logger = logging.getLogger(__name__)

HASHTAG_CONFIG = {
    "x": {"min_hashtags": 0, "max_hashtags": 1},
    "twitter": {"min_hashtags": 0, "max_hashtags": 1},
    "instagram": {"min_hashtags": 3, "max_hashtags": 5},
    "linkedin": {"min_hashtags": 0, "max_hashtags": 3},
    "facebook": {"min_hashtags": 0, "max_hashtags": 1},
}

BANNED_HASHTAGS = {"#trading", "#smc", "#ict", "#nq", "#es"}
INSTAGRAM_FALLBACK_HASHTAGS = ["#ICTTrading", "#FuturesTrading", "#PriceAction"]
LINKEDIN_FALLBACK_HASHTAGS: list[str] = []

HASHTAG_RE = re.compile(r"(?<!\w)#\w+")
WHITESPACE_RE = re.compile(r"[ \t]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")

HASHTAG_TAXONOMY = {
    "fomc": {
        "hashtag": "#FOMC",
        "priority": 100,
        "keywords": ["fomc", "federal open market committee", "fed meeting"],
    },
    "cpi": {
        "hashtag": "#CPI",
        "priority": 100,
        "keywords": ["cpi", "consumer price index", "inflation print"],
    },
    "nfp": {
        "hashtag": "#NFP",
        "priority": 100,
        "keywords": ["nfp", "nonfarm payroll", "non-farm payroll", "jobs report"],
    },
    "nq_futures": {
        "hashtag": "#NQFutures",
        "priority": 82,
        "quote_only": True,
        "keywords": ["nq futures", "nasdaq futures", "nasdaq 100 futures", "nq"],
    },
    "es_futures": {
        "hashtag": "#ESFutures",
        "priority": 82,
        "quote_only": True,
        "keywords": ["es futures", "s&p futures", "s&p 500 futures", "sp500 futures", "e-mini s&p", "es"],
    },
    "fair_value_gap": {
        "hashtag": "#FairValueGap",
        "priority": 76,
        "keywords": ["fair value gap", "fair value gaps", "fvg", "imbalance", "imbalances", "displacement"],
    },
    "liquidity": {
        "hashtag": "#Liquidity",
        "priority": 74,
        "keywords": [
            "liquidity sweep",
            "liquidity sweeps",
            "buy-side liquidity",
            "buyside liquidity",
            "sell-side liquidity",
            "sellside liquidity",
            "stop run",
            "stop runs",
            "swept",
            "sweep",
            "took stops",
        ],
    },
    "risk_management": {
        "hashtag": "#RiskManagement",
        "priority": 68,
        "keywords": [
            "risk",
            "stop loss",
            "stop-loss",
            "position sizing",
            "sizing",
            "drawdown",
            "capital preservation",
            "protecting capital",
            "protect capital",
            "preserve capital",
            "capital",
        ],
    },
    "trading_psychology": {
        "hashtag": "#TradingPsychology",
        "priority": 66,
        "keywords": [
            "trading psychology",
            "psychology",
            "psyche",
            "emotion",
            "emotional",
            "discipline",
            "fear",
            "greed",
            "agitation",
            "agitated",
            "patience",
            "patient",
            "mindset",
            "impulsive",
            "revenge",
            "overconfident",
            "tilt",
            "calm",
            "pressure",
        ],
    },
    "trading_journal": {
        "hashtag": "#TradingJournal",
        "priority": 62,
        "keywords": [
            "trading journal",
            "trade journal",
            "journal",
            "journaling",
            "reviewing trades",
            "review trades",
            "trade review",
            "collecting data",
            "tracking performance",
            "performance tracking",
            "logged",
            "logbook",
        ],
    },
    "ict_trading": {
        "hashtag": "#ICTTrading",
        "priority": 58,
        "keywords": [
            "ict trading",
            "ict methodology",
            "ict mentorship",
            "mentorship",
            "institutional order flow",
            "order flow",
            "order block",
            "orderblock",
        ],
    },
    "price_action": {
        "hashtag": "#PriceAction",
        "priority": 46,
        "keywords": [
            "price action",
            "price trades",
            "market structure",
            "break of structure",
            "repricing",
            "expanding",
            "expansion",
            "delivery",
            "candle",
        ],
    },
}

CATEGORY_TAKEAWAYS = {
    "trading_psychology": "Trading psychology shows up before execution.",
    "risk_management": "Risk management is the edge before the entry.",
    "trading_journal": "A trade journal turns repetition into data.",
    "ict_trading": "Context matters more than labels.",
    "fair_value_gap": "A fair value gap only matters when context supports it.",
    "liquidity": "A liquidity sweep needs context before it becomes a setup.",
    "price_action": "Read the price action, then wait for proof.",
    "nq_futures": "NQ futures demand clean context and execution.",
    "es_futures": "ES futures reward clean context and patience.",
    "fomc": "FOMC risk belongs in the plan before the move.",
    "cpi": "CPI risk belongs in the plan before the reaction.",
    "nfp": "NFP risk belongs in the plan before the reaction.",
}

PLATFORM_RELATED_HASHTAGS = {
    "instagram": {
        "trading_psychology": ["#TradingPsychology", "#TraderMindset", "#TradingDiscipline"],
        "risk_management": ["#RiskManagement", "#CapitalPreservation", "#TradingPlan"],
        "trading_journal": ["#TradingJournal", "#TradeReview", "#TradingData", "#PerformanceTracking"],
        "ict_trading": ["#ICTTrading", "#InstitutionalOrderFlow", "#PriceAction"],
        "fair_value_gap": ["#FairValueGap", "#ICTTrading", "#PriceAction"],
        "liquidity": ["#Liquidity", "#LiquiditySweep", "#PriceAction", "#ICTTrading"],
        "price_action": ["#PriceAction", "#MarketStructure", "#FuturesTrading"],
        "nq_futures": ["#NQFutures", "#FuturesTrading", "#PriceAction"],
        "es_futures": ["#ESFutures", "#FuturesTrading", "#PriceAction"],
        "fomc": ["#FOMC", "#MacroTrading", "#FuturesTrading", "#RiskManagement"],
        "cpi": ["#CPI", "#MacroTrading", "#FuturesTrading", "#RiskManagement"],
        "nfp": ["#NFP", "#MacroTrading", "#FuturesTrading", "#RiskManagement"],
    },
    "linkedin": {
        "trading_psychology": ["#TradingPsychology", "#TradingEducation"],
        "risk_management": ["#RiskManagement", "#TradingEducation"],
        "trading_journal": ["#TradingJournal", "#TradingEducation"],
        "ict_trading": ["#ICTTrading", "#TradingEducation"],
        "fair_value_gap": ["#FairValueGap", "#PriceAction", "#TradingEducation"],
        "liquidity": ["#Liquidity", "#PriceAction", "#TradingEducation"],
        "price_action": ["#PriceAction", "#TradingEducation"],
        "nq_futures": ["#NQFutures", "#TradingEducation"],
        "es_futures": ["#ESFutures", "#TradingEducation"],
        "fomc": ["#FOMC", "#RiskManagement", "#TradingEducation"],
        "cpi": ["#CPI", "#RiskManagement", "#TradingEducation"],
        "nfp": ["#NFP", "#RiskManagement", "#TradingEducation"],
    },
}


@dataclass(frozen=True)
class HashtagDecision:
    platform: str
    selected_category: str | None
    hashtags: list[str]
    matching_keywords: list[str]
    confidence: float
    reason: str

    def to_log_payload(self) -> dict:
        return asdict(self)


def canonical_platform(platform: str | None) -> str:
    cleaned = (platform or "x").strip().lower()
    if cleaned in {"twitter", "tweet"}:
        return "x"
    return cleaned


def normalize_for_matching(value: str | None) -> str:
    text = (value or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def clean_caption_body(value: str | None) -> str:
    text = (value or "").strip()
    text = HASHTAG_RE.sub("", text)
    text = "\n".join(WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return BLANK_LINES_RE.sub("\n\n", text).strip()


def unique_hashtags(hashtags: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for hashtag in hashtags:
        tag = hashtag.strip()
        if not tag:
            continue
        key = tag.lower()
        if key in seen or key in BANNED_HASHTAGS:
            continue
        seen.add(key)
        result.append(tag)
    return result


def _keyword_matches(text: str, keywords: list[str]) -> list[str]:
    matches: list[str] = []
    padded_text = f" {text} "
    for keyword in keywords:
        normalized_keyword = normalize_for_matching(keyword)
        if not normalized_keyword:
            continue

        if f" {normalized_keyword} " in padded_text and keyword not in matches:
            matches.append(keyword)
    return matches


def _score_matches(matches: list[str]) -> float:
    score = 0.0
    for keyword in matches:
        score += 1.5 if " " in keyword or "-" in keyword else 1.0
    return score


def _classify(text: str, supporting_text: str = "") -> tuple[str | None, list[str], float, str]:
    quote_text = normalize_for_matching(text)
    combined_text = normalize_for_matching(f"{text} {supporting_text}")
    candidates = []

    for category, config in HASHTAG_TAXONOMY.items():
        haystack = quote_text if config.get("quote_only") else combined_text
        matches = _keyword_matches(haystack, config["keywords"])
        if not matches:
            continue

        score = _score_matches(matches)
        confidence = min(0.98, 0.42 + (score * 0.13))
        candidates.append(
            {
                "category": category,
                "matches": matches,
                "score": score,
                "confidence": confidence,
                "priority": config["priority"],
            }
        )

    if not candidates:
        return None, [], 0.0, "No contextual keyword match found."

    candidates.sort(key=lambda item: (item["priority"], item["score"], item["confidence"]), reverse=True)
    winner = candidates[0]

    if winner["confidence"] < 0.52:
        return None, winner["matches"], winner["confidence"], "Classification confidence below threshold."

    reason = f"Matched {winner['category']} via {', '.join(winner['matches'])}."
    return winner["category"], winner["matches"], winner["confidence"], reason


def select_hashtags(platform: str, text: str, supporting_text: str = "") -> HashtagDecision:
    canonical = canonical_platform(platform)
    limits = HASHTAG_CONFIG.get(canonical, HASHTAG_CONFIG["x"])
    max_hashtags = limits["max_hashtags"]
    min_hashtags = limits["min_hashtags"]
    category, matches, confidence, reason = _classify(text, supporting_text=supporting_text)

    hashtags: list[str] = []
    if max_hashtags > 0 and category:
        if canonical == "instagram":
            hashtags = PLATFORM_RELATED_HASHTAGS["instagram"].get(category, [HASHTAG_TAXONOMY[category]["hashtag"]])
        elif canonical == "linkedin":
            hashtags = PLATFORM_RELATED_HASHTAGS["linkedin"].get(category, [HASHTAG_TAXONOMY[category]["hashtag"]])
        else:
            hashtags = [HASHTAG_TAXONOMY[category]["hashtag"]]
    elif canonical == "instagram" and min_hashtags > 0:
        hashtags = INSTAGRAM_FALLBACK_HASHTAGS
        reason = "Low-confidence fallback for Instagram niche discovery."
    elif canonical == "linkedin" and min_hashtags > 0:
        hashtags = LINKEDIN_FALLBACK_HASHTAGS
        reason = "Low-confidence LinkedIn fallback."

    if canonical == "instagram" and category and len(hashtags) < min_hashtags:
        hashtags = [*hashtags, *INSTAGRAM_FALLBACK_HASHTAGS]

    hashtags = unique_hashtags(hashtags)[:max_hashtags]

    decision = HashtagDecision(
        platform=canonical,
        selected_category=category,
        hashtags=hashtags,
        matching_keywords=matches,
        confidence=round(confidence, 2),
        reason=reason,
    )
    log_hashtag_decision(decision)
    return decision


def log_hashtag_decision(decision: HashtagDecision) -> None:
    payload = decision.to_log_payload()
    logger.info(
        "social_hashtag_selection platform=%s category=%s hashtags=%s keywords=%s confidence=%.2f reason=%s",
        payload["platform"],
        payload["selected_category"],
        payload["hashtags"],
        payload["matching_keywords"],
        payload["confidence"],
        payload["reason"],
    )


def _join_caption(parts: list[str]) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip()).strip()


def _fit_x_caption(quote_text: str, takeaway: str, hashtags: list[str]) -> str:
    hashtag_text = " ".join(hashtags)
    variants = [
        [f'"{quote_text}"', takeaway, hashtag_text],
        [f'"{quote_text}"', hashtag_text],
        [takeaway, hashtag_text],
    ]

    for parts in variants:
        candidate = _join_caption(parts)
        if len(candidate) <= 280:
            return candidate

    overhead = len(_join_caption(['""', hashtag_text]))
    max_quote_len = max(0, 280 - overhead - 3)
    truncated = quote_text[:max_quote_len].rstrip()
    truncated = f"{truncated}..." if truncated else "..."
    return _join_caption([f'"{truncated}"', hashtag_text])


def format_quote_caption(platform: str, quote_text: str, supporting_text: str = "") -> str:
    canonical = canonical_platform(platform)
    decision = select_hashtags(canonical, quote_text, supporting_text=supporting_text)
    takeaway = CATEGORY_TAKEAWAYS.get(decision.selected_category, "Track your edge.")
    hashtag_text = " ".join(decision.hashtags)

    if canonical == "x":
        return _fit_x_caption(quote_text, takeaway, decision.hashtags)

    return _join_caption([f'"{quote_text}"', takeaway, hashtag_text])


def sanitize_caption_for_platform(
    platform: str,
    caption: str,
    *,
    source_text: str | None = None,
    supporting_text: str = "",
) -> str:
    canonical = canonical_platform(platform)
    body = clean_caption_body(caption)
    classification_text = (source_text or body).strip()
    decision = select_hashtags(canonical, classification_text, supporting_text=supporting_text)
    hashtag_text = " ".join(decision.hashtags)

    if canonical == "x":
        candidate = _join_caption([body, hashtag_text])
        if len(candidate) <= 280:
            return candidate
        if source_text:
            return format_quote_caption(canonical, source_text, supporting_text=supporting_text)
        return _join_caption([body[:277].rstrip() + "...", hashtag_text]).strip()

    return _join_caption([body, hashtag_text])
