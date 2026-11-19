"""Syllabus-scoped sampling. Existing bank questions and exports stay untouched."""
import json
from collections import defaultdict
from datetime import timedelta
from random import SystemRandom

from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from question_bank.models import Chapter, Question, Subtopic
from question_bank.question_types import QUESTION_TYPES
from .models import CorrectionReport

TYPES = dict(QUESTION_TYPES)
DIFFICULTIES = ("easy", "moderate", "hard")
MAX_QUESTIONS = 300
MAX_IDS = 10000
_rng = SystemRandom()


def error(message, status=400, **extra):
    return JsonResponse({"error": message, **extra}, status=status)


def json_body(request):
    if len(request.body) > 150000:
        raise ValueError("This request is too large. Start a new candidate batch.")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise ValueError("Send valid JSON.") from exc
    if not isinstance(data, dict):
        raise ValueError("Send an object.")
    return data


def ids(value, label, limit):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"Invalid {label} selection.")
    result = []
    for item in value:
        if isinstance(item, str) and item.isascii() and item.isdecimal() and len(item) <= 18:
            item = int(item)
        if type(item) is not int or not 0 < item < 2**63:
            raise ValueError(f"Invalid {label} selection.")
        result.append(item)
    return list(dict.fromkeys(result))


def number(value, label, lower=1, upper=MAX_QUESTIONS):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{label} must be between {lower} and {upper}.")
    return value


def query_for(data):
    subject = data.get("subject")
    difficulty = data.get("difficulty", "")
    kind = data.get("question_type", "")
    if subject not in Chapter.Subject.values or difficulty not in ("", *DIFFICULTIES) or kind not in ("", *TYPES):
        raise ValueError("Choose a valid subject, difficulty and question type.")
    chapters = ids(data.get("chapters", []), "chapter", 150)
    topics = ids(data.get("topics", []), "topic", 2000)
    if not chapters:
        raise ValueError("Select at least one chapter.")
    if Chapter.objects.filter(pk__in=chapters, subject=subject).count() != len(chapters):
        raise ValueError("A chapter does not belong to this subject.")
    if Subtopic.objects.filter(pk__in=topics, chapter_id__in=chapters).count() != len(topics):
        raise ValueError("A topic does not belong to the selected chapters.")
    # An empty topic list means none, never an accidental whole-subject query.
    query = Question.objects.filter(active=True, subtopic_id__in=topics,
                                    subtopic__chapter_id__in=chapters,
                                    subtopic__chapter__subject=subject)
    if difficulty:
        query = query.filter(difficulty=difficulty)
    if kind in ("graph", "diagram"):
        query = query.filter(question_visual=kind)
    elif kind:
        query = query.filter(question_kind=kind)
        if kind == "mcq":
            query = query.filter(question_visual="")
    return query


def bucket_filter(kind):
    if kind in ("graph", "diagram"):
        return Q(question_visual=kind)
    return Q(question_kind=kind) & ~Q(question_visual__in=("graph", "diagram"))


def bucket(kind, visual):
    return visual if visual in ("graph", "diagram") else kind if kind in TYPES else "mcq"


def summary(query):
    counters = query.aggregate(total=Count("pk"), **{
        key.replace("-", "_"): Count("pk", filter=bucket_filter(key)) for key in TYPES
    })
    return {
        "total": counters.pop("total"),
        "buckets": {key: counters[key.replace("-", "_")] for key in TYPES},
        "difficulty": {k: v for k, v in query.order_by().values_list("difficulty").annotate(n=Count("pk"))},
    }


@never_cache
@require_GET
def counts(request):
    try:
        data = {key: request.GET.get(key, "") for key in ("subject", "difficulty", "question_type")}
        data["chapters"] = request.GET.getlist("chapters")
        data["topics"] = request.GET.getlist("topics")
        query = query_for(data)
        result = summary(query)
        untyped = query_for({**data, "question_type": ""})
        result["type_counts"] = {}
        for kind in TYPES:
            rule = Q(question_visual=kind) if kind in ("diagram", "graph") else Q(question_kind=kind)
            if kind == "mcq":
                rule &= Q(question_visual="")
            result["type_counts"][kind] = rule
        facets = untyped.aggregate(all=Count("pk"), **{
            kind.replace("-", "_"): Count("pk", filter=rule)
            for kind, rule in result["type_counts"].items()
        })
        result["type_counts"] = {kind: facets[kind.replace("-", "_")] for kind in TYPES}
        result["scope_total"] = facets["all"]
        result["topics"] = {str(k): v for k, v in query.order_by().values_list("subtopic_id").annotate(n=Count("pk"))}
        return JsonResponse(result)
    except ValueError as exc:
        return error(str(exc))


def draw(pool, count):
    """Rotate chapters, then topics, redistributing automatically if a pool empties."""
    chapters = defaultdict(dict)
    for (chapter, topic), rows in pool.items():
        if rows:
            _rng.shuffle(rows)
            chapters[chapter][topic] = rows
    chapter_order = list(chapters)
    _rng.shuffle(chapter_order)
    topic_order = {chapter: list(chapters[chapter]) for chapter in chapter_order}
    for rows in topic_order.values():
        _rng.shuffle(rows)
    positions = defaultdict(int)
    picked = []
    while chapter_order and len(picked) < count:
        for chapter in chapter_order[:]:
            if len(picked) >= count:
                break
            topics = topic_order[chapter]
            if not topics:
                chapter_order.remove(chapter)
                continue
            index = positions[chapter] % len(topics)
            topic = topics[index]
            rows = chapters[chapter][topic]
            picked.append(rows.pop())
            if not rows:
                topics.pop(index)
            else:
                index += 1
            positions[chapter] = index
    return picked


@never_cache
@require_POST
def sample(request):
    try:
        data = json_body(request)
        count = number(data.get("count"), "Candidate count")
        query = query_for(data)
        excluded = ids(data.get("exclude", []), "excluded question", MAX_IDS)
        if excluded:
            query = query.exclude(pk__in=excluded)
        quotas = data.get("quotas")
        if quotas is not None:
            if not isinstance(quotas, dict) or set(quotas) - set(TYPES):
                raise ValueError("Invalid question-type allocation.")
            quotas = {key: number(quotas.get(key, 0), "Type count", 0) for key in TYPES}
            if sum(quotas.values()) != count:
                raise ValueError("The question-type counts must add up to the candidate count.")
        # Reservoirs keep only small ID/metadata tuples; no diagram blobs or equations
        # are loaded while sampling even for a large multi-chapter bank.
        pools = defaultdict(lambda: defaultdict(list))
        seen = defaultdict(int)
        availability = defaultdict(int)
        fields = ("id", "subtopic__chapter_id", "subtopic_id", "difficulty", "question_kind", "question_visual")
        for row in query.order_by().values_list(*fields).iterator(chunk_size=2000):
            pk, chapter, topic, difficulty, kind, visual = row
            group = bucket(kind, visual) if quotas is not None else "all"
            limit = quotas[group] if quotas is not None else count
            availability[group] += 1
            if not limit:
                continue
            key = (group, chapter, topic)
            seen[key] += 1
            reservoir = pools[group][(chapter, topic)]
            if len(reservoir) < limit:
                reservoir.append(row)
            else:
                at = _rng.randrange(seen[key])
                if at < limit:
                    reservoir[at] = row
        needed = quotas if quotas is not None else {"all": count}
        shortages = {key: {"requested": n, "available": availability[key]}
                     for key, n in needed.items() if availability[key] < n}
        if shortages:
            return error("Not enough unused questions match this selection. Reduce the count or widen the syllabus.",
                         status=409, shortages=shortages)
        picked = []
        for group, n in needed.items():
            picked.extend(draw(pools[group], n))
        _rng.shuffle(picked)
        chapter_ids = {row[1] for row in picked}
        topic_ids = {row[2] for row in picked}
        chapter_map = {x.pk: x for x in Chapter.objects.filter(pk__in=chapter_ids)}
        topic_map = dict(Subtopic.objects.filter(pk__in=topic_ids).values_list("id", "name"))
        questions = []
        for pk, chapter, topic, difficulty, kind, visual in picked:
            ch = chapter_map[chapter]
            questions.append({"id": pk, "subject": ch.get_subject_display(), "chapter": ch.name,
                              "chapter_id": chapter, "level": ch.level, "subtopic": topic_map[topic],
                              "topic_id": topic, "difficulty": difficulty, "kind": kind, "visual": visual})
        return JsonResponse({"questions": questions, "count": len(questions)})
    except ValueError as exc:
        return error(str(exc))


def serialize(row):
    from paper_builder.views import inline_preview
    return {"id": row.pk, "subject": row.subtopic.chapter.get_subject_display(),
            "chapter": row.subtopic.chapter.name, "level": row.subtopic.chapter.level,
            "subtopic": row.subtopic.name, "difficulty": row.difficulty,
            "kind": row.question_kind, "visual": row.question_visual,
            "answer": row.correct_option, "preview": inline_preview(row.structured),
            "image": reverse("question-asset", args=[row.pk, "question"]),
            "hint": reverse("question-asset", args=[row.pk, "hint"]) if row.hint or row.structured else None}


@never_cache
@require_GET
def details(request):
    try:
        wanted = ids(request.GET.getlist("ids"), "question", 12)
        if not wanted:
            raise ValueError("Choose questions to preview.")
        rows = Question.objects.filter(pk__in=wanted, active=True).select_related("subtopic__chapter").in_bulk()
        questions, failed = [], []
        for pk in wanted:
            if pk not in rows:
                failed.append({"id": pk, "error": "This question is no longer published."})
                continue
            try:
                questions.append(serialize(rows[pk]))
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                failed.append({"id": pk, "error": "The preview could not render. Please report this question."})
        return JsonResponse({"questions": questions, "failed": failed})
    except ValueError as exc:
        return error(str(exc))


@never_cache
@require_POST
def report(request):
    try:
        data = json_body(request)
        question_id = number(data.get("question_id"), "Question ID", 1, 2**63 - 1)
        category = data.get("category")
        if category not in dict(CorrectionReport._meta.get_field("category").choices):
            raise ValueError("Select what needs correction.")
        note = data.get("note")
        if not isinstance(note, str) or not 10 <= len(note.strip()) <= 2000:
            raise ValueError("Describe the correction in 10–2,000 characters.")
        row = get_object_or_404(Question.objects.select_related("subtopic__chapter"), pk=question_id, active=True)
        if not request.session.session_key:
            request.session.create()
        key = salted_hmac("ojas.correction-report", request.session.session_key).hexdigest()
        recent = CorrectionReport.objects.filter(session_key=key, created_at__gte=timezone.now() - timedelta(hours=1))
        if recent.count() >= 20:
            return error("You have sent 20 reports this hour. Please try again later.", 429)
        duplicate = recent.filter(question=row, category=category, note=note.strip()).first()
        if duplicate:
            return JsonResponse({"id": duplicate.pk, "message": "This correction has already been recorded."})
        content = row.structured if isinstance(row.structured, dict) else {}
        options = content.get("options", [])
        options = options if isinstance(options, list) else []
        snapshot = {"subject": row.subtopic.chapter.get_subject_display(), "chapter": row.subtopic.chapter.name,
                    "subtopic": row.subtopic.name, "answer": row.correct_option,
                    "stem": str(content.get("stem", ""))[:20000],
                    "options": [str(option)[:5000] for option in options[:4]], "hint": str(content.get("hint", ""))[:20000]}
        item = CorrectionReport.objects.create(question=row, category=category, note=note.strip(), snapshot=snapshot,
                                               session_key=key, reporter=request.user if request.user.is_authenticated else None)
        return JsonResponse({"id": item.pk, "message": "Correction sent for review. The bank question has not been changed."}, status=201)
    except ValueError as exc:
        return error(str(exc))
