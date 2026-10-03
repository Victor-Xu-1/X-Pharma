from __future__ import annotations

import re
from collections.abc import Iterable

from pharma_intel.governance.contracts import DocumentSegment, GovernanceError, PreparedSegmentFact, SourceQuoteMatch
from pharma_intel.governance.fact_identity import _prepared_fact_key


def _segments(text: str, max_chars: int, overlap: int = 1000) -> list[DocumentSegment]:
    if max_chars <= overlap:
        raise GovernanceError("AI_MAX_INPUT_CHARS must be larger than the extraction overlap")
    if len(text) <= max_chars:
        return [DocumentSegment(text=text, start_char=0, end_char=len(text))]
    segments: list[DocumentSegment] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        segments.append(DocumentSegment(text=text[start:end], start_char=start, end_char=end))
        if end == len(text):
            break
        start = end - overlap
    return segments


def _deduplicate_prepared_facts(facts: Iterable[PreparedSegmentFact]) -> list[PreparedSegmentFact]:
    unique: dict[str, PreparedSegmentFact] = {}
    for fact in facts:
        key = _prepared_fact_key(fact.prepared)
        previous = unique.get(key)
        candidate_rank = (fact.quote_verified, fact.prepared.fact.citation.confidence)
        previous_rank = (
            (
                previous.quote_verified,
                previous.prepared.fact.citation.confidence,
            )
            if previous is not None
            else None
        )
        if previous_rank is None or candidate_rank > previous_rank:
            unique[key] = fact
    return list(unique.values())


def _quote_source_match(quote: str, segment: DocumentSegment) -> SourceQuoteMatch | None:
    stripped = quote.strip()
    if not stripped:
        return None
    start = segment.text.find(stripped)
    end = start + len(stripped)
    if start < 0:
        tokens = stripped.split()
        if not tokens:
            return None
        match = re.search(r"\s+".join(re.escape(token) for token in tokens), segment.text, flags=re.IGNORECASE)
        if match is None:
            return None
        start, end = match.span()
    return SourceQuoteMatch(
        locator=f"chars={segment.start_char + start}-{segment.start_char + end}",
        quote=segment.text[start:end],
    )
