import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
django.setup()

from django.test import Client
from society_app.models import User, FundCampaign, FundContribution

print("--- TESTING COMMUNITY FUNDS ENHANCEMENTS & MINIMUM CONTRIBUTION RULE ---")

client = Client()
user = User.objects.filter(role='RESIDENT').first()
if not user:
    user = User.objects.filter(is_superuser=True).first()

client.force_login(user)

# 1. Test All Campaigns Tab
r_all = client.get('/funds/?tab=campaigns')
assert r_all.status_code == 200
html_all = r_all.content.decode('utf-8')
assert 'All Campaigns' in html_all
assert 'Who Donated & How Much' in html_all
assert 'My Donations' in html_all
assert 'Min: ₹' in html_all
print("✓ Tab [All Campaigns] loaded with tabs, min contribution badges, and donor preview!")

# 2. Test Who Donated & How Much Tab with Unique Cases (Flat No & Name)
r_donations = client.get('/funds/?tab=donations')
assert r_donations.status_code == 200
html_donations = r_donations.content.decode('utf-8')
assert 'Who Donated & How Much' in html_donations
assert 'Resident Donors (Flat & Name)' in html_donations
assert 'Flat Number' in html_donations
assert 'Resident Name' in html_donations
assert 'Flat A-402' in html_donations or 'A-402' in html_donations
assert 'toggleResident(' in html_donations
assert 'Event Donations for' in html_donations
assert 'Donated To This Event' in html_donations
print("✓ Tab [Who Donated & How Much] loaded with unique resident flat/name cases and event breakdown!")

# 3. Test My Donations Tab
r_my = client.get('/funds/?tab=my_donations')
assert r_my.status_code == 200
html_my = r_my.content.decode('utf-8')
assert 'My Contributions & Donations' in html_my
assert 'Total Donated By You' in html_my
print("✓ Tab [My Donations] loaded with personal summary and history!")

# 4. Test Minimum Contribution Enforcement
# Create or get a test campaign with minimum_amount = 500
campaign, _ = FundCampaign.objects.get_or_create(
    title='Holi Festival 2026',
    defaults={
        'category': 'EVENT',
        'target_amount': Decimal('25000.00'),
        'minimum_amount': Decimal('500.00'),
        'description': 'Annual society festival of colors and sweets.',
        'status': 'ACTIVE',
    }
)
campaign.minimum_amount = Decimal('500.00')
campaign.save()

# Detail view check
r_detail = client.get(f'/funds/{campaign.id}/')
assert r_detail.status_code == 200
html_detail = r_detail.content.decode('utf-8')
assert 'Minimum Required: ₹500.00' in html_detail or 'Minimum Required: ₹500' in html_detail
assert '₹500.00' in html_detail or '₹500' in html_detail
print("✓ Campaign detail page shows Minimum Required: ₹500 and validation rules!")

# Attempt to donate LESS than minimum (e.g. ₹200 when min is ₹500)
count_before = FundContribution.objects.filter(campaign=campaign).count()
r_sub_min = client.post(f'/funds/{campaign.id}/contribute/', {
    'amount': '200.00',
    'payment_method': 'Instant UPI / GPay / PhonePe',
    'note': 'Trying below minimum',
}, follow=True)

count_after_sub_min = FundContribution.objects.filter(campaign=campaign).count()
assert count_after_sub_min == count_before, "Donation below minimum should have been blocked!"
html_sub_min = r_sub_min.content.decode('utf-8')
assert 'Minimum contribution required' in html_sub_min or 'cannot donate' in html_sub_min, f"Expected error message in HTML"
print("✓ Successfully blocked donation below minimum (₹200 < ₹500) with clear resident feedback!")

# Attempt to donate AT OR ABOVE minimum (e.g. ₹1000)
r_valid = client.post(f'/funds/{campaign.id}/contribute/', {
    'amount': '1000.00',
    'payment_method': 'Instant UPI / GPay / PhonePe',
    'note': 'Joyous celebrations!',
}, follow=True)

count_after_valid = FundContribution.objects.filter(campaign=campaign).count()
assert count_after_valid == count_before + 1, "Valid donation should be recorded!"
latest_contrib = FundContribution.objects.filter(campaign=campaign).latest('created_at')
assert latest_contrib.amount == Decimal('1000.00')
assert latest_contrib.contributor == user
print(f"✓ Successfully accepted valid donation (₹1,000 >= ₹500) by {user.username}!")

# Verify it displays on the campaign card, Who Donated tab, and My Donations tab
r_check_my = client.get('/funds/?tab=my_donations')
assert '1000.00' in r_check_my.content.decode('utf-8')
print("✓ Verified donation of ₹1000 appears in [My Donations] tab!")

r_check_ledger = client.get('/funds/?tab=donations')
assert '1000.00' in r_check_ledger.content.decode('utf-8')
print("✓ Verified donation of ₹1000 appears in [Who Donated & How Much] tab!")

print("=== ALL COMMUNITY FUNDS VERIFICATION TESTS PASSED 100%! ===")
