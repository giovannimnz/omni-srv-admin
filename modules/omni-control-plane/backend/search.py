"""
ATIUS Canonical 9-Tier Intelligent Search Engine for Names, Strings, and Documents.
Enforces bidirectional NFD Unicode accent-folding and numeric document matching (CPF, RG, RENACH, CNPJ).
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

DIACRITIC_RE = re.compile(r"[\u0300-\u036f]")
NON_DIGIT_RE = re.compile(r"\D+")
TOKEN_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)


def normalize_text(value: Optional[str]) -> str:
    """Decompose Unicode NFD, strip combining diacritics, and normalize whitespace/case."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFD", str(value))
    stripped = DIACRITIC_RE.sub("", decomposed)
    return " ".join(stripped.lower().strip().split())


def clean_digits(value: Optional[str]) -> str:
    """Extract only numeric digits from a string."""
    if not value:
        return ""
    return NON_DIGIT_RE.sub("", str(value))


def tokenize(value: Optional[str]) -> List[str]:
    """Split normalized text into alphanumeric tokens."""
    norm = normalize_text(value)
    if not norm:
        return []
    return [tok for tok in TOKEN_SPLIT_RE.split(norm) if tok]


def score_text_match(query: str, candidate: str) -> Tuple[float, int]:
    """
    Evaluate 9-Tier match hierarchy between query and candidate text.
    Returns (score, tier) where tier is 1..9 (or 0 if no match).
    """
    if not query or not candidate:
        return 0.0, 0

    raw_q = query.strip()
    raw_c = candidate.strip()
    if not raw_q or not raw_c:
        return 0.0, 0

    # Tier 1 (Score 1.00): Exact literal match (same case and accents)
    if raw_q == raw_c:
        return 1.00, 1

    # Tier 2 (Score 0.99): Exact case-insensitive match (preserving accents)
    low_q = raw_q.lower()
    low_c = raw_c.lower()
    if low_q == low_c:
        return 0.99, 2

    # Tier 3 (Score 0.98): Exact accent-folded normalized match
    norm_q = normalize_text(raw_q)
    norm_c = normalize_text(raw_c)
    if not norm_q or not norm_c:
        return 0.0, 0
    if norm_q == norm_c:
        return 0.98, 3

    q_tokens = tokenize(raw_q)
    c_tokens = tokenize(raw_c)

    # Tier 4 (Score 0.97): Multi-token match (all query words exist in candidate tokens or prefixes)
    if len(q_tokens) >= 2 and c_tokens:
        if all(any(ct == qt or ct.startswith(qt) for ct in c_tokens) for qt in q_tokens):
            return 0.97, 4

    # Tier 5 (Score 0.96): Continuous literal substring
    if raw_q in raw_c or low_q in low_c:
        # Distinguish exact token vs prefix vs general substring if single token
        if len(q_tokens) == 1 and c_tokens:
            qt = q_tokens[0]
            if qt in c_tokens and raw_q in raw_c.split():
                return 0.96, 5
        return 0.96, 5

    # Tier 6 (Score 0.94): Continuous normalized (accent-folded) substring
    if norm_q in norm_c:
        return 0.94, 6

    # Tier 7 (Score 0.93): Exact individual token match
    if q_tokens and c_tokens:
        if any(qt == ct for qt in q_tokens for ct in c_tokens):
            return 0.93, 7

    # Tier 8 (Score 0.90): Token prefix match (e.g. 'liv' prefix of 'Livia')
    if q_tokens and c_tokens:
        if any(ct.startswith(qt) for qt in q_tokens for ct in c_tokens if len(qt) >= 2):
            return 0.90, 8

    # Tier 9 (Score 0.70 to 0.88): Fuzzy similarity (SequenceMatcher) for typo tolerance
    best_ratio = SequenceMatcher(None, norm_q, norm_c).ratio()
    if c_tokens and len(q_tokens) == 1:
        for ct in c_tokens:
            token_ratio = SequenceMatcher(None, norm_q, ct).ratio()
            if token_ratio > best_ratio:
                best_ratio = token_ratio

    if best_ratio >= 0.72:
        scaled = min(0.88, max(0.70, round(0.70 + (best_ratio - 0.72) * (0.18 / 0.28), 4)))
        return scaled, 9

    return 0.0, 0


def score_document_match(query: str, document_values: Iterable[Optional[str]]) -> Tuple[float, int]:
    """
    Evaluate numeric document match (CPF, RG, RENACH, CNPJ) when query has >= 3 digits.
    Returns (0.99, 2) for exact digit match or (0.95, 5) for partial digit match.
    """
    q_digits = clean_digits(query)
    if len(q_digits) < 3:
        return 0.0, 0

    best_score = 0.0
    best_tier = 0
    for doc in document_values:
        d_digits = clean_digits(doc)
        if not d_digits:
            continue
        if q_digits == d_digits:
            return 0.99, 2
        if q_digits in d_digits:
            best_score = 0.95
            best_tier = 5
    return best_score, best_tier


def rank_records(
    records: Iterable[Dict[str, Any]],
    query: Optional[str],
    text_fields: Sequence[str] = ("name", "email", "role", "description"),
    doc_fields: Sequence[str] = ("cpf", "rg", "renach", "cnpj", "document"),
    min_score: float = 0.70,
) -> List[Dict[str, Any]]:
    """
    Rank and filter dictionary records using the 9-Tier ATIUS search hierarchy.
    Attaches `_search_score` and `_search_tier` metadata to each matched copy.
    """
    if not query or not str(query).strip():
        return [dict(item, _search_score=1.0, _search_tier=1) for item in records]

    q_str = str(query).strip()
    scored: List[Tuple[float, int, int, Dict[str, Any]]] = []

    for idx, item in enumerate(records):
        best_score = 0.0
        best_tier = 99

        # Evaluate text fields
        for field in text_fields:
            val = item.get(field)
            if isinstance(val, list):
                candidates = [str(x) for x in val if x is not None]
            elif val is not None:
                candidates = [str(val)]
            else:
                candidates = []

            for cand in candidates:
                sc, tier = score_text_match(q_str, cand)
                if sc > best_score or (sc == best_score and 0 < tier < best_tier):
                    best_score = sc
                    best_tier = tier

        # Evaluate numeric document fields
        doc_vals = [str(item.get(f)) for f in doc_fields if item.get(f)]
        doc_sc, doc_tier = score_document_match(q_str, doc_vals)
        if doc_sc > best_score or (doc_sc == best_score and 0 < doc_tier < best_tier):
            best_score = doc_sc
            best_tier = doc_tier

        if best_score >= min_score:
            enriched = dict(item)
            enriched["_search_score"] = round(best_score, 4)
            enriched["_search_tier"] = best_tier
            scored.append((best_score, -best_tier, -idx, enriched))

    scored.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
    return [entry[3] for entry in scored]
