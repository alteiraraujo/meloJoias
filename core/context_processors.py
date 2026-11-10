from django.conf import settings
from django.utils import timezone

def app_context(request):
    return {'date_today': timezone.localdate(), 'demo_mode': getattr(settings, 'DEMO_MODE', False)}
