"""
Deterministic intent classifier for the DocuMind Brain.

Classifies user requests into intents using transparent, inspectable
keyword-based rules.  No LLM, no external API, no probabilistic model.

Confidence values reflect the rule design honestly:
  • High (0.9) — clear keyword match
  • Medium (0.7) — probable match based on phrasing
  • Low (0.5) — ambiguous, best-effort classification
"""

from brain.types import Intent, ParsedRequest


# ---------------------------------------------------------------------------
# Keyword sets for each intent
# ---------------------------------------------------------------------------

_QUESTION_MARKERS = frozenset({
    "who", "what", "when", "where", "why", "how",
    "which", "whom", "whose",
})

_QUESTION_PHRASES = (
    "when did", "when was", "when were", "when is",
    "who was", "who is", "who were", "who wrote",
    "what is", "what are", "what was", "what were", "what does",
    "how many", "how much", "how did", "how does", "how long",
    "where did", "where was", "where are",
    "why did", "why does", "why is",
    "can you", "could you", "tell me",
    "according to", "based on",
    "in the document", "in the file", "in this",
    "from the", "mentioned in",
)

_SUMMARY_MARKERS = frozenset({
    "summarize", "summary", "summarise", "summarisation",
    "overview", "recap", "brief", "condensed",
    "tldr", "tl;dr", "short version", "key points",
})

_SEARCH_MARKERS = frozenset({
    "search", "find", "look for", "locate", "search for",
    "find mentions", "find references", "find all",
    "where is", "where are", "contains",
})

_MEDIA_MARKERS = frozenset({
    "image", "video", "photo", "picture", "media",
    "deepfake", "fake", "synthetic", "manipulated",
    "verify", "verification", "authentic", "authenticity",
    "check image", "check video", "check photo",
    "is this real", "is this fake", "is this ai",
    "lip sync", "blink rate", "face",
})


def _clean(text: str) -> str:
    """Normalize input text."""
    return " ".join(text.lower().split())


def classify(text: str) -> ParsedRequest:
    """Classify a user request into an intent.

    Returns a ParsedRequest with the classified intent and an honest
    confidence value reflecting the rule-based classification quality.
    """
    cleaned = _clean(text)

    if not cleaned:
        return ParsedRequest(
            cleaned_text=cleaned,
            intent=Intent.UNSUPPORTED_REQUEST,
            intent_confidence=1.0,
        )

    # --- Media verification (check first — specific domain) ---
    for marker in _MEDIA_MARKERS:
        if marker in cleaned:
            return ParsedRequest(
                cleaned_text=cleaned,
                intent=Intent.MEDIA_VERIFICATION,
                intent_confidence=0.85,
            )

    # --- Summary request ---
    for marker in _SUMMARY_MARKERS:
        if marker in cleaned:
            return ParsedRequest(
                cleaned_text=cleaned,
                intent=Intent.DOCUMENT_SUMMARY,
                intent_confidence=0.9,
            )

    # --- Search request ---
    for marker in _SEARCH_MARKERS:
        if marker in cleaned:
            return ParsedRequest(
                cleaned_text=cleaned,
                intent=Intent.DOCUMENT_SEARCH,
                intent_confidence=0.8,
            )

    # --- Document question ---
    # Check for question phrases first (higher confidence)
    for phrase in _QUESTION_PHRASES:
        if phrase in cleaned:
            return ParsedRequest(
                cleaned_text=cleaned,
                intent=Intent.DOCUMENT_QUESTION,
                intent_confidence=0.9,
            )

    # Check for question words at start
    first_word = cleaned.split()[0] if cleaned.split() else ""
    if first_word in _QUESTION_MARKERS:
        return ParsedRequest(
            cleaned_text=cleaned,
            intent=Intent.DOCUMENT_QUESTION,
            intent_confidence=0.85,
        )

    # Check for question mark
    if "?" in cleaned:
        return ParsedRequest(
            cleaned_text=cleaned,
            intent=Intent.DOCUMENT_QUESTION,
            intent_confidence=0.75,
        )

    # --- Default: treat as a document question with low confidence ---
    # Most user input to DocuMind is expected to be document-related.
    # If nothing else matches, assume question but with honest low confidence.
    return ParsedRequest(
        cleaned_text=cleaned,
        intent=Intent.DOCUMENT_QUESTION,
        intent_confidence=0.5,
    )
