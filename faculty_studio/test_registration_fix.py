import json
from io import StringIO
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command,CommandError
from django.db import OperationalError
from faculty_studio.models import Profile

class RegistrationFixTests(TestCase):
    def setUp(self):cache.clear()
    def native(self,data):return self.client.post('/api/mobile/v1/studio-register/',json.dumps(data),content_type='application/json')
    def valid(self):return {'name':'Teacher Test','username':'keyboardteacher','password':'LongFreshPass47!','email':'keyboard@example.com','academy':''}
    def test_native_signup_does_not_need_browser_session_login(self):
        with patch('faculty_studio.views.session_login',side_effect=RuntimeError('No browser session')) as login:
            r=self.native(self.valid())
        self.assertEqual(r.status_code,200,r.content);login.assert_not_called();self.assertIn('token',r.json());self.assertTrue(Profile.objects.filter(user__username='keyboardteacher').exists())
    def test_database_failure_returns_safe_json(self):
        with self.assertLogs('faculty_studio.views',level='ERROR'):
            with patch('faculty_studio.views.Policy.current',side_effect=OperationalError('Missing private table')):r=self.native(self.valid())
        self.assertEqual(r.status_code,503);self.assertEqual(r.json()['code'],'STUDIO_DATABASE_NOT_READY');self.assertNotIn('private',r.content.decode());self.assertFalse(get_user_model().objects.exists())
    def test_failed_profile_write_rolls_back_account(self):
        with self.assertLogs('faculty_studio.views',level='ERROR'):
            with patch('faculty_studio.views.Profile.objects.create',side_effect=OperationalError('Cannot write')):r=self.native(self.valid())
        self.assertEqual(r.status_code,503);self.assertFalse(get_user_model().objects.filter(username='keyboardteacher').exists())
    def test_invalid_details_are_json_not_html(self):
        data=self.valid();data['name']='';r=self.native(data);self.assertEqual(r.status_code,400);self.assertIn('name',r.json()['error']);self.assertFalse(get_user_model().objects.exists())
    def test_unexpected_error_returns_support_reference(self):
        with self.assertLogs('faculty_studio.views',level='ERROR'):
            with patch('faculty_studio.views.Policy.current',side_effect=RuntimeError('Private traceback')):r=self.native(self.valid())
        self.assertEqual(r.status_code,500);self.assertIn('reference',r.json());self.assertNotIn('Private traceback',r.content.decode())
    def test_schema_check_reports_missing_tables(self):
        with patch('faculty_studio.management.commands.studio_healthcheck.connection.introspection.table_names',return_value=[]):
            with self.assertRaisesMessage(CommandError,'migrate'):call_command('studio_healthcheck',stdout=StringIO())
    def test_schema_check_is_read_only(self):
        from faculty_studio.models import Policy
        before=Policy.objects.count();call_command('studio_healthcheck',stdout=StringIO());self.assertEqual(Policy.objects.count(),before)
