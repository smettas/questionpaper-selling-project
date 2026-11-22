from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

class AccountGate(MiddlewareMixin):
    def process_request(self,request):
        # Native endpoints have bearer authentication; Django admin retains its own gate.
        public=('/admin/','/api/mobile/v1/','/static/','/health/')
        if request.path.startswith(public):return
        if request.path in ('/studio/','/studio/api/login/','/studio/api/register/'):return
        if not request.user.is_authenticated:
            if request.path=='/' :return redirect('/studio/')
            return JsonResponse({'error':'Please sign in.'},status=401)
