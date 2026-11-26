import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from question_bank.models import Chapter, Question, Subtopic
from .models import CorrectionReport


class SyllabusWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Chapter.objects.create(subject="physics", level=11, name="Test Chapter One")
        cls.b = Chapter.objects.create(subject="physics", level=11, name="Test Chapter Two")
        cls.c = Chapter.objects.create(subject="chemistry", level=11, name="Other Subject")
        cls.t1 = Subtopic.objects.create(chapter=cls.a, name="Topic A")
        cls.t2 = Subtopic.objects.create(chapter=cls.a, name="Topic B")
        cls.t3 = Subtopic.objects.create(chapter=cls.b, name="Topic C")
        cls.other = Subtopic.objects.create(chapter=cls.c, name="Other Topic")
        cls.rows = []
        for topic, amount in ((cls.t1, 30), (cls.t2, 9), (cls.t3, 21)):
            for i in range(amount):
                kinds = ["mcq", "matching", "statement", "assertion-reason", "mcq", "matching"]
                visuals = ["", "", "", "", "graph", "diagram"]
                kind, visual = kinds[i % 6], visuals[i % 6]
                row = Question.objects.create(subtopic=topic, difficulty=["easy", "moderate", "hard"][i % 3],
                    correct_option=2, fingerprint=f"{topic.id}-{i}", question_kind=kind, question_visual=visual,
                    structured={}, active=True)
                cls.rows.append(row)
        cls.hidden = Question.objects.create(subtopic=cls.t1, difficulty="easy", correct_option=1,
                                             fingerprint="hidden", active=False)
        cls.foreign = Question.objects.create(subtopic=cls.other, difficulty="easy", correct_option=1,
                                              fingerprint="foreign")
        cls.scope = {"subject": "physics", "chapters": [cls.a.id, cls.b.id],
                     "topics": [cls.t1.id, cls.t2.id, cls.t3.id], "difficulty": "", "question_type": ""}

    def setUp(self):
        self.user = get_user_model().objects.create_user("syllabus-test-user")
        self.client.force_login(self.user)

    def test_anonymous_requests_are_rejected(self):
        self.assertEqual(Client().get(reverse("syllabus_builder:counts")).status_code, 401)

    def post(self, endpoint, **data):
        return self.client.post(reverse(f"syllabus_builder:{endpoint}"), json.dumps(data), content_type="application/json")

    def sample(self, **overrides):
        return self.post("sample", **{**self.scope, "count": 12, **overrides})

    def counts(self, **overrides):
        return self.client.get(reverse("syllabus_builder:counts"), {**self.scope, **overrides})

    def test_counts_are_unique_and_bucket_totals_add_up(self):
        data = self.counts().json()
        self.assertEqual(data["total"], 60)
        self.assertEqual(sum(data["buckets"].values()), 60)
        self.assertEqual(sum(data["difficulty"].values()), 60)
        self.assertEqual(sum(data["topics"].values()), 60)
        self.assertEqual(data["buckets"]["diagram"], 9)

    def test_topic_exclusion_and_chapter_boundaries(self):
        self.assertEqual(self.counts(topics=[self.t1.id])["Content-Type"], "application/json")
        self.assertEqual(self.counts(topics=[self.t1.id]).json()["total"], 30)
        self.assertEqual(self.counts(topics=[]).json()["total"], 0)
        self.assertEqual(self.counts(chapters=[]).status_code, 400)
        self.assertEqual(self.counts(topics=[self.other.id]).status_code, 400)
        self.assertEqual(self.counts(chapters=[self.c.id]).status_code, 400)
        self.assertEqual(self.counts(chapters=[self.a.id], topics=[self.t3.id]).status_code, 400)

    def test_type_and_difficulty_filters(self):
        diagrams = self.counts(question_type="diagram").json()
        matches = self.counts(question_type="matching").json()
        standard = self.counts(question_type="mcq").json()
        self.assertEqual(diagrams["total"], 9)
        self.assertEqual(matches["total"], 20)
        self.assertEqual(matches["buckets"]["diagram"], 9)
        self.assertEqual(standard["buckets"]["diagram"], 0)
        self.assertEqual(self.counts(difficulty="easy").json()["total"], 20)
        self.assertEqual(self.counts(question_type="injected").status_code, 400)

    def test_random_candidates_are_unique_published_and_excluded(self):
        excluded = [row.pk for row in self.rows[:10]]
        response = self.sample(exclude=excluded)
        self.assertEqual(response.status_code, 200)
        result = response.json()["questions"]
        self.assertEqual(len(result), 12)
        selected = {row["id"] for row in result}
        self.assertEqual(len(selected), 12)
        self.assertFalse(selected.intersection(excluded))
        self.assertNotIn(self.hidden.pk, selected)
        self.assertNotIn(self.foreign.pk, selected)
        self.assertNotIn("preview", result[0])  # no expensive blobs in sample response
        second = self.sample().json()["questions"]
        self.assertNotEqual([r["id"] for r in result], [r["id"] for r in second])

    def test_chapter_then_topic_spread_and_redistribution(self):
        result = self.sample().json()["questions"]
        self.assertEqual(sum(r["chapter_id"] == self.a.id for r in result), 6)
        self.assertEqual(sum(r["chapter_id"] == self.b.id for r in result), 6)
        self.assertEqual(sum(r["topic_id"] == self.t1.id for r in result), 3)
        self.assertEqual(sum(r["topic_id"] == self.t2.id for r in result), 3)
        all_rows = self.sample(count=60).json()["questions"]
        self.assertEqual(len({r["id"] for r in all_rows}), 60)

    def test_exact_nonoverlapping_type_allocation(self):
        quotas = {"mcq": 2, "matching": 2, "assertion-reason": 2, "statement": 2, "diagram": 2, "graph": 2}
        rows = self.sample(quotas=quotas).json()["questions"]
        actual = {}
        for row in rows:
            key = row["visual"] or row["kind"]
            actual[key] = actual.get(key, 0) + 1
        self.assertEqual(actual, quotas)
        self.assertEqual(self.sample(quotas={"mcq": 2}).status_code, 400)
        self.assertEqual(self.sample(quotas={"unknown": 12}).status_code, 400)

    def test_shortage_is_explicit_and_does_not_pad(self):
        response = self.sample(count=61)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["shortages"]["all"], {"requested": 61, "available": 60})
        response = self.sample(quotas={"diagram": 12})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["shortages"]["diagram"]["available"], 9)
        self.assertEqual(self.sample(exclude=[q.id for q in self.rows]).status_code, 409)

    def test_inputs_are_bounded(self):
        for count in (True, 0, 301, "12", -1):
            self.assertEqual(self.sample(count=count).status_code, 400)
        for chapters in ([True], ["bad"], [2**63], "1", [1]*151):
            self.assertEqual(self.sample(chapters=chapters).status_code, 400)
        self.assertEqual(self.sample(exclude=list(range(1, 10002))).status_code, 400)
        self.assertEqual(self.client.post(reverse("syllabus_builder:sample"), '[]', content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(reverse("syllabus_builder:sample")).status_code, 405)
        self.assertEqual(self.client.post(reverse("syllabus_builder:counts")).status_code, 405)

    def test_detail_batch_keeps_requested_order_and_hides_inactive(self):
        row = self.rows[0]
        row.structured = {"stem": "Find \\(\\sqrt{26}\\) m.", "options": ["1", "2", "3", "4"], "hint": "Take the root.", "diagrams": []}
        row.save()
        wanted = [self.rows[1].id, self.hidden.id, row.id]
        response = self.client.get(reverse("syllabus_builder:details"), {"ids": wanted})
        data = response.json()
        self.assertEqual([q["id"] for q in data["questions"]], [wanted[0], wanted[2]])
        self.assertEqual(data["failed"][0]["id"], self.hidden.id)
        self.assertIn("math", [t[0] for t in data["questions"][1]["preview"]["stem"]])
        self.assertEqual(self.client.get(reverse("syllabus_builder:details"), {"ids": [row.id]*13}).status_code, 400)
        self.assertEqual(response["Cache-Control"].split(",")[0], "max-age=0")

    def test_correction_report_is_review_only_and_deduplicates(self):
        row = self.rows[0]
        original = (row.correct_option, row.structured, row.active)
        data = {"question_id": row.id, "category": "answer", "note": "Please check this answer against the printed units."}
        response = self.post("report", **data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post("report", **data).json()["id"], response.json()["id"])
        self.assertEqual(CorrectionReport.objects.count(), 1)
        report = CorrectionReport.objects.get()
        self.assertEqual(report.snapshot["answer"], 2)
        self.assertEqual(report.status, "open")
        row.refresh_from_db()
        self.assertEqual((row.correct_option, row.structured, row.active), original)
        row.correct_option = 3
        row.save()
        report.refresh_from_db()
        self.assertEqual(report.snapshot["answer"], 2)

    def test_report_validation_and_rate_limit(self):
        data = {"question_id": self.rows[0].id, "category": "answer", "note": "Check this answer please."}
        self.assertEqual(self.post("report", **{**data, "note": "bad"}).status_code, 400)
        self.assertEqual(self.post("report", **{**data, "category": "invalid"}).status_code, 400)
        self.assertEqual(self.post("report", **{**data, "question_id": self.hidden.id}).status_code, 404)
        for i in range(20):
            self.assertEqual(self.post("report", **{**data, "note": f"Please check answer in case {i}."}).status_code, 201)
        self.assertEqual(self.post("report", **data).status_code, 429)

    def test_write_endpoints_require_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for endpoint, body in (("sample", {**self.scope, "count": 1}), ("report", {"question_id": self.rows[0].id, "category": "answer", "note": "Please verify the answer."})):
            self.assertEqual(strict.post(reverse(f"syllabus_builder:{endpoint}"), json.dumps(body), content_type="application/json").status_code, 403)

    def test_classification_follows_admin_and_partial_structured_edits(self):
        row = self.rows[0]
        row.structured = {"stem": "Assertion (A): A.\nReason (R): B.", "options": [], "hint": "", "diagrams": []}
        row.save(update_fields=["structured"])
        row.refresh_from_db()
        self.assertEqual(row.question_kind, "assertion-reason")
        row.structured["stem"] = "Statement I: A.\nStatement II: B."
        row.save()
        row.refresh_from_db()
        self.assertEqual(row.question_kind, "statement")

    def test_admin_reports_restricted_to_staff(self):
        report = CorrectionReport.objects.create(question=self.rows[0], category="answer", note="Check the answer", session_key="test")
        url = reverse("admin:syllabus_builder_correctionreport_change", args=[report.id])
        self.assertEqual(self.client.get(url).status_code, 302)
        admin = get_user_model().objects.create_superuser("tester", "test@example.com", "secret-for-tests")
        self.client.force_login(admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open question")

    def test_only_new_report_table_has_migrations(self):
        from django.db import connection
        self.assertIn("syllabus_builder_correctionreport", connection.introspection.table_names())
