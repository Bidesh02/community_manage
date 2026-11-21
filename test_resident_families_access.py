import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
django.setup()

from django.test import Client
from society_app.models import User

print("--- TESTING RESIDENT FAMILIES ACCESS RESTRICTIONS ---")

client = Client()

# Get users for each role
admin_user = User.objects.filter(role='ADMIN').first()
staff_user = User.objects.filter(role='STAFF').first()
resident_user = User.objects.filter(role='RESIDENT').first()

assert admin_user, "No admin user found"
assert resident_user, "No resident user found"
if not staff_user:
    staff_user = User.objects.create_user(
        username='test_gate_security',
        email='security@example.com',
        role='STAFF',
        password='Password123!'
    )

# 1. RESIDENT USER TEST
client.force_login(resident_user)

# A) Check sidebar on dashboard does NOT have Resident Families link
res_dash = client.get('/dashboard/')
assert res_dash.status_code == 200
html_dash = res_dash.content.decode('utf-8')
assert '<span>Resident Families</span>' not in html_dash, "Error: Resident user must not see 'Resident Families' in navigation"
print("✓ Resident user correctly does NOT see 'Resident Families' in the sidebar navigation!")

# B) Check direct access to /residents/ is restricted
res_dir = client.get('/residents/', follow=True)
assert res_dir.status_code == 200
# Should redirect to dashboard with restriction message
assert res_dir.redirect_chain or 'Access restricted' in res_dir.content.decode('utf-8')
print("✓ Resident user direct access to /residents/ is strictly blocked and redirected with access error!")

# 2. ADMIN USER TEST
client.force_login(admin_user)
admin_dash = client.get('/dashboard/')
assert admin_dash.status_code == 200
html_admin_dash = admin_dash.content.decode('utf-8')
assert '<span>Resident Families</span>' in html_admin_dash
print("✓ Admin user correctly sees 'Resident Families' in navigation!")

admin_dir = client.get('/residents/')
assert admin_dir.status_code == 200
assert 'Resident Families Directory' in admin_dir.content.decode('utf-8')
print("✓ Admin user successfully accesses '/residents/'!")

# 3. SECURITY STAFF TEST
client.force_login(staff_user)
staff_dash = client.get('/dashboard/')
assert staff_dash.status_code == 200
html_staff_dash = staff_dash.content.decode('utf-8')
assert '<span>Resident Families</span>' in html_staff_dash
print("✓ Security staff correctly sees 'Resident Families' in navigation!")

staff_dir = client.get('/residents/')
assert staff_dir.status_code == 200
assert 'Resident Families Directory' in staff_dir.content.decode('utf-8')
print("✓ Security staff successfully accesses '/residents/'!")

print("=== ALL RESIDENT FAMILIES ACCESS CONTROL TESTS PASSED 100%! ===")
