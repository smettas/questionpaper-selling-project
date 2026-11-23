from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from faculty_studio.core import award_welcome
class Command(BaseCommand):
    help='Give one-time welcome credits to a specified existing account; safe to rerun.'
    def add_arguments(self,parser):parser.add_argument('--username',required=True)
    def handle(self,*args,**options):
        try:user=get_user_model().objects.get(username=options['username'])
        except get_user_model().DoesNotExist:raise CommandError('User not found.')
        try:created=award_welcome(user)
        except ValueError as e:raise CommandError(str(e))
        self.stdout.write('Welcome credits added.' if created else 'Welcome credits already awarded; no changes.')
