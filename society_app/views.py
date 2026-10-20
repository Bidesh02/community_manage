import json
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import User, SocietyNotice, ComplaintTicket, TicketComment, MaintenanceBill, VisitorLog, BiometricGateLog
from .forms import (
    ResidentRegistrationForm, UserProfileUpdateForm, ComplaintTicketForm,
    TicketStatusUpdateForm, TicketCommentForm, SocietyNoticeForm,
    VisitorCheckinForm, MaintenanceBillCreateForm
)
from .face_engine import recognize_gate_face, train_face_recognizer
from .serializers import ComplaintTicketSerializer, MaintenanceBillSerializer, VisitorLogSerializer


# -------------------------------------------------------------
# AUTHENTICATION VIEWS
# -------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'auth/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('login')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = ResidentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            # If user uploaded face photo, retrain the face model in background/inline
            if user.face_photo:
                try:
                    train_face_recognizer()
                except Exception as e:
                    print("Face train notice:", e)
            login(request, user)
            messages.success(request, f"Account registered! Welcome to the society, {user.first_name}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ResidentRegistrationForm()
    return render(request, 'auth/register.html', {'form': form})


@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            if 'face_photo' in request.FILES:
                train_face_recognizer()
                messages.success(request, "Profile and biometric facial template updated successfully!")
            else:
                messages.success(request, "Profile updated successfully.")
            return redirect('profile')
    else:
        form = UserProfileUpdateForm(instance=user)

    my_recent_logs = BiometricGateLog.objects.filter(user=user)[:5]
    return render(request, 'auth/profile.html', {
        'form': form,
        'user_obj': user,
        'recent_logs': my_recent_logs
    })


# -------------------------------------------------------------
# DASHBOARD VIEW
# -------------------------------------------------------------
@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.now().date()

    # Common pinned notices
    pinned_notices = SocietyNotice.objects.filter(is_pinned=True)[:3]
    recent_notices = SocietyNotice.objects.all()[:5]

    context = {
        'user': user,
        'pinned_notices': pinned_notices,
        'recent_notices': recent_notices,
        'today': today,
    }

    if user.is_admin_role or user.is_staff_role:
        # Admin / Staff KPIs
        total_residents = User.objects.filter(role='RESIDENT').count()
        total_open_tickets = ComplaintTicket.objects.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
        urgent_tickets = ComplaintTicket.objects.filter(priority='URGENT', status__in=['OPEN', 'IN_PROGRESS']).count()
        visitors_inside = VisitorLog.objects.filter(status='INSIDE').count()
        today_visitors = VisitorLog.objects.filter(entry_time__date=today).count()
        today_biometric_entries = BiometricGateLog.objects.filter(timestamp__date=today, access_granted=True).count()

        pending_dues = MaintenanceBill.objects.filter(status__in=['PENDING', 'OVERDUE']).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        collected_this_month = MaintenanceBill.objects.filter(status='PAID').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        recent_tickets = ComplaintTicket.objects.all()[:5]
        recent_visitors = VisitorLog.objects.all()[:6]
        recent_biometric_entries = BiometricGateLog.objects.all()[:6]

        context.update({
            'total_residents': total_residents,
            'total_open_tickets': total_open_tickets,
            'urgent_tickets': urgent_tickets,
            'visitors_inside': visitors_inside,
            'today_visitors': today_visitors,
            'today_biometric_entries': today_biometric_entries,
            'pending_dues': pending_dues,
            'collected_this_month': collected_this_month,
            'recent_tickets': recent_tickets,
            'recent_visitors': recent_visitors,
            'recent_biometric_entries': recent_biometric_entries,
        })
    else:
        # Resident-specific KPIs
        my_tickets = ComplaintTicket.objects.filter(resident=user)
        my_open_tickets_count = my_tickets.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
        my_bills = MaintenanceBill.objects.filter(resident=user)
        my_pending_bill = my_bills.filter(status__in=['PENDING', 'OVERDUE']).first()
        my_pending_amount = my_bills.filter(status__in=['PENDING', 'OVERDUE']).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        my_recent_visitors = VisitorLog.objects.filter(visiting_resident=user)[:5]
        my_biometrics = BiometricGateLog.objects.filter(user=user)[:5]

        context.update({
            'my_tickets': my_tickets[:5],
            'my_open_tickets_count': my_open_tickets_count,
            'my_bills': my_bills[:4],
            'my_pending_bill': my_pending_bill,
            'my_pending_amount': my_pending_amount,
            'my_recent_visitors': my_recent_visitors,
            'my_biometrics': my_biometrics,
        })

    return render(request, 'dashboard/index.html', context)


# -------------------------------------------------------------
# NOTICES MODULE
# -------------------------------------------------------------
@login_required
def notice_list_view(request):
    category = request.GET.get('category')
    search = request.GET.get('q')

    notices = SocietyNotice.objects.all()
    if category:
        notices = notices.filter(category=category)
    if search:
        notices = notices.filter(Q(title__icontains=search) | Q(content__icontains=search))

    paginator = Paginator(notices, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'notices/list.html', {
        'page_obj': page_obj,
        'category': category,
        'search': search,
        'categories': SocietyNotice.CATEGORY_CHOICES,
    })


@login_required
def notice_create_view(request):
    if not (request.user.is_admin_role or request.user.is_staff_role):
        messages.error(request, "Only society administrators or staff can post announcements.")
        return redirect('notice_list')

    if request.method == 'POST':
        form = SocietyNoticeForm(request.POST, request.FILES)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.author = request.user
            notice.save()
            messages.success(request, f"Notice '{notice.title}' published successfully.")
            return redirect('notice_list')
    else:
        form = SocietyNoticeForm()
    return render(request, 'notices/create.html', {'form': form})


@login_required
def notice_delete_view(request, pk):
    notice = get_object_or_404(SocietyNotice, pk=pk)
    if request.user.is_admin_role or notice.author == request.user:
        notice.delete()
        messages.success(request, "Notice deleted.")
    else:
        messages.error(request, "Unauthorized to delete this notice.")
    return redirect('notice_list')


# -------------------------------------------------------------
# TICKETING & ISSUE TRACKING MODULE
# -------------------------------------------------------------
@login_required
def ticket_list_view(request):
    user = request.user
    status_filter = request.GET.get('status')
    category_filter = request.GET.get('category')
    priority_filter = request.GET.get('priority')
    search = request.GET.get('q')

    if user.is_admin_role or user.is_staff_role:
        tickets = ComplaintTicket.objects.all()
    else:
        tickets = ComplaintTicket.objects.filter(resident=user)

    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if category_filter:
        tickets = tickets.filter(category=category_filter)
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    if search:
        tickets = tickets.filter(Q(title__icontains=search) | Q(ticket_number__icontains=search) | Q(description__icontains=search))

    paginator = Paginator(tickets, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'tickets/list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'priority_filter': priority_filter,
        'search': search,
        'categories': ComplaintTicket.CATEGORY_CHOICES,
        'priorities': ComplaintTicket.PRIORITY_CHOICES,
        'statuses': ComplaintTicket.STATUS_CHOICES,
    })


@login_required
def ticket_create_view(request):
    if request.method == 'POST':
        form = ComplaintTicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.resident = request.user
            ticket.save()
            messages.success(request, f"Ticket #{ticket.ticket_number} created! A technician or facility staff will review it.")
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = ComplaintTicketForm()
    return render(request, 'tickets/create.html', {'form': form})


@login_required
def ticket_detail_view(request, pk):
    ticket = get_object_or_404(ComplaintTicket, pk=pk)
    # Check permission: resident owner or admin/staff
    if not (request.user.is_admin_role or request.user.is_staff_role or ticket.resident == request.user):
        messages.error(request, "You are not authorized to view this ticket.")
        return redirect('ticket_list')

    status_form = None
    if request.user.is_admin_role or request.user.is_staff_role:
        status_form = TicketStatusUpdateForm(instance=ticket)

    comment_form = TicketCommentForm()

    return render(request, 'tickets/detail.html', {
        'ticket': ticket,
        'status_form': status_form,
        'comment_form': comment_form,
        'comments': ticket.comments.all()
    })


@login_required
def ticket_update_status_view(request, pk):
    ticket = get_object_or_404(ComplaintTicket, pk=pk)
    if not (request.user.is_admin_role or request.user.is_staff_role):
        messages.error(request, "Permission denied.")
        return redirect('ticket_detail', pk=pk)

    if request.method == 'POST':
        form = TicketStatusUpdateForm(request.POST, instance=ticket)
        if form.is_valid():
            form.save()
            messages.success(request, f"Ticket #{ticket.ticket_number} updated to '{ticket.get_status_display()}'.")
    return redirect('ticket_detail', pk=pk)


@login_required
def ticket_comment_create_view(request, pk):
    ticket = get_object_or_404(ComplaintTicket, pk=pk)
    if request.method == 'POST':
        form = TicketCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.save()
            messages.success(request, "Comment posted.")
    return redirect('ticket_detail', pk=pk)


# -------------------------------------------------------------
# MAINTENANCE & BILLING MODULE
# -------------------------------------------------------------
@login_required
def maintenance_list_view(request):
    user = request.user
    if user.is_admin_role or user.is_staff_role:
        bills = MaintenanceBill.objects.all()
    else:
        bills = MaintenanceBill.objects.filter(resident=user)

    status_filter = request.GET.get('status')
    if status_filter:
        bills = bills.filter(status=status_filter)

    total_amount = bills.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    paid_amount = bills.filter(status='PAID').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    pending_amount = bills.filter(status__in=['PENDING', 'OVERDUE']).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    paginator = Paginator(bills, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'maintenance/list.html', {
        'page_obj': page_obj,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'pending_amount': pending_amount,
        'status_filter': status_filter,
    })


@login_required
def maintenance_pay_view(request, pk):
    bill = get_object_or_404(MaintenanceBill, pk=pk)
    if not (request.user.is_admin_role or bill.resident == request.user):
        messages.error(request, "Unauthorized payment attempt.")
        return redirect('maintenance_list')

    if request.method == 'POST':
        method = request.POST.get('payment_method', 'Online UPI')
        bill.status = 'PAID'
        bill.paid_date = timezone.now()
        bill.payment_method = method
        bill.transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        bill.save()
        messages.success(request, f"Payment of ${bill.amount} confirmed! Transaction ID: {bill.transaction_id}")
    return redirect('maintenance_list')


@login_required
def maintenance_generate_view(request):
    if not request.user.is_admin_role:
        messages.error(request, "Only administrators can generate society billing.")
        return redirect('maintenance_list')

    if request.method == 'POST':
        form = MaintenanceBillCreateForm(request.POST)
        if form.is_valid():
            bill = form.save()
            messages.success(request, f"Maintenance bill #{bill.bill_number} issued for {bill.resident.username}.")
            return redirect('maintenance_list')
    else:
        form = MaintenanceBillCreateForm()
    return render(request, 'maintenance/generate.html', {'form': form})


# -------------------------------------------------------------
# VISITOR & GATE MANAGEMENT MODULE
# -------------------------------------------------------------
@login_required
def visitor_list_view(request):
    user = request.user
    if user.is_admin_role or user.is_staff_role:
        visitors = VisitorLog.objects.all()
    else:
        visitors = VisitorLog.objects.filter(visiting_resident=user)

    status_filter = request.GET.get('status')
    if status_filter:
        visitors = visitors.filter(status=status_filter)

    search = request.GET.get('q')
    if search:
        visitors = visitors.filter(Q(visitor_name__icontains=search) | Q(flat_number__icontains=search) | Q(vehicle_number__icontains=search) | Q(pass_code__icontains=search))

    paginator = Paginator(visitors, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'visitors/list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search': search,
    })


@login_required
def visitor_checkin_view(request):
    if not (request.user.is_admin_role or request.user.is_staff_role):
        messages.error(request, "Only security staff can perform physical visitor check-ins.")
        return redirect('visitor_list')

    if request.method == 'POST':
        form = VisitorCheckinForm(request.POST)
        if form.is_valid():
            visitor = form.save()
            messages.success(request, f"Visitor {visitor.visitor_name} checked in! Pass Code: {visitor.pass_code}")
            return redirect('visitor_list')
    else:
        form = VisitorCheckinForm()
    return render(request, 'visitors/checkin.html', {'form': form})


@login_required
def visitor_preapprove_view(request):
    """
    Resident can pre-approve expected guests or delivery couriers.
    """
    if request.method == 'POST':
        visitor_name = request.POST.get('visitor_name')
        phone_number = request.POST.get('phone_number')
        purpose = request.POST.get('purpose', 'Guest')
        vehicle_number = request.POST.get('vehicle_number', '')

        if visitor_name and phone_number:
            v = VisitorLog.objects.create(
                visitor_name=visitor_name,
                phone_number=phone_number,
                purpose=purpose,
                visiting_resident=request.user,
                flat_number=request.user.flat_number or 'Unassigned',
                vehicle_number=vehicle_number,
                entry_type='PRE_APPROVED',
                status='INSIDE'
            )
            messages.success(request, f"Pass generated for {visitor_name}! Security Pass Code: {v.pass_code}")
            return redirect('visitor_list')
        else:
            messages.error(request, "Name and phone number are required.")
    return render(request, 'visitors/preapprove.html')


@login_required
def visitor_checkout_view(request, pk):
    visitor = get_object_or_404(VisitorLog, pk=pk)
    visitor.status = 'CHECKED_OUT'
    visitor.exit_time = timezone.now()
    visitor.save()
    messages.success(request, f"Visitor {visitor.visitor_name} checked out at {visitor.exit_time.strftime('%H:%M')}.")
    return redirect('visitor_list')


# -------------------------------------------------------------
# STANDOUT FEATURE: REAL-TIME OPENCV FACE RECOGNITION TERMINAL
# -------------------------------------------------------------
@login_required
def face_terminal_view(request):
    """
    Futuristic Security Gate Terminal interface:
    - Real-time webcam canvas feed
    - Face detection bounding box HUD
    - Instant match feedback with resident name, flat, vehicle, confidence
    - Automatic logging to BiometricGateLog
    """
    registered_residents = User.objects.filter(face_photo__isnull=False).exclude(face_photo='')
    recent_biometric_logs = BiometricGateLog.objects.all()[:8]

    return render(request, 'gate/face_terminal.html', {
        'registered_residents': registered_residents,
        'recent_logs': recent_biometric_logs,
        'gate_name': 'Gate 1 - North Perimeter'
    })


@login_required
def biometric_logs_view(request):
    logs = BiometricGateLog.objects.all()
    paginator = Paginator(logs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'gate/biometric_logs.html', {'page_obj': page_obj})


@login_required
def retrain_face_model_view(request):
    if not (request.user.is_admin_role or request.user.is_staff_role):
        messages.error(request, "Permission denied.")
        return redirect('dashboard')
    result = train_face_recognizer()
    if result['status'] == 'success':
        messages.success(request, f"Face Recognition Engine retrained successfully! Loaded {result['trained_users']} residents ({result['samples']} facial samples).")
    else:
        messages.warning(request, "No registered face profiles found. Please upload face photos in resident profiles.")
    return redirect('face_terminal')


# -------------------------------------------------------------
# REST API ENDPOINTS
# -------------------------------------------------------------
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def api_face_recognize(request):
    """
    Accepts:
      - 'image_base64': base64 string from client webcam/canvas
      - OR 'image_file': multipart file upload
    Runs OpenCV face detection and recognition.
    Creates BiometricGateLog on match.
    """
    image_input = None
    if 'image_file' in request.FILES:
        image_input = request.FILES['image_file']
    elif 'image_base64' in request.data:
        image_input = request.data['image_base64']
    elif 'image' in request.data:
        image_input = request.data['image']

    if not image_input:
        return Response({
            'success': False,
            'match': False,
            'message': 'No image provided. Pass image_base64 or image_file.'
        }, status=status.HTTP_400_BAD_REQUEST)

    result = recognize_gate_face(image_input)

    # If match or unrecognized, log biometric event
    if result.get('face_detected'):
        user_inst = None
        user_id = result.get('user_id')
        if user_id:
            try:
                user_inst = User.objects.get(id=user_id)
            except User.DoesNotExist:
                user_inst = None

        log_entry = BiometricGateLog.objects.create(
            user=user_inst,
            recognized_name=result.get('name') if result.get('match') else 'Unregistered Visitor',
            matched_role=result.get('role', 'Visitor'),
            confidence_score=result.get('confidence', 0.0),
            gate_name=request.data.get('gate_name', 'Gate 1 - North Perimeter'),
            access_granted=result.get('match', False),
            notes=result.get('message', '')
        )
        result['log_id'] = log_entry.id
        result['timestamp'] = log_entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_quick_stats(request):
    today = timezone.now().date()
    stats = {
        'total_residents': User.objects.filter(role='RESIDENT').count(),
        'open_tickets': ComplaintTicket.objects.filter(status__in=['OPEN', 'IN_PROGRESS']).count(),
        'visitors_today': VisitorLog.objects.filter(entry_time__date=today).count(),
        'biometric_today': BiometricGateLog.objects.filter(timestamp__date=today, access_granted=True).count(),
        'pending_maintenance': float(MaintenanceBill.objects.filter(status__in=['PENDING', 'OVERDUE']).aggregate(total=Sum('amount'))['total'] or 0.0),
    }
    return Response(stats)
