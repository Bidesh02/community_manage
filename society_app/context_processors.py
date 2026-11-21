from django.conf import settings


def google_auth_settings(request):
    return {
        'GOOGLE_CLIENT_ID': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
        'google_verified_user': request.session.get('google_user'),
    }
