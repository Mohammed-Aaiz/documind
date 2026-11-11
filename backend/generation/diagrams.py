"""Bounded, source-described process figures; never invented construction geometry.

The provider may draw unsupported arrows or omit a figure. Recovery uses only
an explicit source arrow chain or consecutive steps in one document/topic. It
adds no inference request and keeps the citation on every displayed label.
"""
from __future__ import annotations

import re
import textwrap
from collections import defaultdict
from typing import Sequence

from generation.types import EvidenceBlock

_ARROW = re.compile(r"(?:[-=]+>|→|⇒)")
_RELATION = re.compile(
    r"\b(?:driv(?:e|es|en|ing)|turn(?:s|ed|ing)?|transfer(?:s|red|ring)?|keep(?:s|ing)?|"
    r"convert(?:s|ed|ing)?|flow(?:s|ed|ing)|caus(?:e|es|ed|ing)|produc(?:e|es|ed|ing)|"
    r"generat(?:e|es|ed|ing)|connect(?:s|ed|ing)?|suppl(?:y|ies|ied|ying)|"
    r"rotat(?:e|es|ed|ing)|power(?:s|ed|ing)|feed(?:s|ing)?|fed|"
    r"releas(?:e|es|ed|ing)|lead(?:s|ing)?|led|result(?:s|ed|ing)?|"
    r"strik(?:e|es|ing)|increas(?:e|es|ed|ing))\b", re.I,
)
_STEP = re.compile(r"(?:^|\n|>\s*)(\d{1,2})[.)]\s+(.+?)(?=\n\s*\d{1,2}[.)]\s|\Z)", re.S)
_FORM_WORDS = frozenset("explain describe define discuss compare contrast evaluate draw sketch show provide include illustrate diagram diagrams neat with using the of a an and or working principle operation construction following".split())
MAX_FIGURES = 4
MAX_STEPS = 8


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _key(value: str) -> str:
    from generation.planning import strip_citations
    return re.sub(r"\W+", " ", strip_citations(value).casefold()).strip()


def _terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9]*", value.casefold())) - _FORM_WORDS


def _relevant(blocks: Sequence[EvidenceBlock], subject: str) -> list[EvidenceBlock]:
    from generation.topic_context import select_topic_heading_path, topic_acronyms
    terms = _terms(subject)
    result = []
    acronyms = topic_acronyms(subject)
    # A recovered window is anchored by its named definition. Anonymous body
    # steps may share that context, but an unrelated chapter or document cannot.
    anchored_windows = set()
    for block in blocks:
        path = block.heading_path or ((block.section,) if block.section else ())
        if (block.topic_context_kind == "section_window" and block.topic_context_id
                and select_topic_heading_path(subject, path)):
            anchored_windows.add((block.document_id, block.topic_context_id))
    for block in blocks:
        path = block.heading_path or ((block.section,) if block.section else ())
        # A named acronym narrows a broad wind/energy match to its own topic.
        text = " ".join(path) + " " + block.content
        window_match = (block.topic_context_kind == "section_window"
                        and (block.document_id, block.topic_context_id) in anchored_windows)
        if acronyms and not all(word in _terms(text) or word + "s" in _terms(text) for word in acronyms) and not window_match:
            continue
        if window_match or select_topic_heading_path(subject, path) or (terms and terms <= _terms(block.content)):
            result.append(block)
    return result


def _arrow_chains(block: EvidenceBlock) -> list[list[str]]:
    chains = []
    for line in block.content.splitlines():
        if not _ARROW.search(line):
            continue
        parts = [_plain(part).strip(" .;:") for part in _ARROW.split(line)]
        # A lead-in such as "The conversion is: A -> B" is prose, not a node.
        parts[0] = parts[0].rsplit(":", 1)[-1].strip()
        if 2 <= len(parts) <= MAX_STEPS and all(1 <= len(part) <= 100 for part in parts):
            if not any(re.search(r"[<>`{}]", part) for part in parts):
                chains.append(parts)
    return chains


def _step_groups(blocks: Sequence[EvidenceBlock]) -> list[list[tuple[int, str, int]]]:
    from generation.verification import split_sentences
    groups: dict[tuple, dict[int, tuple[str, int]]] = defaultdict(dict)
    conflicts = set()
    for block in blocks:
        if block.truncated:
            continue
        path = tuple(block.heading_path or ())
        context = " ".join(path) + " " + (block.section or "")
        # Numbering an inventory or a list of benefits establishes no process.
        if re.search(r"\b(?:inventory|advantages?|disadvantages?|benefits?|limitations?|properties|types|features)\b", context, re.I):
            continue
        # A chapter-level "conversion" heading may also contain inventories or
        # design notes. It does not by itself establish process order; the
        # sentence still needs an explicit action relation, unless a narrower
        # working/steps/process heading supplies the procedural context.
        procedural = bool(re.search(r"\b(?:steps?|working|procedure|process|operation|sequence)\b", context, re.I))
        # The last heading is often the numbered body/"Working step N".
        if len(path) > 1:
            path = path[:-1]
        group = block.topic_context_id if block.topic_context_kind == "section_window" else None
        identity = (block.document_id or ("block", block.index), group or path or block.section or ("block", block.index))
        for match in _STEP.finditer(block.content):
            sentences = split_sentences(match.group(2))
            if not sentences:
                continue
            sentence = _plain(sentences[0])
            number = int(match.group(1))
            if not 1 <= number <= 30 or not 20 <= len(sentence) <= 300 or not sentence.endswith((".", "!", "?")):
                continue
            if not procedural and not _RELATION.search(sentence):
                continue
            # A numbered property (for example, "no yaw alignment is
            # required") is not a step in the energy-conversion sequence.
            if re.search(r"\b(?:no|without|not required)\b.{0,60}\b(?:alignment|yaw)\b|\b(?:alignment|yaw)\b.{0,60}\bnot required\b", sentence, re.I):
                continue
            existing = groups[identity].get(number)
            if existing and _key(existing[0]) != _key(sentence):
                conflicts.add(identity)
            groups[identity].setdefault(number, (sentence, block.index))
    result = []
    for identity, steps in groups.items():
        if identity in conflicts:
            continue
        run: list[tuple[int, str, int]] = []
        for number, (sentence, citation) in sorted(steps.items()):
            if run and number != run[-1][0] + 1:
                if len(run) >= 2:
                    result.append(run[:MAX_STEPS])
                run = []
            run.append((number, sentence, citation))
        if len(run) >= 2:
            result.append(run[:MAX_STEPS])
    return result


def _nodes_and_edges(diagram: str) -> tuple[list[tuple[str, list[int]]], list[tuple[int, int]]]:
    """Read simple vertical/horizontal connections, not arbitrary graph geometry."""
    from generation.planning import _DIAGRAM_DECORATION_RE, extract_citations, strip_citations
    nodes: list[tuple[str, list[int]]] = []
    edges: list[tuple[int, int]] = []
    current = []
    incoming = None
    pending = None

    def flush():
        nonlocal current, incoming
        if current:
            label = _plain(" ".join(current))
            index = len(nodes)
            nodes.append((strip_citations(label), extract_citations(label)))
            if incoming is not None and index:
                edges.append((index - 1, index) if incoming == "forward" else (index, index - 1))
            current, incoming = [], None

    for raw in diagram.splitlines():
        line = raw.strip()
        if not line or re.match(r"^(?:figure|diagram)\s*:", line, re.I):
            continue
        if _DIAGRAM_DECORATION_RE.fullmatch(line):
            # Box borders express no connection. Bare shafts/arrows do.
            if not re.search(r"[+┌┐└┘─━_=]", line) and re.search(r"[|│↓↑vV^▼▲<>]", line):
                flush()
                pending = "reverse" if re.search(r"[↑^▲<]", line) else "forward"
            continue
        horizontal = re.split(r"([-]+>|→|⇒|<[-]+)", line)
        if len(horizontal) > 1:
            flush()
            for position in range(0, len(horizontal), 2):
                node = horizontal[position].strip(" |│")
                index = len(nodes)
                nodes.append((strip_citations(node), extract_citations(node)))
                if position:
                    edges.append((index, index - 1) if horizontal[position - 1].startswith("<") else (index - 1, index))
            pending = None
            continue
        if not current:
            incoming, pending = pending, None
        current.append(line.strip(" |│┌┐└┘"))
    flush()
    return nodes, edges


def connections_supported(diagram: str, blocks: Sequence[EvidenceBlock]) -> bool:
    """Every displayed edge needs cited relation text or explicit source order.

    This is a conservative textual check, not semantic entailment. Separate
    mentions and reversed arrow chains do not establish a connection.
    """
    from generation.verification import split_sentences
    nodes, edges = _nodes_and_edges(diagram)
    by_index = {block.index: block for block in blocks}
    step_edges = set()
    numbered_step_edges = set()
    for group in _step_groups(blocks):
        for left, right in zip(group, group[1:]):
            step_edges.add((_key(f"{left[0]}. {left[1]}"), left[2], _key(f"{right[0]}. {right[1]}"), right[2]))
            numbered_step_edges.add((left[0], left[2], right[0], right[2]))
    for left_index, right_index in edges:
        left, left_cites = nodes[left_index]
        right, right_cites = nodes[right_index]
        if any((_key(left), a, _key(right), b) in step_edges for a in left_cites for b in right_cites):
            continue
        left_number = re.match(r"\s*(\d+)[.)]", left)
        right_number = re.match(r"\s*(\d+)[.)]", right)
        if left_number and right_number and any(
            (int(left_number.group(1)), a, int(right_number.group(1)), b) in numbered_step_edges
            for a in left_cites for b in right_cites
        ):
            # Short heading labels remain readable when the source sentence is
            # too long to wrap into separately checked, unsupported fragments.
            continue
        left_terms, right_terms = _terms(left), _terms(right)
        supported = False
        for citation in set(left_cites + right_cites):
            block = by_index.get(citation)
            if block is None:
                continue
            if any(left_terms and right_terms and left_terms <= _terms(a) and right_terms <= _terms(b)
                   for chain in _arrow_chains(block) for a, b in zip(chain, chain[1:])):
                supported = True
                break
            # A predicate elsewhere in a sentence does not connect these two
            # labels. Keep the directed match inside one clause and between
            # the labels; do not interpret nouns such as "generator power" as
            # verbs, or bridge an unrelated clause after a semicolon.
            clauses = (clause for sentence in split_sentences(block.content)
                       for clause in re.split(r"[;]|\b(?:and|or|but|while|whereas|although)\b", sentence, flags=re.I))
            for clause in clauses:
                if re.search(r"\b(?:not|never|neither|without|cannot)\b|n't\b", clause, re.I):
                    continue
                # Passive "is driven by" reverses textual order. Such cases
                # require explicit source order rather than this small parser.
                if re.search(r"\bby\b", clause, re.I) and re.search(r"\b(?:is|are|was|were|be|been|being)\b", clause, re.I):
                    continue
                terms = _terms(clause)
                left_only, right_only = left_terms - right_terms, right_terms - left_terms
                if not left_only or not right_only or not (left_terms | right_terms) <= terms:
                    continue
                words = list(re.finditer(r"[a-z][a-z0-9]*", clause.casefold()))
                left_end = max(word.end() for word in words if word.group() in left_only)
                right_start = min(word.start() for word in words if word.group() in right_only)
                predicates = list(_RELATION.finditer(clause, left_end, right_start)) if left_end < right_start else []
                if len(predicates) == 1:
                    supported = True
                    break
            if supported:
                break
        if not supported:
            return False
    return True


def _render(labels: Sequence[tuple[str, int]]) -> str:
    from generation.planning import _with_citation
    lines = []
    for position, (label, citation) in enumerate(labels):
        if position:
            lines.extend(("           |", "           v"))
        heading = re.match(r"^\s*(\d+[.)])\s+([^:]{2,90}):(?:\s|$)", label)
        display = f"{heading.group(1)} {heading.group(2).strip()}" if heading else label
        rows = textwrap.wrap(display, width=62, break_long_words=False, break_on_hyphens=False)
        # Every wrapped label remains directly attributable to its own source.
        rows = [_with_citation(row, citation) for row in rows]
        width = max(len(row) for row in rows)
        lines.append("+" + "-" * (width + 2) + "+")
        lines.extend("| " + row.ljust(width) + " |" for row in rows)
        lines.append("+" + "-" * (width + 2) + "+")
    return "```text\n" + "\n".join(lines) + "\n```"


def ensure_source_diagrams(answer: str, blocks: Sequence[EvidenceBlock], question: str) -> tuple[str, list[str]]:
    """Complete requested figures after prose repair; report exact missing parts."""
    from generation.planning import extract_citations, text_diagram_blocks, validate_text_diagram
    from generation.provider_prompt import asks_for_diagram, student_question_plan
    from generation.topic_context import topic_acronyms
    if not asks_for_diagram(question):
        return answer, []
    _, parts = student_question_plan(question)
    requests = parts or (question,)
    notes = []
    figures = text_diagram_blocks(answer) or []
    for subject in requests[:MAX_FIGURES]:
        relevant = _relevant(blocks, subject)
        indices = {block.index for block in relevant}
        if any(set(extract_citations(figure)) and set(extract_citations(figure)) <= indices for figure in figures):
            continue
        candidates = []
        groups = _step_groups(relevant)
        if groups:
            candidates.extend(_render([(f"{number}. {sentence}", citation) for number, sentence, citation in group])
                              for group in sorted(groups, key=len, reverse=True))
        # Wrapped source sentences can fail conservative lexical attribution.
        # Try another explicit source representation before reporting a gap.
        candidates.extend(_render([(label, block.index) for label in chain])
                          for block in relevant for chain in _arrow_chains(block))
        candidate = next((figure for figure in candidates if len(figure)<=8000
                          and validate_text_diagram(figure, blocks, question=question)), "")
        if candidate:
            # A source-observed subject name distinguishes multipart figures.
            # It is cited and checked as prose, rather than inventing a title.
            caption = ""
            for acronym in sorted(topic_acronyms(subject)):
                for block in relevant:
                    match = re.search(r"\b" + re.escape(acronym) + r"s?\b", block.content, re.I)
                    if match:
                        caption = f"**{match.group()}** [{block.index}]"
                        break
                if caption:
                    break
            answer += "\n\n" + (caption + "\n\n" if caption else "") + candidate
            figures.extend(text_diagram_blocks(candidate) or [])
            notes.append("A source-described process sequence is shown for: " + subject + ". It does not establish physical construction geometry.")
        else:
            notes.append("The supplied excerpts do not support a process or construction diagram for: " + subject)
    if len(requests) > MAX_FIGURES:
        notes.append("Diagrams are limited to four requested parts; remaining parts require a separate question.")
    return answer, notes
