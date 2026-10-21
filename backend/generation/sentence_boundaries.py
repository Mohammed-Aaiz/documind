"""Shared abbreviation rules for claim and evidence sentence boundaries.

Two splitters in the generation package cut text at ``[.!?]`` followed by
whitespace:

* :func:`generation.planning.split_claims` splits a generated answer into claims;
* :func:`generation.verification.split_sentences` splits an evidence block into
  sentences for matching.

Both must agree on what is *not* a sentence end (``Dr.``, ``U.S.``, ``J.``,
``e.g.``), and both must still split after a real abbreviation at the end of a
sentence.  Keeping one predicate here avoids the two implementations drifting
apart, which is how the evidence-side defect survived the claim-side fix.

This is a deterministic heuristic, not a parser.  It errs toward *not* splitting
when the text after the period is a lower-case word or a digit, so a claim or
sentence is kept together rather than lost.
"""

from __future__ import annotations

import re

#: Abbreviations that do not end a sentence when followed by whitespace.  Titles,
#: initialisms and Latin abbreviations are here; abbreviations that commonly close
#: a sentence (``etc.``, ``Inc.``, ``Ltd.``) are deliberately absent, because a
#: capitalised next word must still start a new sentence.
NON_TERMINAL_ABBREVIATIONS = frozenset(
    {
        "dr", "mr", "mrs", "ms", "prof", "rev", "sr", "jr", "st", "hon",
        "vs", "e.g", "i.e", "cf", "al", "fig", "eq", "sec", "dept", "est",
        "u.s", "u.k", "u.n", "e.u", "u.s.a", "a.m", "p.m",
    }
)


def is_non_terminal_boundary(before: str, after: str) -> bool:
    """Whether the period at the end of ``before`` does not close a sentence.

    Suppressed cases:

    * an ellipsis (``Wait... what?``) always closes the sentence;
    * a trailing capital single letter standing alone is an initial (``J. Smith``);
    * a title, initialism or Latin abbreviation from the curated list (``Dr.``,
      ``U.S.``, ``e.g.``), even before a capital;
    * any other dotted abbreviation followed by a lower-case word or a digit
      (``Acme Inc. filed``, ``e.g. 3.5``).  A capitalised next word is treated as
      a real boundary, so ``… checked, etc. Nothing failed.`` still splits.
    """
    stripped = before.rstrip()
    if stripped.endswith("..."):
        return False
    match = re.search(r"([A-Za-z][A-Za-z.]*)$", stripped)
    if not match:
        return False
    token = match.group(1).rstrip(".")
    lowered = token.lower()
    # A single letter is an initial only when it stands alone; ``$8.3M.`` ends in
    # the unit suffix ``M``, not in an initial.  Lower-case letters are units
    # (``m/s.``) and do end a sentence.
    standalone = not stripped[: match.start()] or not stripped[match.start() - 1].isalnum()
    if len(token) == 1 and token.isalpha() and token.isupper() and standalone:
        return True
    if lowered in NON_TERMINAL_ABBREVIATIONS:
        return True
    following = after.lstrip()
    return bool(following) and (following[0].islower() or following[0].isdigit())
