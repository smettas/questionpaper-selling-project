from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime
from .models import Paper,Wallet,Ledger
class PaperLibraryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('library-teacher',password='LongPassword123!');self.other=get_user_model().objects.create_user('other-teacher');self.wallet=Wallet.objects.create(user=self.user);self.other_wallet=Wallet.objects.create(user=self.other);self.client.force_login(self.user)
        self.paper=Paper.objects.create(owner=self.user,wallet=self.wallet,fingerprint='one',title='November Chemistry',count=40,charged=40,files=[{'private':'storage-ref'}]);Paper.objects.filter(pk=self.paper.pk).update(created_at=timezone.make_aware(datetime(2026,11,10,12)))
        self.old=Paper.objects.create(owner=self.user,wallet=self.wallet,fingerprint='old',title='October Biology',count=40,charged=40,files=[]);Paper.objects.filter(pk=self.old.pk).update(created_at=timezone.make_aware(datetime(2026,10,10,12)))
        Paper.objects.create(owner=self.other,wallet=self.other_wallet,fingerprint='private',title='Private paper',count=40,charged=40,files=[])
    def get(self,**query):return self.client.get('/studio/api/papers/',query)
    def test_month_and_ownership(self):
        r=self.get(month='2026-11');self.assertEqual(r.status_code,200);self.assertEqual(r.json()['count'],1);self.assertEqual(r.json()['papers'][0]['id'],self.paper.pk);self.assertNotIn('files',r.json()['papers'][0]);self.assertEqual(Ledger.objects.count(),0)
    def test_all_dates_search_and_older_month(self):
        self.assertEqual(self.get().json()['count'],2);self.assertEqual(self.get(month='2026-10').json()['papers'][0]['id'],self.old.pk);self.assertEqual(self.get(search='CHEMISTRY').json()['count'],1)
    def test_pagination_beyond_dashboard_limit(self):
        for i in range(45):Paper.objects.create(owner=self.user,wallet=self.wallet,fingerprint='extra'+str(i),title='Extra '+str(i),count=1,charged=1,files=[])
        r=self.get(page=2).json();self.assertEqual(r['count'],47);self.assertEqual(r['pages'],3);self.assertEqual(len(r['papers']),20);self.assertEqual(self.get(page=3).json()['page'],3)
    def test_reject_invalid_filters_and_anonymous(self):
        for q in [{'month':'2026-99'},{'month':'bad'},{'page':'0'},{'page':'bad'},{'search':'a'*121}]:self.assertEqual(self.get(**q).status_code,400)
        self.client.logout();self.assertEqual(self.get().status_code,401)
