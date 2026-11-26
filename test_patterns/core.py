"""Explicit academy test patterns; no claim of an official question-type quota."""
from collections import defaultdict
from random import SystemRandom
from django.db.models import Count, Q
from question_bank.models import Chapter, Question, Subtopic
from question_bank.chapter_order import CHAPTERS, RANKS, _key, order_chapters
from syllabus_builder.views import ids, bucket, draw

SECTIONS = ("physics", "chemistry", "botany", "zoology")
PCMB_SECTIONS = ("physics", "chemistry", "mathematics", "biology")
LABELS = {"biology": "Biology", "physics": "Physics", "chemistry": "Chemistry", "botany": "Botany", "zoology": "Zoology", "mathematics": "Mathematics"}
PROFILES = {"grand": "NEET Grand Test", "cumulative": "Cumulative Test", "custom180": "Custom 180-question Test", "custom40": "Custom 40-question Test"}
# Suggestions are editable academy conventions, NOT an official NCERT/NTA partition.
JEE_SECTIONS = ("physics", "chemistry", "mathematics")
JEE_COUNTS = {"jee30": 10, "jee45": 15, "jee60": 20, "jee75": 25}
PROFILES.update({"jee30": "JEE Quick Practice", "jee45": "JEE Standard Practice", "jee60": "JEE Intensive Practice", "jee75": "JEE Main MCQ Practice", "jeecumulative": "JEE Cumulative Practice", "jeecustom": "JEE Custom Practice"})
ZOOLOGY = {_key(s) for s in (
    "Animal Kingdom", "Structural Organisation in Animals", "Structural Organization in Animals",
    "Biomolecules", "Breathing and Exchange of Gases", "Body Fluids and Circulation",
    "Excretory Products and Their Elimination", "Locomotion and Movement", "Neural Control and Coordination",
    "Chemical Coordination and Integration", "Human Reproduction", "Reproductive Health", "Evolution", "Human Health and Disease",
)}
rng = SystemRandom()


def subject_for(section):
    return section if section in ("physics", "chemistry", "mathematics") else "biology"


def suggestion(chapter):
    if chapter["subject"] != "biology":
        return chapter["subject"]
    return "zoology" if _key(chapter["name"]) in ZOOLOGY else "botany"


def available_catalog():
    chapters = list(Chapter.objects.annotate(available=Count("subtopic__question", filter=Q(subtopic__question__active=True))).values("id", "subject", "level", "name", "available"))
    chapters = order_chapters(chapters)
    topics = list(Subtopic.objects.filter(question__active=True).annotate(available=Count("question")).values("id", "chapter_id", "name", "available"))
    for ch in chapters:
        ch["suggested_section"] = suggestion(ch)
    return chapters, topics


def missing_chapters(chapters):
    missing = defaultdict(list)
    for (subject, level), names in CHAPTERS.items():
        if subject == "mathematics":
            continue  # NEET readiness must not depend on Mathematics.
        present = {RANKS.get((subject, level), {}).get(_key(c["name"]))
                   for c in chapters if c["subject"] == subject and c["level"] == level and c["available"]}
        for rank, name in enumerate(names, 1):
            if rank not in present:
                missing[subject].append(f"Class {level}: {name}")
    return dict(missing)


def validate_spec(data):
    profile = data.get("profile")
    if profile not in PROFILES:
        raise ValueError("Choose a test pattern.")
    subject = data.get("subject", "all")
    jee = profile in (*JEE_COUNTS, "jeecumulative", "jeecustom")
    exam = data.get("exam")
    if exam not in (None, "jee", "neet"):
        raise ValueError("Unknown examination.")
    if exam == "jee" and not jee:
        raise ValueError("Select a JEE practice pattern.")
    if exam == "neet" and (jee or subject in ("pcmb", "pcm", "mathematics")):
        raise ValueError("NEET uses Physics, Chemistry and Biology only.")
    if jee:
        if subject not in ("all", "pcm"):
            raise ValueError("JEE presets use Physics, Chemistry and Mathematics only.")
        if profile in JEE_COUNTS:
            targets = dict.fromkeys(JEE_SECTIONS, JEE_COUNTS[profile])
        else:
            raw_targets = data.get("targets")
            if not isinstance(raw_targets, dict) or set(raw_targets) != set(JEE_SECTIONS):
                raise ValueError("Enter counts for Physics, Chemistry and Mathematics.")
            if any(type(n) is not int or not 0 <= n <= 300 for n in raw_targets.values()):
                raise ValueError("Use whole question counts from 0 to 300.")
            targets = {k: raw_targets[k] for k in JEE_SECTIONS if raw_targets[k]}
            if not 1 <= sum(targets.values()) <= 300:
                raise ValueError("Choose 1–300 questions in total.")
        total = sum(targets.values())
    else:
        pcmb = profile in ("custom40", "custom180") and subject == "pcmb"
        full = profile in ("grand", "cumulative") or subject in ("all", "pcb", "pcmb")
        if not full and subject not in (*SECTIONS, "mathematics"):
            raise ValueError("Choose a subject for this custom test.")
        total = 40 if profile == "custom40" else 180
        targets = {section: total // 4 for section in (PCMB_SECTIONS if pcmb else SECTIONS)} if full else {subject: total}
    chapters, topics = available_catalog()
    published = {c["id"]: c for c in chapters if c["available"]}
    supplied = data.get("sections", {})
    if not isinstance(supplied, dict):
        raise ValueError("Invalid chapter selection.")
    if exam == "neet" and set(supplied) - set(SECTIONS):
        raise ValueError("NEET does not accept Mathematics or other sections.")
    if jee and set(supplied) - set(JEE_SECTIONS):
        raise ValueError("JEE does not accept Biology or other sections.")
    if not jee and not pcmb and full and supplied.get("mathematics"):
        raise ValueError("Mathematics is not part of the PCB or NEET test. Choose PCMB custom test instead.")
    if profile == "grand":
        missing = missing_chapters(chapters)
        if missing:
            detail = "; ".join(f"{name}: {len(rows)} missing chapter banks" for name, rows in missing.items())
            raise ValueError("The Grand Test is not ready for the full syllabus. " + detail + ". Use a cumulative/custom test for uploaded chapters, or import the missing banks first.")
    selected = {}
    for section in targets:
        raw = supplied.get(section, {})
        if not isinstance(raw, dict):
            raise ValueError("Invalid chapter selection.")
        chapter_ids = ids(raw.get("chapters", []), "chapter", 150)
        if profile == "grand":
            if section in ("physics", "chemistry"):
                chapter_ids = [c["id"] for c in chapters if c["subject"] == section and c["available"]]
            # Biology split remains explicitly confirmed by the teacher.
        if not chapter_ids:
            raise ValueError(f"Select chapters for {LABELS[section]}.")
        for pk in chapter_ids:
            if pk not in published or published[pk]["subject"] != subject_for(section):
                raise ValueError(f"An unavailable or wrong-subject chapter was selected for {LABELS[section]}.")
        all_topics = [t["id"] for t in topics if t["chapter_id"] in chapter_ids]
        if profile in ("grand", "cumulative", "jeecumulative"):
            topic_ids = all_topics
        else:
            topic_ids = ids(raw.get("topics", []), "topic", 2000)
            if not topic_ids or set(topic_ids) - set(all_topics):
                raise ValueError(f"Select valid topics for {LABELS[section]}.")
            chapter_ids = [pk for pk in chapter_ids if any(t["id"] in topic_ids and t["chapter_id"] == pk for t in topics)]
        selected[section] = {"chapters": chapter_ids, "topics": topic_ids}
    if "botany" in selected or "zoology" in selected:
        if data.get("confirm_biology") is not True:
            raise ValueError("Confirm the Botany/Zoology chapter split for this test.")
        bot = set(selected.get("botany", {}).get("chapters", []))
        zoo = set(selected.get("zoology", {}).get("chapters", []))
        if bot & zoo:
            raise ValueError("A Biology chapter cannot belong to both Botany and Zoology in the same test.")
        if profile == "grand":
            all_bio = {c["id"] for c in chapters if c["subject"] == "biology" and c["available"]}
            if bot | zoo != all_bio:
                raise ValueError("The Grand Test must include every Biology chapter in either Botany or Zoology.")
    return {"profile": profile, "total": total, "marks": total * 4, "targets": targets, "sections": selected}


def query_for_section(spec, section):
    scope = spec["sections"][section]
    return Question.objects.filter(active=True, subtopic_id__in=scope["topics"], subtopic__chapter_id__in=scope["chapters"], subtopic__chapter__subject=subject_for(section))


def choose_section(spec, section, exclude=(), count=None):
    """Sample metadata only, seed available formats and cover eligible chapters."""
    target = count if count is not None else spec["targets"][section]
    query = query_for_section(spec, section).exclude(pk__in=exclude)
    pools = defaultdict(list)
    for row in query.order_by().values_list("id", "subtopic__chapter_id", "subtopic_id", "difficulty", "question_kind", "question_visual").iterator(chunk_size=2000):
        pools[(row[1], row[2])].append(row)
    available = sum(map(len, pools.values()))
    if available < target:
        raise ValueError(f"{LABELS[section]} needs {target} questions, but only {available} unused questions match. No other subject will be substituted.")
    for rows in pools.values():
        rng.shuffle(rows)
    picked, used = [], set()
    def take(predicate):
        eligible = [key for key, rows in pools.items() if any(predicate(row) for row in rows)]
        rng.shuffle(eligible)
        for key in eligible:
            rows = pools[key]
            for i in range(len(rows)-1, -1, -1):
                if predicate(rows[i]):
                    item = rows.pop(i);picked.append(item);used.add(item[0]);return item
        return None
    # Use available formats without claiming a fixed official NEET type ratio.
    if target >= 6:
        for kind in ("assertion-reason", "statement", "matching", "diagram", "graph", "mcq"):
            if len(picked) < target:
                take(lambda row, kind=kind: bucket(row[4], row[5]) == kind)
    covered = {row[1] for row in picked}
    chapters = list({row[1] for rows in pools.values() for row in rows} - covered)
    rng.shuffle(chapters)
    for chapter in chapters:
        if len(picked) >= target:
            break
        take(lambda row, chapter=chapter: row[1] == chapter)
    picked.extend(draw(pools, target - len(picked)))
    rng.shuffle(picked)
    return picked


def metadata(rows, section):
    chapters = {c.pk: c for c in Chapter.objects.filter(pk__in={r[1] for r in rows})}
    topics = dict(Subtopic.objects.filter(pk__in={r[2] for r in rows}).values_list("pk", "name"))
    return [{"id": pk, "section": section, "section_label": LABELS[section], "subject": chapters[ch].get_subject_display(),
             "chapter": chapters[ch].name, "chapter_id": ch, "level": chapters[ch].level,
             "subtopic": topics[topic], "topic_id": topic, "difficulty": diff, "kind": kind, "visual": visual}
            for pk, ch, topic, diff, kind, visual in rows]
