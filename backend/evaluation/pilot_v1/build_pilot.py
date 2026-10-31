"""Build the unreviewed educational pilot from a pinned, openly licensed PDF.

Only --acquire uses the network. PDF bytes remain in ignored source_cache/.
No application imports, database, model downloads or provider calls are used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parent
PDF_URL = "https://assets.openstax.org/oscms-prodcms/media/documents/College_Physics-WEB_2s5sHvR.pdf"
PDF_SHA256 = "e4e91aa48b4e95ccdbac33ae938dae7e890bc0e123796635052bcafe53301671"
DOC_ID = "openstax-college-physics-1e-selected-electricity"
BUNDLE = "pilot-electricity-development"
ATTRIBUTION = "College Physics, Paul Peter Urone and Roger Hinrichs / OpenStax, Rice University, 2020. CC BY 4.0. Access for free at openstax.org."
TOPICS = {"20.1": "Current", "20.2": "Ohm's law", "20.3": "Resistance and resistivity",
          "20.4": "Electric power and energy", "20.5": "AC and DC", "20.6": "Electrical hazards",
          "21.1": "Series and parallel resistors", "21.2": "Emf and internal resistance", "21.6": "RC circuits"}
PAGES = list(range(862, 885)) + list(range(906, 920)) + list(range(937, 942))


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(raw: str) -> str:
    """Before annotation: trim lines, fold horizontal runs, at most one blank line."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def span(pages: dict, page: int, start: str, end: str) -> dict:
    topic = ("20.1" if page <= 867 else "20.2" if page <= 870 else "20.3" if page <= 875
             else "20.4" if page <= 878 else "20.5" if page <= 883 else "20.6" if page <= 884
             else "21.1" if page <= 915 else "21.2" if page <= 919 else "21.6")
    if page == 870 and start.startswith("The resistance of an object"):
        topic = "20.3"
    text = pages[page]["canonical_text"]
    begin = re.search(r"\s+".join(re.escape(part) for part in start.split()), text)
    if begin is None:
        raise ValueError(f"Missing start anchor on PDF page {page}: {start}")
    finish = re.search(r"\s+".join(re.escape(part) for part in end.split()), text[begin.start():])
    if finish is None:
        raise ValueError(f"Missing end anchor on PDF page {page}: {end}")
    lo, hi = begin.start(), begin.start() + finish.end()
    quote = text[lo:hi]
    return {"document_id": DOC_ID, "page": page, "topic_id": topic,
            "start_char": lo, "end_char": hi, "quote": quote, "quote_sha256": digest(quote.encode())}


def unit(pages: dict, identity: str, requirement: str, *locations) -> dict:
    return {"id": identity, "requirement": requirement,
            "alternatives": [{"all_of": [span(pages, *location) for location in locations]}]}


def rubric(marks: int, units: list[dict], missing: list[str]) -> dict:
    if missing:
        maxima = {5: (2, 2, 1), 10: (4, 4, 2), 15: (6, 6, 3)}[marks]
        statements = ["Explicitly state that the requested result cannot be determined from the supplied corpus.",
                      "Identify the missing information: " + "; ".join(missing),
                      "Give a concise, coherent explanation without fabricating measurements, formulas or citations."]
        criteria = [{"id": f"negative-{i+1}", "description": description, "max_marks": maximum,
                     "evidence_unit_ids": [], "partial_credit": "Full credit for explicit correct statement; half for an incomplete but correct statement; zero for absent/incorrect statement."}
                    for i, (description, maximum) in enumerate(zip(statements, maxima))]
    else:
        content, accuracy, structure = {5: (3, 1, 1), 10: (6, 3, 1), 15: (10, 3, 2)}[marks]
        base, remainder = divmod(content, len(units))
        criteria = [{"id": f"content-{i+1}", "description": item["requirement"],
                     "max_marks": base + (i < remainder), "evidence_unit_ids": [item["id"]],
                     "partial_credit": "Full credit covers the whole requirement accurately; half covers a correct material part; zero omits or contradicts it."}
                    for i, item in enumerate(units)]
        criteria += [{"id": "accuracy", "description": "Keep entity bindings, conditions, units and directions correct; do not introduce unsupported facts.",
                      "max_marks": accuracy, "evidence_unit_ids": [u["id"] for u in units],
                      "partial_credit": "Full credit: no material error; half: minor error without changing the conclusion; zero: a central contradiction or invented result."},
                     {"id": "organization", "description": "Present the requested explanation or comparison in a coherent order with explicit connections.",
                      "max_marks": structure, "evidence_unit_ids": [],
                      "partial_credit": "Full credit: traceable explanation; half: understandable but disordered; zero: disconnected statements. No credit merely for length or headings."}]
    return {"max_marks": marks, "status": "draft_requires_subject_review", "criteria": criteria,
            "error_policy": "No negative total marks. A factual contradiction loses the corresponding content/accuracy credit; do not apply an additional hidden penalty."}


def build(pdf_path: Path) -> dict:
    import pymupdf
    raw_bytes = pdf_path.read_bytes()
    if digest(raw_bytes) != PDF_SHA256:
        raise ValueError("Source PDF changed; a new reviewed dataset version is required")
    pdf = pymupdf.open(stream=raw_bytes, filetype="pdf")
    pages = {}
    for number in PAGES:
        raw_text = pdf[number - 1].get_text(sort=True)
        text = canonical(raw_text)
        history = []
        if number == 871:
            # Numeric math glyphs are omitted by the PDF text extractor. This
            # explicitly labelled visual transcription was checked against a
            # rendered original page by the coding agent, not human-reviewed.
            text += ("\n[DRAFT VISUAL TRANSCRIPTION: Table 20.1, PDF page 871, printed page 853]\n"
                     "Resistivities of various materials at 20 degrees Celsius.\n"
                     "Material | Resistivity (ohm metre) | Category\n"
                     "Silver | 1.59 x 10^-8 | Conductors\n"
                     "Copper | 1.72 x 10^-8 | Conductors\n")
            history.append({"kind": "AI-assisted visual transcription", "source_region_points": [188, 428, 418, 730],
                            "scope": "Table title, column units and silver/copper rows only",
                            "review_status": "not_independently_human_reviewed"})
        pages[number] = {"page": number, "printed_page_label": str(number - 18),
                         "canonical_text": text, "canonical_text_sha256": digest(text.encode()),
                         "raw_extracted_text_sha256": digest(raw_text.encode()),
                         "attribution": ATTRIBUTION, "correction_history": history}

    questions = []
    def add(identity, category, marks, question, answer, requirements=(), tags=(), missing=()):
        units = [unit(pages, f"{identity}-u{i+1}", requirement, *locations)
                 for i, (requirement, locations) in enumerate(requirements)]
        topic_ids = sorted({s["topic_id"] for u in units for alt in u["alternatives"] for s in alt["all_of"]})
        questions.append({"id": identity, "bundle_id": BUNDLE, "split": "development",
            "status": "draft_unreviewed", "category": category, "category_status": "proposed_requires_independent_review",
            "difficulty": "proposed_" + ({5:"introductory",10:"intermediate",15:"advanced"}[marks]),
            "designated_marks": marks, "question": question, "answerability": "unanswerable" if missing else "answerable",
            "topic_ids": topic_ids, "tags": list(tags), "reference_answer": answer,
            "reference_answer_provenance": "AI-assisted draft authored from the cited textbook, not an output from a tested retrieval system",
            "required_evidence_units": units, "missing_requirements": list(missing),
            "rubrics": {str(marks): rubric(marks, units, list(missing))},
            "independent_annotation_reviews": [{"reviewer_id": None, "decision": None, "notes": None},
                                               {"reviewer_id": None, "decision": None, "notes": None}],
            "adjudication": None})

    add("L1", "localized_single_topic", 5,
        "Define conventional current direction and compare it with the motion of electrons in a metal wire.",
        "Conventional current follows the direction positive charge would move. In a metal the moving carriers are negative electrons, so their motion is opposite to conventional current.",
        [("State the positive-charge convention and opposite electron motion.", [(865,"Conventional current is","electronic flow.")])])
    add("L2", "localized_single_topic", 5,
        "What makes a material ohmic, and is Ohm's law universally valid?",
        "An ohmic material has resistance independent of the applied voltage and current under the stated conditions. Ohm's law is not universally valid; copper and aluminium are examples of materials that can be ohmic.",
        [("Define ohmic behavior and explicitly reject universal validity.", [(869,"Ohm’s law (like","even if its\nresistance is small.")])])
    add("L3", "localized_single_topic", 5,
        "Using Table 20.1 at 20 degrees Celsius, give the resistivities and category of silver and copper, including units.",
        "Silver: 1.59 x 10^-8 ohm metre; copper: 1.72 x 10^-8 ohm metre. Both appear under conductors. The values apply at 20 degrees Celsius.",
        [("Supply both correctly labelled resistivities, units, temperature and category.", [(871,"Resistivities of various materials at 20 degrees Celsius.","Copper | 1.72 x 10^-8 | Conductors")])],
        tags=["table", "visual_transcription_draft"])
    add("L4", "localized_single_topic", 5,
        "What components define an RC circuit, and what does its capacitor store?",
        "An RC circuit contains a resistor and a capacitor. The capacitor stores electric charge.",
        [("Identify resistor and capacitor and charge storage.", [(937,"An RCcircuit is","charge.")])])

    add("D1", "distributed_single_topic", 10,
        "Explain within the topic of electric current why an electrical signal travels rapidly while electrons drift slowly, and why an ordinary conductor needs continuous energy input.",
        "The signal is a rapidly propagating change in electric field, passed along through interactions between charges. Individual free electrons undergo many collisions and have a small average drift velocity. Collisions transfer energy to the conductor's atoms, so continuous power is needed to maintain an ordinary current; superconductors are an exception.",
        [("Distinguish propagating field signal from carrier drift.", [(866,"The high speed of electrical signals","moving signal or shock wave is a rapidly propagating change in electric field."), (866,"Good conductors have","given current.")]),
         ("Explain collisions, energy transfer, continuous input and the superconducting exception.", [(866,"The free-electron collisions transfer energy","The work is"),(867,"transferred to the conductor’s atoms","a great energy savings.")])], tags=["page_crossing_topic", "repeated_running_headings"])
    add("D2", "distributed_single_topic", 15,
        "Explain how material, length, cross-sectional area and temperature affect resistance, contrasting ordinary metallic conductors and the listed semiconductors.",
        "Resistance increases with length and decreases with cross-sectional area. Resistivity is an intrinsic material property independent of shape and size. In ordinary metals warming increases atomic vibration and electron collisions, so resistivity rises. The listed semiconductors have decreasing resistivity with increasing temperature because more free charges become available; impurity type and amount also matter.",
        [("Explain length, area and intrinsic material dependence.", [(870,"The resistance of an object depends","similar to the resistance of a pipe to fluid flow."),(871,"longer the cylinder","sectional area"),(871,"For a given shape","independent of its shape or size.")]),
         ("Contrast metallic and semiconductor temperature response with mechanisms.", [(873,"Conversely, the resistivity of conductors","effectively making the resistivity higher."),(875,"Note also that","impurities present in the semiconductors.")])], tags=["page_crossing_topic"])
    add("D3", "distributed_single_topic", 10,
        "Compare the major features of series and parallel resistor connections: total resistance, current sharing and voltage sharing.",
        "In series, resistances add, the same current passes through every resistor, and the source voltage is divided. In parallel, equivalent resistance is below any individual resistance, each branch receives the full source voltage, and branch currents divide the total current.",
        [("State all three series features.", [(909,"Major Features of Resistors in Series","divide it.")]),
         ("State all three parallel features.", [(912,"Major Features of Resistors in Parallel","divide it.")])], tags=["page_crossing_topic", "repeated_headings"])
    add("D4", "distributed_single_topic", 15,
        "Describe charging and discharging in an RC circuit, the fractions reached after one time constant, and why a flash camera charges more slowly than it discharges.",
        "During charging the capacitor voltage rises toward the source emf while current falls. After one time constant it has reached 0.632 of its final value. During discharge its voltage falls exponentially to 0.368 of its previous value in each time constant. A flash camera has much greater resistance while charging, largely from its battery; its flash discharges through low-resistance ionized gas, so discharge is far quicker.",
        [("Describe charging voltage/current and the 0.632 fraction.", [(937,"The current thus decreases","the voltage source."),(938,"This means that in the time","achieved in every time,")]),
         ("Describe discharge fraction and the resistance explanation for camera timing.", [(938,"During each successive time","graph in Figure 21.39(b)."),(938,"Now we can explain why","proceeds very rapidly.")])], tags=["page_crossing_topic"])

    add("M1", "multi_topic_synthesis", 10,
        "Compare intended energy conversion in a simple resistor circuit with thermal and shock hazards. Distinguish the three ideas without treating every heating effect as a shock.",
        "In a simple circuit the source supplies energy that the resistor converts, for example to thermal energy. Heating is a thermal hazard when energy is delivered too rapidly to be dissipated safely, potentially starting a fire. A shock hazard instead requires current through a person; intended resistor heating is not by itself a shock.",
        [("Describe intended source-to-resistor energy conversion.", [(870,"The voltage source supplies energy","the energy converted by the resistor are equal.")]),
         ("Distinguish thermal and shock hazards and unsafe heating rate.", [(884,"There are two known hazards","quantitative manner."),(884,"Electric power causes undesired heating effects","can be safely dissipated.")])])
    add("M2", "multi_topic_synthesis", 5,
        "Compare the conventional current direction rule with the distinction between direct and alternating current.",
        "Conventional current is defined by positive-charge motion, opposite to electron motion. DC flows in one direction, whereas AC periodically reverses direction. These are different distinctions: the sign convention defines direction, while AC/DC describes its variation over time.",
        [("Explain the sign convention.", [(865,"Conventional current is","electronic flow.")]),
         ("Distinguish one-direction DC and periodically reversing AC.", [(879,"Direct current (DC)","alternating current circuit.")])])
    add("M3", "multi_topic_synthesis", 10,
        "Compare the simple voltage-source/resistor model with a real battery model, distinguishing emf, terminal voltage and internal resistance.",
        "A simple circuit is modelled with one source and one resistor and negligible wire resistance, or wire resistance included in the load. A real source also has internal resistance. Emf is its no-current potential difference; terminal voltage is lower while supplying current and equals emf when measured without drawing current. Larger internal resistance reduces the available current and terminal voltage.",
        [("State the simple circuit and wire-resistance assumption.", [(869,"A simple circuit has","resistance can be included in")]),
         ("Define emf and distinguish loaded terminal voltage/internal resistance.", [(916,"Emf is not a force at all","Units of emf are volts."),(917,"Electromotive force is directly related","emf (even for a very depleted battery)."),(919,"You can see that the larger the current","smaller the terminal voltage.")])])
    add("M4", "multi_topic_synthesis", 15,
        "Compare the roles of a resistor and a capacitor using the sections on resistance, electric power and RC circuits; include current limitation, energy conversion and charge storage.",
        "Resistance impedes current through collisions and associated energy transfer. In a simple resistive circuit the source's supplied power is dissipated by the resistor. A capacitor stores charge; in an RC circuit its growing voltage opposes the battery and charging current falls toward zero. Thus resistance-mediated dissipation and charge storage are distinct roles, even when both components are present together.",
        [("Describe resistance as current opposition with energy transfer and resistive power conversion.", [(868,"The electric property that impedes current","limit current."),(877,"In a simple circuit, with one","by the resistor are identical.")]),
         ("Describe capacitor storage and the change during RC charging.", [(937,"An RCcircuit is","charge."),(937,"This voltage opposes the battery","the voltage source.")])])

    add("R1", "relational_multihop", 15,
        "Trace the causal chain from a cold headlight filament to its initially high current/power, then explain why warming changes the initial behavior.",
        "The cold filament has lower resistance and initially draws more current. At a fixed source voltage lower resistance means greater delivered power, so initial power is high. Warming increases collisions and metallic resistivity; the filament resistance rises and the initial power decreases. The excerpt reports about 411 W cold and 30 W hot for its example, not a universal bulb rating.",
        [("Connect cold filament resistance to current and power at a fixed source voltage.", [(869,"As we shall see in Resistance","its brief warm-up period."),(877,"the lower the resistance connected","the greater the power delivered.")]),
         ("Connect warming to metallic resistance and declining example power.", [(873,"Conversely, the resistivity of conductors","effectively making the resistivity higher."),(877,"The 30 W dissipated","its resistance increases.")])], tags=["causal_relation_chain"])
    add("R2", "relational_multihop", 10,
        "Trace how battery depletion can reduce delivered current and make a camera's capacitor take longer to recharge, using both source internal resistance and RC charging.",
        "As a battery is depleted its internal resistance rises. That extra resistance can reduce current to its load. Camera charging includes the battery's internal resistance, so increasing it reduces charging current and lengthens recharge time; the capacitor must accumulate charge through that higher-resistance path.",
        [("Connect battery depletion to increased internal resistance and reduced supplied current.", [(917,"The internal resistance can behave","a battery is depleted."),(919,"We see from this expression","significantly reduced, as the following example illustrates.")]),
         ("Connect increased battery resistance to slower camera RC charging.", [(937,"Note that the internal resistance of the voltage source","get ready for the next flash.")])], tags=["causal_relation_chain"])
    add("R3", "relational_multihop", 15,
        "For a fixed amount of transmitted power, trace why higher transmission voltage reduces current and line loss, and connect this to the practical choice of AC distribution.",
        "Power is current times voltage, so delivering fixed power at higher voltage requires less current. In fixed-resistance lines lower current reduces resistive loss; the textbook's comparison explicitly states lower voltage needs more current and greater loss. AC is convenient because its voltage is much easier to raise for transmission and lower at the user, combining reduced long-distance loss with safer point-of-use voltage.",
        [("Connect fixed transmitted power and voltage to the necessary current.", [(877,"Electric power (","current times voltage."),(883,"The lower the voltage","fixed-resistance transmission lines.")]),
         ("Connect lower losses to transformer-compatible AC distribution.", [(882,"High voltages can be transmitted","power distribution systems.")])], tags=["causal_relation_chain"])
    add("R4", "relational_multihop", 15,
        "Trace the chain from switching on a high-current motor to a nearby lamp dimming, connecting wire resistance, voltage drop and power delivered to the lamp.",
        "A high-current device increases the shared wire current. Its wire resistance causes a larger voltage drop, reducing the voltage across the lamp, which dims. This is consistent with lower delivered load current/power when wire resistance is significant, and with a resistor's delivered power increasing strongly with applied voltage at otherwise comparable resistance. The simple model that ignores wire resistance can miss the effect.",
        [("Connect high device current through shared wire resistance to reduced lamp voltage and dimming.", [(915,"What is happening in these high-current situations","then dims noticeably.")]),
         ("Connect appreciable wire resistance to lower load power and distinguish ideal assumptions.", [(915,"One implication of this last example","this loss can be significant."),(877,"Furthermore, since voltage is","its power would be exactly 100 W")])], tags=["causal_relation_chain"])

    add("U1", "unanswerable", 5,
        "From Table 20.1 alone, report the numerical uncertainty or confidence interval for copper's listed resistivity at 20 degrees Celsius.",
        "The supplied table gives a representative resistivity but no measurement uncertainty, sample distribution or confidence interval. A numerical uncertainty cannot be determined from these excerpts.",
        missing=["measurement uncertainty, sample data or a stated confidence interval for the tabulated copper value"], tags=["table", "missing_measurement_metadata"])
    add("U2", "unanswerable", 10,
        "Use the supplied RC discussion to calculate the exact recharge time in seconds for a particular photographer's camera after 1,000 charge cycles.",
        "The text explains the dependence on resistance, capacitance and battery condition, but does not specify this camera's component values or their condition after 1,000 cycles. Its exact recharge time cannot be calculated.",
        missing=["camera-specific resistance and capacitance after 1,000 cycles", "the numerical recharge criterion or target voltage"], tags=["underdetermined_calculation"])
    add("U3", "unanswerable", 5,
        "Give the exact resistivity of graphene at 20 degrees Celsius from the supplied Table 20.1 excerpts.",
        "Graphene is not listed in the supplied table excerpts. Its exact resistivity cannot be obtained from this corpus; importing an external value would not be source-grounded.",
        missing=["a graphene entry with its resistivity and stated measurement conditions"], tags=["table", "absent_material"])
    add("U4", "unanswerable", 10,
        "Derive a numerical function giving semiconductor resistivity for every dopant concentration and temperature using only the supplied pages.",
        "The text says semiconductor resistivity depends on temperature and impurity type and amount, but does not give a universal concentration-dependent numerical model or its parameters. The requested function is not determined by the supplied evidence.",
        missing=["a specified semiconductor/dopant model", "concentration-dependent parameters and validity ranges"], tags=["unsupported_generalization"])

    document = {"id": DOC_ID, "bundle_id": BUNDLE, "split": "development", "title": "College Physics (first edition), selected electricity pages",
        "source_url": PDF_URL, "book_url": "https://openstax.org/details/books/college-physics", "retrieved_date":"2026-10-31",
        "publisher_metadata_url": "https://openstax.org/apps/cms/api/books/college-physics/",
        "raw_file_sha256": PDF_SHA256, "raw_file_bytes": len(raw_bytes), "raw_pdf_page_count": len(pdf),
        "license": {"identifier":"CC-BY-4.0", "url":"https://creativecommons.org/licenses/by/4.0/", "attribution":ATTRIBUTION,
                    "verification":"PDF copyright page 4 and official publisher CMS both specify CC BY 4.0; this is not the differently licensed second edition."},
        "extraction": {"parser":"PyMuPDF", "version":pymupdf.VersionBind, "policy":"get_text(sort=True); horizontal whitespace folded and lines trimmed; blank runs reduced before annotation; visual transcription explicitly recorded",
                       "ocr":"not_used_born_digital", "known_limitations":"Many formula glyphs and numeric table cells are absent in automatic extraction; the silver/copper rows have an explicit draft visual transcription. No silent OCR/math repair."},
        "topic_ids":list(TOPICS), "topics":[{"id":k,"label":v} for k,v in TOPICS.items()],
        "pages":list(pages.values()), "scope":"Only the listed pages are the pilot corpus. The rest of the source textbook is not available to pilot retrieval. Some topics are excerpted, not complete chapters."}
    return {"schema_version":"documind-educational-pilot-v1", "status":"draft_unreviewed_pilot",
        "created_at":"2026-10-31", "split":"development", "independent_review_status":"pending_two_qualified_reviewers",
        "offset_convention":"Zero-based Unicode code points in canonical page text, end exclusive; immutable canonical_text_sha256.",
        "provenance":"Real openly licensed textbook extracts with AI-assisted question/evidence/rubric drafts. No human grades or independent annotations exist yet.",
        "documents":[document], "questions":questions,
        "coverage_gaps":["One physics bundle only; not the proposed four-subject/24-bundle benchmark.",
                         "No scanned pages or conflicting revisions were found in this selected born-digital corpus; those tags remain unfilled.",
                         "Repeated running headings and page-crossing topics are present; table transcription still needs independent review.",
                         "Categories and difficulty remain proposed; confirm the 256-token window rule with the frozen benchmark tokenizer before final labels.",
                         "Relational questions concern explicit causal relations among electrical concepts, not named-person/company graphs; reviewers must confirm scope."]}


def validate(data: dict) -> dict:
    pages = {p["page"]: p for p in data["documents"][0]["pages"]}
    questions = data["questions"]
    assert len(questions) == len({q["id"] for q in questions}) == 20
    assert Counter(q["category"] for q in questions) == {k:4 for k in ("localized_single_topic","distributed_single_topic","multi_topic_synthesis","relational_multihop","unanswerable")}
    assert Counter(q["designated_marks"] for q in questions) == {5:7,10:7,15:6}
    span_count = 0
    for p in pages.values():
        assert digest(p["canonical_text"].encode()) == p["canonical_text_sha256"]
    for q in questions:
        assert q["status"] == "draft_unreviewed" and len(q["independent_annotation_reviews"]) == 2
        assert all(r["reviewer_id"] is None and r["decision"] is None for r in q["independent_annotation_reviews"])
        assert bool(q["required_evidence_units"]) == (q["answerability"] == "answerable")
        rubric_data = q["rubrics"][str(q["designated_marks"])]
        assert sum(c["max_marks"] for c in rubric_data["criteria"]) == q["designated_marks"]
        for u in q["required_evidence_units"]:
            assert u["alternatives"]
            for alternative in u["alternatives"]:
                assert alternative["all_of"]
                for s in alternative["all_of"]:
                    page = pages[s["page"]];text=page["canonical_text"]
                    assert s["document_id"] == DOC_ID and s["topic_id"] in TOPICS
                    assert 0 <= s["start_char"] < s["end_char"] <= len(text)
                    assert text[s["start_char"]:s["end_char"]] == s["quote"]
                    assert digest(s["quote"].encode()) == s["quote_sha256"]
                    span_count += 1
    return {"status":"format_integrity_pass_not_human_review", "questions":20, "source_pages":len(pages),
            "source_spans":span_count, "categories":dict(Counter(q["category"] for q in questions)),
            "designated_marks":dict(Counter(q["designated_marks"] for q in questions)),
            "independent_reviews_completed":0, "results_measured":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquire",action="store_true",help="Download only the pinned official source PDF")
    parser.add_argument("--check",action="store_true",help="Check existing dataset without PDF/model/network access")
    parser.add_argument("--output",type=Path,default=ROOT/'dataset.json',help="New dataset path; existing outputs are never overwritten")
    args=parser.parse_args()
    if args.check:
        print(json.dumps(validate(json.loads(args.output.read_text(encoding='utf-8'))),indent=2));return
    path=ROOT/'source_cache/college_physics_1e.pdf'
    if args.acquire and not path.exists():
        path.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(PDF_URL,path)
    data=build(path)
    with args.output.open('x',encoding='utf-8') as target:json.dump(data,target,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(validate(data),indent=2))


if __name__ == '__main__':
    main()
