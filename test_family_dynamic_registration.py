import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
django.setup()

from django.test import Client
from society_app.models import User
from society_app.forms import ResidentRegistrationForm

print("--- TESTING DYNAMIC FAMILY REGISTRATION (NAME & AGE SECTIONS) ---")

# Test 1: ResidentRegistrationForm with 2 dynamic family members
form_data_2 = {
    'username': 'family_test_user_2',
    'email': 'fam2@example.com',
    'first_name': 'Frank',
    'last_name': 'Castle',
    'role': 'RESIDENT',
    'phone_number': '9876501234',
    'flat_number': 'C-101',
    'block_tower': 'Tower 2',
    'family_members_count': 2,
    'member_name_1': 'Frank Castle',
    'member_age_1': '38',
    'member_name_2': 'Maria Castle',
    'member_age_2': '36',
    'password': 'StrongPassword123!',
    'confirm_password': 'StrongPassword123!',
    'lives_here': 'yes',
}

# Clean any previous test user
User.objects.filter(username__in=['family_test_user_2', 'family_test_user_3']).delete()

form = ResidentRegistrationForm(data=form_data_2)
assert form.is_valid(), f"Form errors: {form.errors}"
cleaned = form.cleaned_data
assert cleaned['family_members_count'] == 2
assert "Frank Castle - Age 38" in cleaned['family_details']
assert "Maria Castle - Age 36" in cleaned['family_details']
user_saved = form.save()
assert user_saved.family_members_count == 2
assert "Frank Castle - Age 38" in user_saved.family_details
assert "Maria Castle - Age 36" in user_saved.family_details
print("✓ Successfully validated and saved 2 dynamic family members (Name & Age) to User model!")

# Test 2: Incomplete dynamic member inputs (e.g. Member 2 missing age)
form_data_incomplete = {
    'username': 'family_test_user_bad',
    'email': 'fambad@example.com',
    'first_name': 'Bad',
    'last_name': 'Data',
    'role': 'RESIDENT',
    'phone_number': '9876509999',
    'flat_number': 'C-102',
    'block_tower': 'Tower 2',
    'family_members_count': 2,
    'member_name_1': 'Good Member',
    'member_age_1': '40',
    'member_name_2': 'Incomplete Member',
    # member_age_2 is missing!
    'password': 'StrongPassword123!',
    'confirm_password': 'StrongPassword123!',
    'lives_here': 'yes',
}
bad_form = ResidentRegistrationForm(data=form_data_incomplete)
assert not bad_form.is_valid()
assert 'family_details' in bad_form.errors
print("✓ Incomplete dynamic member fields correctly blocked with validation message:", bad_form.errors['family_details'])

# Test 3: Form with 3 dynamic family members
form_data_3 = {
    'username': 'family_test_user_3',
    'email': 'fam3@example.com',
    'first_name': 'Bruce',
    'last_name': 'Wayne',
    'role': 'RESIDENT',
    'phone_number': '9876505678',
    'flat_number': 'C-103',
    'block_tower': 'Tower 3',
    'family_members_count': 3,
    'member_name_1': 'Bruce Wayne',
    'member_age_1': '35',
    'member_name_2': 'Alfred Pennyworth',
    'member_age_2': '65',
    'member_name_3': 'Dick Grayson',
    'member_age_3': '18',
    'password': 'StrongPassword123!',
    'confirm_password': 'StrongPassword123!',
    'lives_here': 'yes',
}
form3 = ResidentRegistrationForm(data=form_data_3)
assert form3.is_valid(), f"Form errors: {form3.errors}"
u3 = form3.save()
assert u3.family_members_count == 3
assert "Bruce Wayne - Age 35" in u3.family_details
assert "Alfred Pennyworth - Age 65" in u3.family_details
assert "Dick Grayson - Age 18" in u3.family_details
print("✓ Successfully validated and saved 3 dynamic family members (Name & Age) to User model!")

# Test 4: Verify template markup contains dynamic member sections
client = Client()
# Set session with verified google user to test Step 2 template
session = client.session
session['google_user'] = {
    'email': 'testgoogle@example.com',
    'name': 'Google Resident',
    'given_name': 'Google',
    'family_name': 'Resident',
    'google_id': '1234567890',
}
session.save()

res = client.get('/register/')
assert res.status_code == 200
html = res.content.decode('utf-8')
assert 'family-members-dynamic-list' in html
assert 'renderFamilyMemberInputs' in html
assert 'Family Number' in html
assert 'Family Members Details' in html
print("✓ Registration template correctly renders dynamic family container and JavaScript generator!")

# Clean up test users
User.objects.filter(username__in=['family_test_user_2', 'family_test_user_3']).delete()

print("=== ALL DYNAMIC FAMILY REGISTRATION TESTS PASSED 100%! ===")
