import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "society_core.settings")
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
c = Client()
u = User.objects.filter(role="RESIDENT").first()
if not u:
    u = User.objects.create_user(username="test_resident", password="password123", role="RESIDENT", flat_number="B-208")

c.force_login(u)
resp = c.get("/")
print("Dashboard status:", resp.status_code)
assert resp.status_code == 200
print("User authenticated:", u.username)
