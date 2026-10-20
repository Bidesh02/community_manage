"""
Seed script to populate AegisGate with realistic society data, enrolled face models,
notices, maintenance bills, and tickets.
"""

import os
import shutil
import django
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'society_core.settings')
django.setup()

from society_app.models import (
    User, SocietyNotice, ComplaintTicket, TicketComment,
    MaintenanceBill, VisitorLog, BiometricGateLog
)
from society_app.face_engine import train_face_recognizer, recognize_gate_face

MEDIA_DIR = os.path.join(os.path.dirname(__file__), 'media', 'face_profiles')
os.makedirs(MEDIA_DIR, exist_ok=True)

# Copy artifact portraits to media directory
ARTIFACT_DIR = r"C:\Users\bides\.gemini\antigravity-ide\brain\ad6ec444-f62b-4da0-a862-8d5a702e2cf9"

portraits = {
    'john_doe': os.path.join(ARTIFACT_DIR, 'john_doe_portrait_1792478100830.jpg'),
    'sarah_connor': os.path.join(ARTIFACT_DIR, 'sarah_connor_portrait_1792478122396.jpg'),
    'guard_vikram': os.path.join(ARTIFACT_DIR, 'guard_portrait_1792478143561.jpg'),
}

for name, src in portraits.items():
    dst = os.path.join(MEDIA_DIR, f"{name}.jpg")
    if os.path.exists(src):
        shutil.copyfile(src, dst)
        print(f"Copied portrait for {name} -> {dst}")


def seed():
    print("Clearing old records...")
    # Clean up non-admin test data if desired or update
    User.objects.all().delete()
    SocietyNotice.objects.all().delete()
    ComplaintTicket.objects.all().delete()
    MaintenanceBill.objects.all().delete()
    VisitorLog.objects.all().delete()
    BiometricGateLog.objects.all().delete()

    print("Creating Users & RBAC Roles...")

    # 1. Super Admin
    admin_user = User.objects.create_superuser(
        username='admin',
        email='president@aegisgate.com',
        password='admin123',
        first_name='Marcus',
        last_name='Sterling',
        role='ADMIN',
        flat_number='Penthouse 01',
        block_tower='Apex Tower',
        phone_number='+1 (555) 901-2200',
        vehicle_number='KA-01-EXP-9999'
    )

    # 2. Security Guard / Staff
    guard_user = User.objects.create_user(
        username='guard_vikram',
        email='security.gate1@aegisgate.com',
        password='guard123',
        first_name='Vikram',
        last_name='Rathore',
        role='STAFF',
        flat_number='Security Gatehouse A',
        block_tower='Perimeter Station',
        phone_number='+1 (555) 321-4455',
        face_photo='face_profiles/guard_vikram.jpg'
    )
    guard_user.is_staff = True
    guard_user.save()

    # 3. Resident 1 (John Doe)
    john = User.objects.create_user(
        username='john_doe',
        email='john.doe@residence.com',
        password='resident123',
        first_name='John',
        last_name='Doe',
        role='RESIDENT',
        flat_number='A-402',
        block_tower='Emerald Tower',
        phone_number='+1 (555) 489-1029',
        vehicle_number='KA-01-MJ-4521',
        emergency_contact='+1 (555) 489-9999',
        face_photo='face_profiles/john_doe.jpg'
    )

    # 4. Resident 2 (Sarah Connor)
    sarah = User.objects.create_user(
        username='sarah_connor',
        email='sarah.connor@cyberdyne.org',
        password='resident123',
        first_name='Sarah',
        last_name='Connor',
        role='RESIDENT',
        flat_number='B-204',
        block_tower='Sapphire Tower',
        phone_number='+1 (555) 777-1984',
        vehicle_number='DL-04-CA-8890',
        emergency_contact='+1 (555) 777-2000',
        face_photo='face_profiles/sarah_connor.jpg'
    )

    # 5. Resident 3 (David Kim)
    david = User.objects.create_user(
        username='david_kim',
        email='david.kim@techlab.io',
        password='resident123',
        first_name='David',
        last_name='Kim',
        role='RESIDENT',
        flat_number='C-301',
        block_tower='Diamond Block',
        phone_number='+1 (555) 662-8190',
        vehicle_number='MH-12-PQ-9021',
        emergency_contact='+1 (555) 662-1111'
    )

    print("Users created: admin, guard_vikram, john_doe, sarah_connor, david_kim")

    # Notices
    print("Creating Society Announcements...")
    SocietyNotice.objects.create(
        title="Emergency Elevator Inspection & Hydraulic Modernization",
        content="Please be informed that Otis technicians will conduct scheduled safety certification on Passenger Lift #2 in Emerald Tower this Thursday from 10:00 AM to 3:00 PM. Please use Service Lift #1 during this window.",
        category='MAINTENANCE',
        is_pinned=True,
        author=admin_user
    )

    SocietyNotice.objects.create(
        title="Annual Community Cultural Gathering & Gala Banquet",
        content="The Managing Committee cordially invites all families to the Grand Amphitheater this Saturday at 6:30 PM. Live music, food trucks, and children's sports tournament will be hosted. RSVP via the society portal.",
        category='EVENT',
        is_pinned=True,
        author=admin_user
    )

    SocietyNotice.objects.create(
        title="Mandatory Vehicle Gate Tag Registration & Face Biometric Check",
        content="Security officers have activated the OpenCV Face Recognition Gate Scanner at North Gate 1. All registered residents are requested to upload front-facing portrait photos on their profile page to expedite gate entry clearance.",
        category='SECURITY',
        is_pinned=False,
        author=guard_user
    )

    SocietyNotice.objects.create(
        title="Clubhouse & Heated Infinity Pool Winter Timings",
        content="Beginning next week, the swimming pool and fitness center will operate from 6:00 AM to 10:00 PM. Water temperature will be maintained at 28°C continuously.",
        category='GENERAL',
        is_pinned=False,
        author=admin_user
    )

    # Maintenance Bills
    print("Creating Maintenance Invoices...")
    today = timezone.now().date()
    
    # John's bill (Paid)
    MaintenanceBill.objects.create(
        resident=john,
        month="October 2026",
        amount=Decimal("250.00"),
        due_date=today + timedelta(days=5),
        status='PAID',
        paid_date=timezone.now() - timedelta(days=2),
        payment_method="Online UPI / Card",
        transaction_id="TXN-OCT26-89240"
    )

    # John's upcoming bill (Pending)
    MaintenanceBill.objects.create(
        resident=john,
        month="November 2026",
        amount=Decimal("250.00"),
        due_date=today + timedelta(days=25),
        status='PENDING'
    )

    # Sarah's bill (Pending)
    MaintenanceBill.objects.create(
        resident=sarah,
        month="October 2026",
        amount=Decimal("280.00"),
        due_date=today - timedelta(days=3),
        status='OVERDUE'
    )

    # David's bill (Paid)
    MaintenanceBill.objects.create(
        resident=david,
        month="October 2026",
        amount=Decimal("240.00"),
        due_date=today + timedelta(days=5),
        status='PAID',
        paid_date=timezone.now() - timedelta(days=1),
        payment_method="Net Banking",
        transaction_id="TXN-OCT26-55102"
    )

    # Admin's bill (Paid)
    MaintenanceBill.objects.create(
        resident=admin_user,
        month="October 2026",
        amount=Decimal("350.00"),
        due_date=today + timedelta(days=5),
        status='PAID',
        paid_date=timezone.now() - timedelta(days=4),
        payment_method="Corporate Auto-Debit",
        transaction_id="TXN-OCT26-11009"
    )

    # Complaint Tickets
    print("Creating Complaint Tickets & Resolution Threads...")
    t1 = ComplaintTicket.objects.create(
        resident=john,
        title="High water pressure causing pipe leak beneath master washbasin",
        description="Noticed water seeping from the chrome valve under the master bedroom vanity sink this morning. Needs an urgent washer gasket replacement.",
        category='PLUMBING',
        priority='HIGH',
        status='IN_PROGRESS',
        assigned_staff=guard_user
    )
    TicketComment.objects.create(
        ticket=t1,
        author=john,
        message="Water shutoff valve is currently turned halfway to avoid pooling on tiles."
    )
    TicketComment.objects.create(
        ticket=t1,
        author=guard_user,
        message="Technician Rajesh has been dispatched with brass replacement fittings. ETA 30 minutes."
    )

    t2 = ComplaintTicket.objects.create(
        resident=john,
        title="Corridor sensor light flickering on 4th floor elevator lobby",
        description="The motion sensor light in the hallway between Flat 402 and 404 flickers rapidly when activated.",
        category='ELECTRICAL',
        priority='LOW',
        status='RESOLVED',
        assigned_staff=guard_user,
        resolution_notes="Replaced faulty LED ballast and recalibrated PIR motion detector. All functioning correctly.",
        resolved_at=timezone.now() - timedelta(hours=6)
    )

    t3 = ComplaintTicket.objects.create(
        resident=sarah,
        title="Elevator B displaying floor misalignment warning",
        description="Lift stopped approximately 2 inches below the 2nd floor landing sill. Safety sensor triggered door delay.",
        category='ELEVATOR',
        priority='URGENT',
        status='OPEN'
    )

    t4 = ComplaintTicket.objects.create(
        resident=david,
        title="Excessive late-night noise from terrace pavilion",
        description="Bass reverberations audible in Unit C-301 past 11:30 PM last night.",
        category='NOISE',
        priority='MEDIUM',
        status='RESOLVED',
        assigned_staff=admin_user,
        resolution_notes="Night patrol issued verbal reminder to occupants. Terrace curfew reinforced at 10:30 PM.",
        resolved_at=timezone.now() - timedelta(days=1)
    )

    # Visitor Logs
    print("Creating Visitor Gate Passes...")
    now = timezone.now()
    VisitorLog.objects.create(
        visitor_name="Michael Scott",
        phone_number="+1 (555) 902-1111",
        purpose="Amazon Prime Courier Delivery",
        visiting_resident=john,
        flat_number="A-402",
        vehicle_number="KA-05-EB-4190",
        entry_type='PRE_APPROVED',
        status='CHECKED_OUT',
        entry_time=now - timedelta(hours=3),
        exit_time=now - timedelta(hours=2, minutes=45),
        pass_code="PRIME1"
    )

    VisitorLog.objects.create(
        visitor_name="Dr. Emily Watson",
        phone_number="+1 (555) 344-9898",
        purpose="Family Dinner Guest",
        visiting_resident=sarah,
        flat_number="B-204",
        vehicle_number="DL-03-TC-1234",
        entry_type='PRE_APPROVED',
        status='INSIDE',
        entry_time=now - timedelta(minutes=45),
        pass_code="PASS88"
    )

    VisitorLog.objects.create(
        visitor_name="Rajesh Kumar",
        phone_number="+1 (555) 881-2300",
        purpose="Society Emergency Plumbing Contractor",
        visiting_resident=john,
        flat_number="A-402",
        vehicle_number="KA-01-TOOL-09",
        entry_type='MANUAL',
        status='INSIDE',
        entry_time=now - timedelta(minutes=25),
        pass_code="WORK77"
    )

    VisitorLog.objects.create(
        visitor_name="Carlos Mendez",
        phone_number="+1 (555) 234-5544",
        purpose="Uber Ride Pickup",
        visiting_resident=david,
        flat_number="C-301",
        vehicle_number="MH-14-CAB-3030",
        entry_type='MANUAL',
        status='CHECKED_OUT',
        entry_time=now - timedelta(hours=4),
        exit_time=now - timedelta(hours=3, minutes=50),
        pass_code="UBER04"
    )

    # Train OpenCV Face Engine
    print("Training OpenCV Face Recognition Model...")
    res = train_face_recognizer()
    print("Training result:", res)

    # Add initial BiometricGateLogs
    BiometricGateLog.objects.create(
        user=john,
        recognized_name="John Doe",
        matched_role="Resident Member",
        confidence_score=97.8,
        gate_name="Gate 1 - North Perimeter",
        access_granted=True,
        notes="Automated biometric gate unlock"
    )

    BiometricGateLog.objects.create(
        user=sarah,
        recognized_name="Sarah Connor",
        matched_role="Resident Member",
        confidence_score=96.4,
        gate_name="Gate 1 - North Perimeter",
        access_granted=True,
        notes="Automated biometric gate unlock"
    )

    BiometricGateLog.objects.create(
        user=guard_user,
        recognized_name="Vikram Rathore",
        matched_role="Security Officer",
        confidence_score=98.9,
        gate_name="Gate 2 - East Service Entry",
        access_granted=True,
        notes="Staff duty shift clearance"
    )

    print("Seed complete! AegisGate is loaded with rich operational data.")


if __name__ == '__main__':
    seed()
