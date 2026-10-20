import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Society Admin / Committee Board'),
        ('STAFF', 'Security Gate Officer / Facility Staff'),
        ('RESIDENT', 'Resident Member'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='RESIDENT')
    phone_number = models.CharField(max_length=20, blank=True)
    flat_number = models.CharField(max_length=20, blank=True, help_text="e.g. A-402")
    block_tower = models.CharField(max_length=50, blank=True, help_text="e.g. Tower 1 / Emerald Block")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    face_photo = models.ImageField(upload_to='face_profiles/', blank=True, null=True, help_text="Reference face photo for gate recognition")
    face_encoding = models.TextField(blank=True, null=True, help_text="Serialized facial feature descriptor")
    vehicle_number = models.CharField(max_length=30, blank=True, help_text="e.g. KA-01-MJ-4521")
    emergency_contact = models.CharField(max_length=50, blank=True)
    is_verified_resident = models.BooleanField(default=True)

    @property
    def is_admin_role(self):
        return self.role == 'ADMIN' or self.is_superuser

    @property
    def is_staff_role(self):
        return self.role in ['ADMIN', 'STAFF'] or self.is_staff

    @property
    def is_resident_role(self):
        return self.role == 'RESIDENT'

    def __str__(self):
        unit = f" [{self.flat_number}]" if self.flat_number else ""
        return f"{self.get_full_name() or self.username} ({self.get_role_display()}){unit}"


class SocietyNotice(models.Model):
    CATEGORY_CHOICES = (
        ('GENERAL', 'General Announcement'),
        ('MAINTENANCE', 'Maintenance & Utilities'),
        ('SECURITY', 'Security & Safety'),
        ('EVENT', 'Community Event'),
        ('EMERGENCY', 'Emergency Alert'),
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='GENERAL')
    is_pinned = models.BooleanField(default=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notices')
    attachment = models.FileField(upload_to='notices/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"{'[PINNED] ' if self.is_pinned else ''}{self.title} ({self.get_category_display()})"


class ComplaintTicket(models.Model):
    CATEGORY_CHOICES = (
        ('PLUMBING', 'Plumbing & Water Supply'),
        ('ELECTRICAL', 'Electrical & Lighting'),
        ('ELEVATOR', 'Lift & Elevator'),
        ('SECURITY', 'Security & Parking'),
        ('CLEANLINESS', 'Sanitation & Housekeeping'),
        ('NOISE', 'Noise & Disturbance'),
        ('OTHER', 'General Maintenance'),
    )
    PRIORITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent Emergency'),
    )
    STATUS_CHOICES = (
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    )

    ticket_number = models.CharField(max_length=30, unique=True, editable=False)
    resident = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='complaints')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='OTHER')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    attachment = models.ImageField(upload_to='complaints/', blank=True, null=True)
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks'
    )
    resolution_notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = f"TKT-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        if self.status in ['RESOLVED', 'CLOSED'] and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_number}: {self.title} [{self.get_status_display()}]"


class TicketComment(models.Model):
    ticket = models.ForeignKey(ComplaintTicket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.username} on {self.ticket.ticket_number}"


class MaintenanceBill(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
    )
    bill_number = models.CharField(max_length=40, unique=True, editable=False)
    resident = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bills')
    month = models.CharField(max_length=30, help_text="e.g. October 2026")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    paid_date = models.DateTimeField(blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, default='')
    transaction_id = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.bill_number = f"INV-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bill_number} - {self.resident.username} - {self.month} (${self.amount})"


class VisitorLog(models.Model):
    ENTRY_TYPES = (
        ('MANUAL', 'Security Guard Entry'),
        ('PRE_APPROVED', 'Resident Pre-Approved Pass'),
        ('FACE_RECOGNITION', 'Biometric Fast-Track Entry'),
    )
    STATUS_CHOICES = (
        ('INSIDE', 'Inside Campus'),
        ('CHECKED_OUT', 'Checked Out'),
        ('DENIED', 'Access Denied'),
    )
    visitor_name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=20)
    purpose = models.CharField(max_length=150, help_text="e.g. Delivery, Guest, Contractor, Taxi")
    visiting_resident = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='hosted_visitors'
    )
    flat_number = models.CharField(max_length=20, help_text="Destination Unit")
    vehicle_number = models.CharField(max_length=30, blank=True, default='')
    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPES, default='MANUAL')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INSIDE')
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(blank=True, null=True)
    snapshot = models.ImageField(upload_to='visitor_snapshots/', blank=True, null=True)
    pass_code = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        ordering = ['-entry_time']

    def save(self, *args, **kwargs):
        if not self.pass_code:
            self.pass_code = uuid.uuid4().hex[:6].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Visitor: {self.visitor_name} -> {self.flat_number} [{self.get_status_display()}]"


class BiometricGateLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    recognized_name = models.CharField(max_length=120)
    matched_role = models.CharField(max_length=30)
    confidence_score = models.FloatField(help_text="Confidence percentage 0-100%")
    gate_name = models.CharField(max_length=80, default="Gate 1 - Main Entry")
    timestamp = models.DateTimeField(auto_now_add=True)
    access_granted = models.BooleanField(default=True)
    capture_image = models.ImageField(upload_to='biometric_captures/', blank=True, null=True)
    notes = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Biometric: {self.recognized_name} ({self.confidence_score:.1f}%) at {self.timestamp.strftime('%H:%M:%S')}"
