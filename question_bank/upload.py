from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.shortcuts import render

from .models import Chapter, Question
from .pdf_import import MAX_BYTES


class ImportForm(forms.Form):
    questions = forms.FileField(label="Question PDF")
    answers = forms.FileField(label="Answer key PDF")
    count = forms.IntegerField(min_value=1, max_value=300)
    subject = forms.ChoiceField(choices=Chapter.Subject.choices)
    level = forms.TypedChoiceField(choices=[(11, "Class 11"), (12, "Class 12")], coerce=int)
    chapter = forms.CharField(max_length=150)
    subtopic = forms.CharField(max_length=150)
    difficulty = forms.ChoiceField(choices=Question.Difficulty.choices)
    publish = forms.BooleanField(required=False, label="Activate questions that pass the option check")

    def clean(self):
        data = super().clean()
        for name in ("questions", "answers"):
            uploaded = data.get(name)
            if uploaded and uploaded.size > MAX_BYTES:
                self.add_error(name, "Each PDF must be 25 MB or smaller.")
        return data


def import_questions(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    form = ImportForm(request.POST, request.FILES) if request.method == "POST" else ImportForm()
    output = StringIO()
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        try:
            with TemporaryDirectory() as directory:
                paths = []
                for name in ("questions", "answers"):
                    path = Path(directory) / f"{name}.pdf"
                    with path.open("wb") as destination:
                        for chunk in data.pop(name).chunks():
                            destination.write(chunk)
                    paths.append(str(path))
                call_command("import_paper", *paths, stdout=output, **data)
        except CommandError as exc:
            form.add_error(None, str(exc))
    return render(request, "admin/question_bank/import.html", {
        **admin.site.each_context(request), "title": "Import question PDFs",
        "form": form, "output": output.getvalue(),
    })
