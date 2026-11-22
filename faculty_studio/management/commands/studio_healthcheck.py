from django.core.management.base import BaseCommand,CommandError
from django.db import connection
from faculty_studio.models import Policy,Profile,Wallet,Grant,Ledger,Pattern,Draft,Paper,Practice,Recharge,RewardedQuestion,Promotion

class Command(BaseCommand):
    help='Read-only faculty studio schema and registration readiness check. Does not create users or credits.'
    def handle(self,*args,**kwargs):
        tables=set(connection.introspection.table_names())
        missing=[m._meta.db_table for m in [Policy,Profile,Wallet,Grant,Ledger,Pattern,Draft,Paper,Practice,Recharge,RewardedQuestion,Promotion] if m._meta.db_table not in tables]
        if missing:raise CommandError('Missing studio tables: '+', '.join(missing)+'. Run: python manage.py migrate --noinput')
        Policy.objects.first();Profile.objects.first()
        self.stdout.write(self.style.SUCCESS('Studio tables are present. Policy/profile reads passed. No user or credit writes performed.'))
