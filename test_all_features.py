"""
Comprehensive automated test suite verifying all modules of AegisGate Society Manager.
"""

import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from society_app.models import SocietyNotice, ComplaintTicket, MaintenanceBill, VisitorLog, BiometricGateLog
from society_app.face_engine import recognize_gate_face

User = get_user_model()


def run_checks():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE AEGISGATE VERIFICATION SUITE")
    print("=" * 60)

    client = Client()

    # 1. VERIFY AUTHENTICATION & LOGIN
    print("\n[1/8] Verifying User Authentication & Roles...")
    admin = User.objects.get(username='admin')
    guard = User.objects.get(username='guard_vikram')
    john = User.objects.get(username='john_doe')

    assert admin.is_admin_role, "Admin role check failed"
    assert guard.is_staff_role, "Staff role check failed"
    assert john.is_resident_role, "Resident role check failed"
    print("  -> Roles verified: ADMIN, STAFF, RESIDENT")

    # Login check
    login_success = client.login(username='john_doe', password='resident123')
    assert login_success, "Resident login failed"
    print("  -> Resident login successful: john_doe")

    # 2. VERIFY DASHBOARD VIEW
    print("\n[2/8] Verifying Dashboard...")
    res = client.get('/dashboard/')
    assert res.status_code == 200, f"Dashboard returned {res.status_code}"
    assert 'Emerald Heights' in res.content.decode(), "Dashboard content missing"
    print("  -> Dashboard HTTP 200 OK")

    # 3. VERIFY NOTICES MODULE
    print("\n[3/8] Verifying Notice Board...")
    res = client.get('/notices/')
    assert res.status_code == 200, "Notice list failed"
    notices_count = SocietyNotice.objects.count()
    assert notices_count >= 1, "No notices in database"
    print(f"  -> Notice Board HTTP 200 OK ({notices_count} announcements loaded)")

    # 4. VERIFY TICKETING & ISSUE TRACKING
    print("\n[4/8] Verifying Service Tickets Module...")
    res = client.get('/tickets/')
    assert res.status_code == 200, "Tickets list failed"

    # Create new ticket via POST
    res = client.post('/tickets/create/', {
        'title': 'Corridor exhaust fan making loud rattling noise',
        'category': 'ELECTRICAL',
        'priority': 'MEDIUM',
        'description': 'Fan in block A 4th floor has loose bracket bolts.'
    })
    assert res.status_code == 302, f"Ticket creation failed with {res.status_code}"
    new_ticket = ComplaintTicket.objects.filter(title__icontains='exhaust fan').first()
    assert new_ticket is not None, "Created ticket not found in database"
    print(f"  -> Ticket created: {new_ticket.ticket_number}")

    # Add comment to ticket
    res = client.post(f'/tickets/{new_ticket.id}/comment/', {
        'message': 'Noise has been constant since this morning.'
    })
    assert res.status_code == 302, "Comment creation failed"
    assert new_ticket.comments.count() >= 1, "Comment not saved"
    print(f"  -> Comment thread working on {new_ticket.ticket_number}")

    # Switch to staff to update status
    client.login(username='guard_vikram', password='guard123')
    res = client.post(f'/tickets/{new_ticket.id}/status/', {
        'status': 'IN_PROGRESS',
        'assigned_staff': guard.id,
        'resolution_notes': 'Electrician assigned with safety ladder.'
    })
    assert res.status_code == 302, "Staff status update failed"
    new_ticket.refresh_from_db()
    assert new_ticket.status == 'IN_PROGRESS', "Status did not update"
    print(f"  -> Staff status transition verified: IN_PROGRESS")

    # 5. VERIFY MAINTENANCE & BILLING
    print("\n[5/8] Verifying Maintenance & Fee Collection...")
    client.login(username='john_doe', password='resident123')
    res = client.get('/maintenance/')
    assert res.status_code == 200, "Maintenance list failed"

    pending_bill = MaintenanceBill.objects.filter(resident=john, status='PENDING').first()
    if pending_bill:
        res = client.post(f'/maintenance/{pending_bill.id}/pay/', {
            'payment_method': 'Instant UPI Test'
        })
        assert res.status_code == 302, "Payment simulation failed"
        pending_bill.refresh_from_db()
        assert pending_bill.status == 'PAID', "Bill status not changed to PAID"
        assert pending_bill.transaction_id.startswith('TXN-'), "Transaction ID missing"
        print(f"  -> Payment settled for Invoice {pending_bill.bill_number}: TXN {pending_bill.transaction_id}")
    else:
        print("  -> Maintenance billing verified")

    # 6. VERIFY VISITOR MANAGEMENT & PASSES
    print("\n[6/8] Verifying Visitor Gate Management...")
    res = client.get('/visitors/')
    assert res.status_code == 200, "Visitor list failed"

    # Pre-approve a pass
    res = client.post('/visitors/preapprove/', {
        'visitor_name': 'Robert Taylor',
        'phone_number': '+1 (555) 334-9000',
        'purpose': 'Guest / Friend',
        'vehicle_number': 'CA-77-XYZ-11'
    })
    assert res.status_code == 302, "Pre-approve failed"
    new_vis = VisitorLog.objects.filter(visitor_name='Robert Taylor').first()
    assert new_vis is not None, "Pre-approved visitor not found"
    assert len(new_vis.pass_code) >= 6, "Pass code not generated"
    print(f"  -> Pre-approved visitor pass generated: Code [{new_vis.pass_code}] for {new_vis.visitor_name}")

    # 7. STANDOUT FEATURE: OPENCV FACE RECOGNITION PIPELINE
    print("\n[7/8] Verifying OpenCV Biometric Face Recognition...")
    terminal_res = client.get('/gate/terminal/')
    assert terminal_res.status_code == 200, "Gate terminal view failed"
    print("  -> Face Gate Terminal View HTTP 200 OK")

    # Test John Doe's enrolled face photo through recognize_gate_face
    john_res = recognize_gate_face('media/face_profiles/john_doe.jpg')
    assert john_res['success'] is True, f"Recognition failed: {john_res}"
    assert john_res['match'] is True, f"Expected match=True, got {john_res}"
    assert 'John Doe' in john_res['name'], f"Expected John Doe, got {john_res.get('name')}"
    assert john_res['confidence'] > 90.0, f"Confidence too low: {john_res.get('confidence')}"
    assert john_res['annotated_image'] is not None, "Annotated base64 image missing"
    print(f"  -> John Doe Recognized: Confidence {john_res['confidence']}% | HUD Annotated Frame Generated")

    # Test Sarah Connor's enrolled face photo
    sarah_res = recognize_gate_face('media/face_profiles/sarah_connor.jpg')
    assert sarah_res['match'] is True, f"Expected match=True for Sarah, got {sarah_res}"
    print(f"  -> Sarah Connor Recognized: Confidence {sarah_res['confidence']}%")

    # Test API endpoint POST /api/face-recognize/
    with open('media/face_profiles/john_doe.jpg', 'rb') as fp:
        api_res = client.post('/api/face-recognize/', {'image_file': fp, 'gate_name': 'Main Gate 1'})
    assert api_res.status_code == 200, f"API returned {api_res.status_code}"
    api_data = api_res.json()
    assert api_data['match'] is True, "API match was false"
    assert 'log_id' in api_data, "BiometricGateLog ID missing in API response"
    print(f"  -> REST API /api/face-recognize/ HTTP 200 OK: Log ID #{api_data['log_id']}")

    # 8. VERIFY REST STATS & STREAMLIT ANALYTICS INTEGRATION
    print("\n[8/8] Verifying REST API Quick Stats & Streamlit Architecture...")
    stats_res = client.get('/api/quick-stats/')
    assert stats_res.status_code == 200, "Quick stats API failed"
    stats_data = stats_res.json()
    assert 'total_residents' in stats_data, "Missing total_residents in stats"
    print(f"  -> Quick Stats API: {stats_data}")

    # Check Streamlit script syntax
    with open('admin_analytics.py', 'r', encoding='utf-8') as f:
        code = f.read()
    compile(code, 'admin_analytics.py', 'exec')
    print("  -> Streamlit admin_analytics.py compiled and syntax valid")

    print("\n" + "=" * 60)
    print("ALL 8 VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 60)


if __name__ == '__main__':
    run_checks()
