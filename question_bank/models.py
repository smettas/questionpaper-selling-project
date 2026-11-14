from django.db import models


class Chapter(models.Model):
    class Subject(models.TextChoices):
        PHYSICS = "physics", "Physics"
        CHEMISTRY = "chemistry", "Chemistry"
        BIOLOGY = "biology", "Biology"

    subject = models.CharField(max_length=10, choices=Subject.choices)
    level = models.PositiveSmallIntegerField(choices=[(11, "Class 11"), (12, "Class 12")])
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["subject", "level", "name"]
        unique_together = [("subject", "level", "name")]

    def __str__(self):
        return f"{self.get_subject_display()} · Class {self.level} · {self.name}"


class Subtopic(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["name"]
        unique_together = [("chapter", "name")]

    def __str__(self):
        return self.name


class Question(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MODERATE = "moderate", "Moderate"
        HARD = "hard", "Hard"

    subtopic = models.ForeignKey(Subtopic, on_delete=models.PROTECT)
    difficulty = models.CharField(max_length=8, choices=Difficulty.choices)
    correct_option = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 5)])
    artwork = models.ImageField(upload_to="questions/")
    hint = models.ImageField(upload_to="hints/", blank=True)
    structured = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=64, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"Question {self.pk} · {self.subtopic}"
