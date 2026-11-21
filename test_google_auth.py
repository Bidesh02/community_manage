import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
django.setup()

from django.test import Client
from society_app.models import User

def test_google_registration_gate():
    print("=" * 60)
    print("TESTING GOOGLE AUTHENTICATION & REGISTRATION ENFORCEMENT")
    print("=" * 60)

    client = Client()

    # 1. Access /register/ without Google auth
    print("\n[Step 1] Visiting /register/ without Google authentication...")
    res = client.get('/register/')
    assert res.status_code == 200
    content = res.content.decode()
    assert "Resident Identity Verification" in content
    assert "Sign In with Active Google Account" in content
    assert "Step 1" in content or "Google Verification" in content
    print("  -> PASSED: Mandatory Google Verification screen displayed.")

    # 2. Attempt to bypass Step 1 with a direct POST
    print("\n[Step 2] Attempting unauthorized POST directly to /register/...")
    res = client.post('/register/', {
        'username': 'attacker',
        'email': 'hacker@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'role': 'RESIDENT',
        'flat_number': 'Z-999'
    }, follow=True)
    assert not User.objects.filter(username='attacker').exists()
    content = res.content.decode()
    assert "Resident Identity Verification" in content or "Access Denied" in content
    print("  -> PASSED: Direct registration blocked without active Google account.")

    # 3. Simulate Google Sign-In verification for a new resident
    print("\n[Step 3] Authenticating with active Google account (priya.sharma@gmail.com)...")
    res = client.post('/auth/google/verify/', json.dumps({
        'action': 'register',
        'simulate': True,
        'google_email': 'priya.sharma@gmail.com',
        'google_name': 'Priya Sharma'
    }), content_type='application/json')
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'success'
    print(f"  -> PASSED: Google account verified: {data['message']}")

    # 4. Visit /register/ with verified Google account in session
    print("\n[Step 4] Visiting /register/ after Google verification...")
    res = client.get('/register/')
    assert res.status_code == 200
    content = res.content.decode()
    assert "Google Account Verified" in content or "Google Verified" in content
    assert "priya.sharma@gmail.com" in content
    assert "Complete Society Registration" in content
    print("  -> PASSED: Step 2 unlocked with verified Google identity and pre-filled email.")

    # 5. Complete resident registration
    print("\n[Step 5] Submitting resident enrollment form...")
    # Clean up prior test user if exists
    User.objects.filter(username='priya_sharma').delete()
    User.objects.filter(email='priya.sharma@gmail.com').delete()

    res = client.post('/register/', {
        'username': 'priya_sharma',
        'first_name': 'Priya',
        'last_name': 'Sharma',
        'role': 'RESIDENT',
        'phone_number': '+91 98765 43210',
        'flat_number': 'C-304',
        'block_tower': 'Tower 3',
        'family_members_count': 2,
        'family_details': 'Priya Sharma (Head, Age 32)\nRahul Sharma (Spouse, Age 34)',
        'vehicle_number': 'KA-05-PS-2024',
        'password': 'PriyaPassword123@',
        'confirm_password': 'PriyaPassword123@'
    }, follow=True)

    assert res.status_code == 200
    user = User.objects.filter(username='priya_sharma').first()
    assert user is not None, "User priya_sharma was not created"
    assert user.email == 'priya.sharma@gmail.com'
    assert user.is_google_verified is True
    assert user.google_id is not None
    print(f"  -> PASSED: User created: {user.username} ({user.email}), Google Verified: {user.is_google_verified}")

    # 6. Verify Google Direct Sign-In on login page
    print("\n[Step 6] Testing Google Direct Sign-In for registered resident...")
    client.logout()
    res = client.post('/auth/google/verify/', json.dumps({
        'action': 'login',
        'simulate': True,
        'google_email': 'priya.sharma@gmail.com',
        'google_name': 'Priya Sharma'
    }), content_type='application/json')
    assert res.status_code == 200
    login_data = res.json()
    assert login_data['status'] == 'success'
    print("  -> PASSED: Google direct login successful.")

    # Clean up test user
    user.delete()
    print("\n[Cleanup] Test resident priya_sharma safely removed.")

    print("\n" + "=" * 60)
    print("ALL GOOGLE AUTHENTICATION TESTS PASSED 100%!")
    print("=" * 60)

if __name__ == '__main__':
    test_google_registration_gate()
