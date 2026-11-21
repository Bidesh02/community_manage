import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
django.setup()

from django.test import Client
from django.utils import timezone
from society_app.models import User, VisitorLog

print("--- TESTING VISITOR PASSES (TODAY'S PASSES & PREVIOUS PASSES) ---")

client = Client()
user = User.objects.filter(role='ADMIN').first()
if not user:
    user = User.objects.filter(is_superuser=True).first()

client.force_login(user)

today = timezone.now().date()

# Ensure we have at least one today pass and one previous pass
# 1. Today pass
v_today, _ = VisitorLog.objects.get_or_create(
    visitor_name="Vikram Courier Express",
    defaults={
        'phone_number': '9876543210',
        'purpose': 'Document Delivery',
        'flat_number': 'A-402',
        'status': 'INSIDE',
    }
)
VisitorLog.objects.filter(id=v_today.id).update(entry_time=timezone.now())
v_today.refresh_from_db()

# 2. Previous pass
past_date = timezone.now() - timedelta(days=2)
v_past, created = VisitorLog.objects.get_or_create(
    visitor_name="Old Contractor Inspection",
    defaults={
        'phone_number': '9123456780',
        'purpose': 'Plumbing Repair',
        'flat_number': 'B-101',
        'status': 'CHECKED_OUT',
    }
)
if created or v_past.entry_time.date() >= today:
    # Update entry_time to past
    VisitorLog.objects.filter(id=v_past.id).update(entry_time=past_date)
    v_past.refresh_from_db()

# Test 1: Main visitor passes page
r_main = client.get('/visitors/')
assert r_main.status_code == 200
html_main = r_main.content.decode('utf-8')

# Verify the strictly two clickable options are present
assert "Today's Passes" in html_main
assert "Previous Passes" in html_main
assert "?time_filter=today" in html_main
assert "?time_filter=previous" in html_main

# Verify the removed elements from user request/screenshot are absent:
assert "Visitor Log & Entry Passes" not in html_main, "Error: 'Visitor Log & Entry Passes' should be removed"
assert "Track delivery executives, cabs, contractors, and guests entering the society premises" not in html_main, "Error: Subtitle banner should be removed"
assert "All Passes" not in html_main, "Error: 'All Passes' button should be removed"
print("✓ Main visitor passes page cleanly removed 'Visitor Log & Entry Passes' heading, subtext, and 'All Passes' button!")
print("✓ Main visitor passes page contains strictly the two clickable 'Today's Passes' and 'Previous Passes'!")

# Test 2: Filter by Today's Passes
r_today = client.get('/visitors/?time_filter=today')
assert r_today.status_code == 200
html_today = r_today.content.decode('utf-8')
assert "Vikram Courier Express" in html_today
assert "Old Contractor Inspection" not in html_today
print("✓ Clickable [Today's Passes] correctly filters exclusively today's entries!")

# Test 3: Filter by Previous Passes
r_prev = client.get('/visitors/?time_filter=previous&q=Old+Contractor')
assert r_prev.status_code == 200
html_prev = r_prev.content.decode('utf-8')
assert "Old Contractor Inspection" in html_prev
assert "Vikram Courier Express" not in html_prev
print("✓ Clickable [Previous Passes] correctly filters exclusively past entries!")

# Test 4: Dashboard verification (Live Visitor Entries removed as requested)
r_dash = client.get('/dashboard/')
assert r_dash.status_code == 200
html_dash = r_dash.content.decode('utf-8')
assert "Live Visitor Entries" not in html_dash, "Error: 'Live Visitor Entries' should be removed from dashboard"
assert "Recent Service Requests" not in html_dash, "Error: 'Recent Service Requests' should be removed from dashboard"
assert "Society Analytics Panel" not in html_dash, "Error: 'Society Analytics Panel' should be removed from dashboard"
print("✓ Dashboard section cleanly removed 'Live Visitor Entries', 'Recent Service Requests', and 'Society Analytics Panel'!")

print("=== ALL VISITOR PASSES TESTS PASSED 100%! ===")
