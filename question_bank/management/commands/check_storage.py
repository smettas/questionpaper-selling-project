from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Verify database connectivity and media storage write, read, and delete."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        payload = b"question-paper-storage-check"
        key = default_storage.save(f"checks/{uuid4().hex}.txt", ContentFile(payload))
        try:
            with default_storage.open(key, "rb") as asset:
                if asset.read() != payload:
                    raise CommandError("Storage returned unexpected content.")
        finally:
            default_storage.delete(key)
        self.stdout.write(self.style.SUCCESS(f"{connection.vendor} and {type(default_storage).__name__}: OK"))
