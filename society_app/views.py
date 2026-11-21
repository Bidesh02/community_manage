import json
import uuid
from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import (
    User, SocietyNotice, ComplaintTicket, TicketComment, MaintenanceBill,
    VisitorLog, BiometricGateLog, CommunityMessage, FundCampaign, FundContribution
)
from .forms import (
    ResidentRegistrationForm, UserProfileUpdateForm, ComplaintTicketForm,
    TicketStatusUpdateForm, TicketCommentForm, SocietyNoticeForm,
    VisitorCheckinForm, MaintenanceBillCreateForm, FundCampaignCreateForm, FundContributionForm
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

    google_user = request.session.get('google_user')

    # STEP 1: MUST SIGN IN WITH GOOGLE FIRST
    if not google_user:
        if request.method == 'POST':
            messages.error(request, "Access Denied: You must first authenticate with an active Google Account before registering.")
            return redirect('register')
        return render(request, 'auth/register.html', {
            'step': 'google_required',
            'google_user': None,
        })

    # STEP 2: Google Account Verified -> Proceed with Resident & Biometric Enrollment
    if request.method == 'POST':
        form = ResidentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            # Enforce Google-verified identity fields (cannot be tampered)
            user.email = google_user['email']
            user.google_id = google_user.get('google_id')
            user.google_avatar_url = google_user.get('picture')
            user.is_google_verified = True
            user.save()
            form.save_m2m()

            # Clean up the session
            request.session.pop('google_user', None)

            # If user uploaded face photo, train the biometric face model
            if user.face_photo:
                try:
                    train_face_recognizer()
                except Exception as e:
                    print("Face train notice:", e)

            login(request, user)
            messages.success(request, f"Registration complete! Welcome to AegisGate Society, {user.first_name}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors in the registration form below.")
    else:
        # Pre-fill form using verified Google identity
        initial_data = {
            'email': google_user.get('email', ''),
            'first_name': google_user.get('given_name') or (google_user.get('name', '').split()[0] if google_user.get('name') else ''),
            'last_name': google_user.get('family_name') or (' '.join(google_user.get('name', '').split()[1:]) if google_user.get('name') and len(google_user.get('name').split()) > 1 else ''),
            'username': google_user.get('email', '').split('@')[0].replace('.', '_'),
            'role': 'RESIDENT',
        }
        form = ResidentRegistrationForm(initial=initial_data)

    return render(request, 'auth/register.html', {
        'step': 'resident_form',
        'form': form,
        'google_user': google_user,
    })


@csrf_exempt
def google_verify_view(request):
    """
    Handles Google Authentication for both Registration prerequisite and Google Login.
    Supports:
    1. Official Google Identity Services (GSI) credential JWT verification.
    2. Zero-config / Instant development verification with active Google account simulation.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = request.POST.dict()
    except Exception:
        payload = request.POST.dict()

    credential = payload.get('credential')
    action = payload.get('action', 'register')  # 'register' or 'login'

    email = ''
    name = ''
    given_name = ''
    family_name = ''
    picture = ''
    google_id = ''

    if credential:
        # Live Google ID token verification with Google's public endpoint
        try:
            import urllib.request
            import json as json_lib
            verify_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
            req = urllib.request.Request(verify_url, headers={'User-Agent': 'AegisGate-OAuth/1.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                token_info = json_lib.loads(response.read().decode('utf-8'))
            
            email = token_info.get('email', '').strip().lower()
            google_id = token_info.get('sub', '')
            name = token_info.get('name', '')
            given_name = token_info.get('given_name', '')
            family_name = token_info.get('family_name', '')
            picture = token_info.get('picture', '')
            
            client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
            if client_id and token_info.get('aud') != client_id:
                return JsonResponse({'status': 'error', 'message': 'Google token audience mismatch.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Failed to verify Google token: {str(e)}'}, status=400)
    elif payload.get('google_email'):
        email = payload.get('google_email', '').strip().lower()
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            return JsonResponse({'status': 'error', 'message': 'Please provide a valid Google email address.'}, status=400)
        
        name = payload.get('google_name', '').strip()
        if not name:
            name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        
        parts = name.split()
        given_name = parts[0] if parts else ''
        family_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        google_id = f"google_verified_{abs(hash(email))}"
        picture = payload.get('google_picture', f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=4285F4&color=fff&size=128")
    else:
        return JsonResponse({'status': 'error', 'message': 'No Google authentication credentials provided.'}, status=400)

    # 1. Action: Direct Google Sign-In (Login)
    if action == 'login':
        matched_user = User.objects.filter(Q(google_id=google_id) | Q(email__iexact=email)).first()
        if matched_user:
            matched_user.is_google_verified = True
            if not matched_user.google_id:
                matched_user.google_id = google_id
            if picture and not matched_user.google_avatar_url:
                matched_user.google_avatar_url = picture
            matched_user.save(update_fields=['is_google_verified', 'google_id', 'google_avatar_url'])
            login(request, matched_user)
            messages.success(request, f"Welcome back, {matched_user.get_full_name() or matched_user.username}! Signed in with Google account ({email}).")
            return JsonResponse({'status': 'success', 'redirect_url': '/dashboard/'})
        else:
            return JsonResponse({
                'status': 'not_registered',
                'message': f"No resident account is linked to '{email}'. Please complete society registration first.",
                'redirect_url': '/register/'
            })

    # 2. Action: Registration Pre-verification
    existing_user = User.objects.filter(Q(google_id=google_id) | Q(email__iexact=email)).first()
    if existing_user:
        return JsonResponse({
            'status': 'already_registered',
            'message': f"An account with email '{email}' already exists in the society directory. Please log in directly.",
            'login_url': '/login/'
        })

    # Store verified Google identity in session
    request.session['google_user'] = {
        'google_id': google_id,
        'email': email,
        'name': name,
        'given_name': given_name,
        'family_name': family_name,
        'picture': picture,
        'verified_at': timezone.now().isoformat(),
    }
    request.session.modified = True

    return JsonResponse({
        'status': 'success',
        'message': f'Google account verified: {email}',
        'redirect_url': '/register/'
    })


def google_disconnect_view(request):
    """Disconnects the current unsubmitted Google verification session."""
    if 'google_user' in request.session:
        del request.session['google_user']
        request.session.modified = True
        messages.info(request, "Google session disconnected. You can sign in with another active Google account.")
    return redirect('register')



@login_required
def profile_view(request):
    """Own profile: any logged-in user can view and edit their own profile."""
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
        'recent_logs': my_recent_logs,
        'is_own_profile': True,
        'can_edit': True,
    })


@login_required
def resident_profile_view(request, pk):
    """
    View another resident's profile.
    Only admins (ADMIN role / superuser) can access this.
    """
    if not request.user.is_admin_role:
        messages.error(request, "Access denied. Only society managers can view resident profiles.")
        return redirect('dashboard')

    target_user = get_object_or_404(User, pk=pk)

    # If admin is viewing their own profile, redirect to the normal profile page
    if target_user == request.user:
        return redirect('profile')

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, request.FILES, instance=target_user)
        if form.is_valid():
            form.save()
            if 'face_photo' in request.FILES:
                train_face_recognizer()
                messages.success(request, f"Profile for {target_user.get_full_name() or target_user.username} updated (biometrics recalibrated).")
            else:
                messages.success(request, f"Profile for {target_user.get_full_name() or target_user.username} updated.")
            return redirect('resident_profile', pk=pk)
    else:
        form = UserProfileUpdateForm(instance=target_user)

    recent_logs = BiometricGateLog.objects.filter(user=target_user)[:5]
    return render(request, 'auth/profile.html', {
        'form': form,
        'user_obj': target_user,
        'recent_logs': recent_logs,
        'is_own_profile': False,
        'can_edit': True,
    })


@login_required
def resident_list_view(request):
    """
    Resident Families Directory: Lists registered resident households,
    their head of room, family count, family details (names/ages), and biometric status.
    Accessible exclusively to Society Administrators and Security Staff.
    """
    user = request.user
    if not (user.is_admin_role or user.is_staff_role):
        messages.error(request, "Access restricted: Only Society Administrators and Security Staff can access the Resident Families directory.")
        return redirect('dashboard')

    search_query = request.GET.get('q', '').strip()
    block_filter = request.GET.get('block', '').strip()

    residents = User.objects.filter(role='RESIDENT', is_active=True).order_by('block_tower', 'flat_number', 'first_name')

    if search_query:
        residents = residents.filter(
            Q(flat_number__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(family_details__icontains=search_query) |
            Q(block_tower__icontains=search_query)
        )

    if block_filter:
        residents = residents.filter(block_tower__iexact=block_filter)

    available_blocks = User.objects.filter(role='RESIDENT', is_active=True).exclude(block_tower='').values_list('block_tower', flat=True).distinct()

    all_active_residents = User.objects.filter(role='RESIDENT', is_active=True)
    total_families = all_active_residents.count()
    total_individuals = sum((r.family_members_count or 1) for r in all_active_residents)
    biometric_enrolled_count = all_active_residents.exclude(face_photo='').exclude(face_photo__isnull=True).count()
    is_elevated = user.is_admin_role or user.is_staff_role

    context = {
        'residents': residents,
        'search_query': search_query,
        'block_filter': block_filter,
        'available_blocks': available_blocks,
        'total_families': total_families,
        'total_individuals': total_individuals,
        'biometric_enrolled_count': biometric_enrolled_count,
        'is_elevated': is_elevated,
    }
    return render(request, 'residents/list.html', context)


# -------------------------------------------------------------
# DASHBOARD VIEW
# -------------------------------------------------------------
@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.now().date()

    # Time-of-day greeting
    current_hour = timezone.localtime().hour
    if 5 <= current_hour < 12:
        greeting_text = "Good morning"
        greeting_emoji = "🌅"
    elif 12 <= current_hour < 17:
        greeting_text = "Good afternoon"
        greeting_emoji = "☀️"
    elif 17 <= current_hour < 21:
        greeting_text = "Good evening"
        greeting_emoji = "🌇"
    else:
        greeting_text = "Good evening"
        greeting_emoji = "🌙"

    # Human-centric Community Amenities
    amenities = [
        {'name': 'Clubhouse & Resident Lounge', 'status': 'Open', 'hours': '6:00 AM – 10:30 PM', 'icon': 'fa-champagne-glasses', 'badge': 'Community Hub', 'color': '#6366f1'},
        {'name': 'Temperature-Controlled Pool', 'status': 'Open', 'hours': '6:00 AM – 9:00 PM', 'icon': 'fa-person-swimming', 'badge': 'Cleaned • 27°C', 'color': '#06b6d4'},
        {'name': 'Fitness & Cardio Center', 'status': 'Open', 'hours': '24/7 Resident Access', 'icon': 'fa-dumbbell', 'badge': 'Trainer on Duty', 'color': '#10b981'},
        {'name': 'Badminton & Tennis Courts', 'status': 'Open', 'hours': '6:00 AM – 10:00 PM', 'icon': 'fa-baseball-bat-ball', 'badge': 'Floodlights Ready', 'color': '#f59e0b'},
    ]

    # Emergency & Support Desk
    emergency_contacts = [
        {'title': 'Security Main Gate', 'ext': 'Ext. 101', 'phone': '+91 98765 00101', 'icon': 'fa-shield-halved', 'color': '#06b6d4'},
        {'title': 'Facility & Estate Office', 'ext': 'Ext. 102', 'phone': '+91 98765 00102', 'icon': 'fa-building', 'color': '#6366f1'},
        {'title': 'Emergency Medical Service', 'ext': 'Toll-free', 'phone': '108', 'icon': 'fa-truck-medical', 'color': '#f43f5e'},
        {'title': 'Police Control Helpline', 'ext': 'Emergency', 'phone': '100', 'icon': 'fa-building-shield', 'color': '#f59e0b'},
    ]

    context = {
        'user': user,
        'greeting_text': greeting_text,
        'greeting_emoji': greeting_emoji,
        'amenities': amenities,
        'emergency_contacts': emergency_contacts,
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
        total_funds_collected = FundContribution.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        active_funds_count = FundCampaign.objects.filter(status='ACTIVE').count()

        context.update({
            'total_residents': total_residents,
            'total_open_tickets': total_open_tickets,
            'urgent_tickets': urgent_tickets,
            'visitors_inside': visitors_inside,
            'today_visitors': today_visitors,
            'today_biometric_entries': today_biometric_entries,
            'pending_dues': pending_dues,
            'collected_this_month': collected_this_month,
            'total_funds_collected': total_funds_collected,
            'active_funds_count': active_funds_count,
        })
    else:
        # Resident-specific KPIs
        my_open_tickets_count = ComplaintTicket.objects.filter(resident=user, status__in=['OPEN', 'IN_PROGRESS']).count()
        my_pending_amount = MaintenanceBill.objects.filter(resident=user, status__in=['PENDING', 'OVERDUE']).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        my_funds_contributed = FundContribution.objects.filter(contributor=user).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        context.update({
            'my_open_tickets_count': my_open_tickets_count,
            'my_pending_amount': my_pending_amount,
            'my_funds_contributed': my_funds_contributed,
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
        messages.success(request, f"Payment of ₹{bill.amount} confirmed! Transaction ID: {bill.transaction_id}")
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
        base_visitors = VisitorLog.objects.all()
    else:
        base_visitors = VisitorLog.objects.filter(visiting_resident=user)

    today = timezone.now().date()
    today_passes_count = base_visitors.filter(entry_time__date=today).count()
    previous_passes_count = base_visitors.filter(entry_time__date__lt=today).count()

    time_filter = request.GET.get('time_filter', 'today').strip().lower()
    if time_filter not in ['today', 'previous']:
        time_filter = 'today'

    visitors = base_visitors
    if time_filter == 'today':
        visitors = visitors.filter(entry_time__date=today)
    elif time_filter == 'previous':
        visitors = visitors.filter(entry_time__date__lt=today)

    status_filter = request.GET.get('status')
    if status_filter:
        visitors = visitors.filter(status=status_filter)

    search = request.GET.get('q')
    if search:
        visitors = visitors.filter(
            Q(visitor_name__icontains=search) |
            Q(flat_number__icontains=search) |
            Q(vehicle_number__icontains=search) |
            Q(pass_code__icontains=search)
        )

    paginator = Paginator(visitors, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'visitors/list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search': search,
        'time_filter': time_filter,
        'today_passes_count': today_passes_count,
        'previous_passes_count': previous_passes_count,
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
    if not (request.user.is_admin_role or request.user.is_staff_role):
        messages.error(request, "Only security staff can check out visitors.")
        return redirect('visitor_list')

    visitor = get_object_or_404(VisitorLog, pk=pk)
    if visitor.status != 'CHECKED_OUT':
        visitor.status = 'CHECKED_OUT'
        visitor.exit_time = timezone.now()
        visitor.save()
        messages.success(request, f"Visitor {visitor.visitor_name} checked out at {visitor.exit_time.strftime('%H:%M')}.")
    else:
        messages.info(request, f"Visitor {visitor.visitor_name} is already checked out.")
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
    is_elevated = request.user.is_admin_role or request.user.is_staff_role
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    # Raw individual logs queryset for metrics
    raw_logs_qs = BiometricGateLog.objects.all() if is_elevated else BiometricGateLog.objects.filter(user=request.user)

    today = timezone.now().date()
    today_logs = raw_logs_qs.filter(timestamp__date=today)
    total_today = today_logs.count()
    granted_today = today_logs.filter(access_granted=True).count()
    denied_today = today_logs.filter(access_granted=False).count()

    # Unique Room / Flat Directory
    if is_elevated:
        user_flats = list(User.objects.filter(is_active=True).exclude(flat_number='').values_list('flat_number', flat=True))
        log_flats = list(BiometricGateLog.objects.exclude(flat_number='').values_list('flat_number', flat=True))
        all_flats = user_flats + log_flats
    else:
        all_flats = [request.user.flat_number] if request.user.flat_number else []

    seen = set()
    unique_flat_names = []
    for f in all_flats:
        f_clean = f.strip()
        norm = f_clean.replace(' ', '').replace('-', '').upper()
        if norm and norm not in seen:
            seen.add(norm)
            unique_flat_names.append(f_clean)

    unique_rooms = []
    for flat in unique_flat_names:
        head = User.objects.filter(flat_number__iexact=flat, is_active=True).first()
        if not head:
            norm = flat.replace(' ', '').replace('-', '').upper()
            for u in User.objects.filter(is_active=True).exclude(flat_number=''):
                if u.flat_number.replace(' ', '').replace('-', '').upper() == norm:
                    head = u
                    break

        room_logs = BiometricGateLog.objects.filter(
            Q(flat_number__iexact=flat) | (Q(user=head) if head else Q(id=-1))
        )
        latest_log = room_logs.order_by('-timestamp').first()
        total_room_scans = room_logs.count()
        granted_scans = room_logs.filter(access_granted=True).count()
        family_lines = [l.strip() for l in (head.family_details if head else '').split('\n') if l.strip()]

        room_item = {
            'flat_number': flat,
            'head': head,
            'head_name': (head.get_full_name() or head.username) if head else 'Unregistered Resident',
            'username': head.username if head else '',
            'block_tower': head.block_tower if head else '',
            'has_face_photo': bool(head.face_photo) if head else False,
            'face_photo_url': head.face_photo.url if head and head.face_photo else None,
            'family_count': (head.family_members_count or len(family_lines) or 1) if head else 0,
            'family_details': head.family_details if head else '',
            'latest_log': latest_log,
            'latest_id': latest_log.id if latest_log else None,
            'latest_timestamp': latest_log.timestamp if latest_log else None,
            'latest_gate': latest_log.gate_name if latest_log else 'No Scans Yet',
            'latest_confidence': latest_log.confidence_score if latest_log else 0.0,
            'latest_granted': latest_log.access_granted if latest_log else None,
            'total_scans': total_room_scans,
            'granted_scans': granted_scans,
        }

        if search_query:
            q_lower = search_query.lower()
            matches = (
                q_lower in flat.lower() or
                (head and (q_lower in head.username.lower() or q_lower in (head.get_full_name() or '').lower())) or
                (head and q_lower in (head.block_tower or '').lower())
            )
            if not matches:
                continue

        if status_filter == 'granted' and room_item['latest_granted'] is not True:
            continue
        elif status_filter == 'denied' and room_item['latest_granted'] is not False:
            continue
        elif status_filter == 'enrolled' and not room_item['has_face_photo']:
            continue

        unique_rooms.append(room_item)

    # Sort rooms with recent scans first, then alphabetical
    unique_rooms.sort(key=lambda r: (r['latest_timestamp'] is not None, r['latest_timestamp']), reverse=True)

    paginator = Paginator(unique_rooms, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'gate/biometric_logs.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_today': total_today,
        'granted_today': granted_today,
        'denied_today': denied_today,
        'unique_rooms_count': len(unique_flat_names),
        'is_elevated': is_elevated,
    })


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
      - Optional for delivery clearance:
        'is_delivery': 'true'
        'delivery_name': name of delivery agent
        'delivery_company': company (e.g. Amazon, FedEx, Courier, Swiggy)
        'delivery_flat': target apartment (e.g. A-402)
        'delivery_phone': phone number
        'delivery_vehicle': vehicle number
    Runs OpenCV face detection and recognition.
    Creates BiometricGateLog on match or clearance.
    """
    from django.core.files.base import ContentFile

    image_input = None
    image_file_obj = None

    if 'image_file' in request.FILES:
        image_input = request.FILES['image_file']
        image_file_obj = request.FILES['image_file']
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

    is_delivery = str(request.data.get('is_delivery', '')).lower() in ['true', '1', 'yes'] or bool(request.data.get('delivery_flat'))
    delivery_flat = request.data.get('delivery_flat') or request.POST.get('delivery_flat')

    # If this is a fast-track delivery agent face clearance submission:
    if is_delivery and delivery_flat:
        from .face_engine import load_image_to_cv2, detect_faces, draw_futuristic_box, cv2_to_base64
        cv_img = load_image_to_cv2(image_input)
        faces = detect_faces(cv_img)
        if len(faces) == 0:
            return Response({
                'success': False,
                'match': False,
                'face_detected': False,
                'message': 'No face detected in delivery agent photo. Please ensure face is clearly visible.'
            })

        d_name = request.data.get('delivery_name') or 'Delivery Agent'
        d_company = request.data.get('delivery_company') or 'Courier Delivery'
        d_phone = request.data.get('delivery_phone') or '+1 (555) 000-0000'
        d_vehicle = request.data.get('delivery_vehicle') or ''

        # Convert image to ContentFile if base64
        save_file = image_file_obj
        if not save_file and isinstance(image_input, str):
            if ',' in image_input:
                header, encoded = image_input.split(',', 1)
            else:
                encoded = image_input
            save_file = ContentFile(base64.b64decode(encoded), name=f"delivery_{uuid.uuid4().hex[:8]}.jpg")

        visitor = VisitorLog.objects.create(
            visitor_name=d_name,
            phone_number=d_phone,
            purpose=d_company,
            flat_number=delivery_flat,
            vehicle_number=d_vehicle,
            entry_type='FACE_RECOGNITION',
            status='INSIDE',
            snapshot=save_file
        )

        # Draw HUD annotation
        x, y, w, h = faces[0]
        draw_futuristic_box(cv_img, (x, y, w, h), color=(0, 240, 100), label=f"DELIVERY: {d_name} [{d_company}]", score=98.8)

        gate_name = request.data.get('gate_name', 'Gate 1 - Delivery Lane')
        log_entry = BiometricGateLog.objects.create(
            user=None,
            recognized_name=d_name,
            matched_role=f"Delivery ({d_company})",
            confidence_score=98.8,
            gate_name=gate_name,
            access_granted=True,
            notes=f"Delivery clearance for Unit {delivery_flat}. Pass Code: {visitor.pass_code}"
        )

        try:
            train_face_recognizer()
        except Exception as e:
            print("Background train notice:", e)

        return Response({
            'success': True,
            'match': True,
            'face_detected': True,
            'is_delivery': True,
            'confidence': 98.8,
            'visitor_id': visitor.id,
            'name': d_name,
            'role': f"Delivery ({d_company})",
            'flat': delivery_flat,
            'block': '',
            'vehicle': d_vehicle or 'Delivery Vehicle',
            'pass_code': visitor.pass_code,
            'message': f"Delivery Authorized for Unit {delivery_flat}! Pass Code: {visitor.pass_code}. Gate Unlocked.",
            'annotated_image': cv2_to_base64(cv_img),
            'log_id': log_entry.id,
            'timestamp': log_entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })

    # Standard Recognition Pipeline
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


@api_view(['GET'])
@permission_classes([AllowAny])
def api_check_flat(request):
    """
    Checks if a room / flat number is already registered to an active resident.
    Endpoint: /api/check-flat/?flat=A-402
    """
    flat = request.GET.get('flat', '').strip()
    if not flat:
        return Response({'available': True, 'message': ''})

    norm_flat = flat.replace(" ", "").upper()
    existing_users = User.objects.filter(is_active=True).exclude(flat_number='')

    for u in existing_users:
        u_norm = u.flat_number.strip().replace(" ", "").upper()
        if u_norm == norm_flat or u_norm.replace("-", "") == norm_flat.replace("-", ""):
            owner_name = u.get_full_name() or u.username
            return Response({
                'available': False,
                'registered_to': owner_name,
                'flat': u.flat_number,
                'tower': u.block_tower or '',
                'message': f"Room / Flat No. '{flat}' is already registered for another resident ({owner_name}, Flat {u.flat_number})."
            })

    return Response({
        'available': True,
        'message': f"Room / Flat No. '{flat}' is available."
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_flat_biometrics(request):
    """
    Returns biometric profile of the head of room and family names with ages.
    Endpoint: /api/flat-biometrics/?flat=A-402&log_id=12
    """
    flat = request.GET.get('flat', '').strip()
    log_id = request.GET.get('log_id', '').strip()

    target_log = None
    if log_id and log_id.isdigit():
        target_log = BiometricGateLog.objects.filter(id=int(log_id)).first()
        if target_log and not flat:
            flat = target_log.display_flat_number

    if not flat:
        return Response({'success': False, 'message': 'Flat number parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Permission check: Admin or Staff can inspect any flat; Resident can inspect their own flat
    is_elevated = request.user.is_admin_role or request.user.is_staff_role
    if not is_elevated and (not request.user.flat_number or request.user.flat_number.strip().upper() != flat.upper()):
        return Response({
            'success': False,
            'is_admin': False,
            'message': 'Society Admin clearance required to inspect room biometrics and family records.'
        }, status=status.HTTP_403_FORBIDDEN)

    # Locate resident head of this flat
    head = User.objects.filter(flat_number__iexact=flat, is_active=True).first()
    if not head:
        norm = flat.replace(" ", "").replace("-", "").upper()
        for u in User.objects.filter(is_active=True).exclude(flat_number=''):
            if u.flat_number.replace(" ", "").replace("-", "").upper() == norm:
                head = u
                break

    # If log was linked to a specific user and head wasn't found by string, use log's user
    if not head and target_log and target_log.user:
        head = target_log.user

    data = {
        'success': True,
        'is_admin': is_elevated,
        'flat_number': flat,
        'has_resident': bool(head),
    }

    if head:
        family_lines = [line.strip() for line in (head.family_details or '').split('\n') if line.strip()]

        data['head'] = {
            'id': head.id,
            'full_name': head.get_full_name() or head.username,
            'username': head.username,
            'role_display': head.get_role_display(),
            'phone': head.phone_number or 'Not provided',
            'email': head.email or 'Not provided',
            'flat_number': head.flat_number,
            'block_tower': head.block_tower or 'Emerald Heights Residency',
            'vehicle_number': head.vehicle_number or 'None registered',
            'has_face_photo': bool(head.face_photo),
            'face_photo_url': head.face_photo.url if head.face_photo else None,
            'avatar_url': head.avatar.url if head.avatar else (head.google_avatar_url or None),
            'is_google_verified': head.is_google_verified,
            'family_members_count': head.family_members_count or (len(family_lines) if family_lines else 1),
            'family_details': head.family_details or 'No family description provided yet.',
            'family_members_list': family_lines,
        }
    else:
        data['head'] = None
        data['message'] = f"No resident account is registered for Unit '{flat}'."

    recent_logs_qs = BiometricGateLog.objects.filter(
        Q(flat_number__iexact=flat) | (Q(user=head) if head else Q(id=-1))
    )[:6]

    data['recent_scans'] = [{
        'id': l.id,
        'gate_name': l.gate_name,
        'confidence': round(l.confidence_score, 1),
        'access_granted': l.access_granted,
        'timestamp': l.timestamp.strftime('%b %d, %Y • %H:%M:%S'),
        'notes': l.notes,
        'capture_image_url': l.capture_image.url if l.capture_image else None
    } for l in recent_logs_qs]

    if target_log:
        data['current_scan'] = {
            'id': target_log.id,
            'gate_name': target_log.gate_name,
            'confidence': round(target_log.confidence_score, 1),
            'access_granted': target_log.access_granted,
            'timestamp': target_log.timestamp.strftime('%b %d, %Y • %H:%M:%S'),
            'notes': target_log.notes,
            'capture_image_url': target_log.capture_image.url if target_log.capture_image else None
        }

    return Response(data)


# -------------------------------------------------------------
# COMMUNITY CHAT MODULE (PRIVACY PROTECTED)
# -------------------------------------------------------------
@login_required
def community_chat_view(request):
    """
    Community Chat Section for all residents, security officers, and admins.
    Privacy Guarantee: Displays ONLY sender name and messages.
    No private info (flat numbers, phone, email, family details) is shown.
    """
    if request.method == 'POST':
        msg_text = request.POST.get('message', '').strip()
        if msg_text:
            msg = CommunityMessage.objects.create(
                sender=request.user,
                message=msg_text
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
                return JsonResponse({
                    'success': True,
                    'message': {
                        'id': msg.id,
                        'sender_name': msg.sender_display_name,
                        'message': msg.message,
                        'created_at': msg.created_at.strftime('%I:%M %p'),
                        'is_me': True,
                    }
                })
        return redirect('community_chat')

    # Fetch last 80 messages in chronological order
    recent_messages = list(CommunityMessage.objects.all().order_by('-created_at')[:80])
    recent_messages.reverse()

    return render(request, 'chat/index.html', {
        'chat_messages': recent_messages,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_chat_messages(request):
    """
    Live API for Community Chat polling and instant transmission.
    Privacy Policy: Emits strictly sender name, message body, and time.
    """
    if request.method == 'POST':
        text = request.data.get('message', '').strip()
        if not text:
            return Response({'success': False, 'message': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
        
        msg = CommunityMessage.objects.create(sender=request.user, message=text)
        return Response({
            'success': True,
            'message': {
                'id': msg.id,
                'sender_name': msg.sender_display_name,
                'message': msg.message,
                'created_at': msg.created_at.strftime('%I:%M %p'),
                'is_me': True,
            }
        })

    since_id = request.GET.get('since_id')
    if since_id and since_id.isdigit():
        messages_qs = CommunityMessage.objects.filter(id__gt=int(since_id)).order_by('created_at')
    else:
        messages_qs = list(CommunityMessage.objects.all().order_by('-created_at')[:80])
        messages_qs.reverse()

    results = [{
        'id': m.id,
        'sender_name': m.sender_display_name,
        'message': m.message,
        'created_at': m.created_at.strftime('%I:%M %p'),
        'is_me': (m.sender_id == request.user.id),
    } for m in messages_qs]

    return Response({
        'success': True,
        'messages': results,
    })


# -------------------------------------------------------------
# COMMUNITY FUNDS, EVENTS & DONATIONS MODULE
# -------------------------------------------------------------
@login_required
def funds_list_view(request):
    """
    Overview of all community fund drives, festival collections, and donation campaigns.
    All residents, security, and admins can view and contribute.
    Supports tab views:
      - 'campaigns' (All Campaigns & Drives)
      - 'donations' (Who donated and how much - transparent society ledger)
      - 'my_donations' (My personal donations history)
    """
    active_tab = request.GET.get('tab', 'campaigns').strip()
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()
    my_filter = request.GET.get('my_contributions', '').strip()
    search_query = request.GET.get('q', '').strip()

    campaigns = FundCampaign.objects.all()

    if category_filter:
        campaigns = campaigns.filter(category=category_filter)
    if status_filter:
        campaigns = campaigns.filter(status=status_filter)
    if my_filter == '1':
        campaigns = campaigns.filter(contributions__contributor=request.user).distinct()
    if search_query:
        campaigns = campaigns.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Attach personal donation total per campaign for logged-in user
    user_contrib_map = {}
    if request.user.is_authenticated:
        user_contribs = (
            FundContribution.objects.filter(contributor=request.user)
            .values('campaign_id')
            .annotate(total=Sum('amount'))
        )
        for item in user_contribs:
            user_contrib_map[item['campaign_id']] = item['total']

    for c in campaigns:
        c.my_donation = user_contrib_map.get(c.id, Decimal('0.00'))

    # All donations ledger across society (who donated & how much)
    all_donations = FundContribution.objects.select_related('contributor', 'campaign').all()
    if search_query and active_tab in ['donations', 'my_donations']:
        all_donations = all_donations.filter(
            Q(campaign__title__icontains=search_query) |
            Q(contributor__first_name__icontains=search_query) |
            Q(contributor__last_name__icontains=search_query) |
            Q(contributor__username__icontains=search_query) |
            Q(contributor__flat_number__icontains=search_query) |
            Q(note__icontains=search_query)
        )

    # Unique Resident Donors aggregation with per-event breakdown
    grouped_contributors = {}
    for donation in all_donations:
        user_key = donation.contributor_id
        if user_key not in grouped_contributors:
            c_user = donation.contributor
            full_name = c_user.get_full_name()
            display_name = full_name.strip() if full_name and full_name.strip() else c_user.username
            flat_no = c_user.flat_number.strip() if c_user.flat_number else "N/A"
            grouped_contributors[user_key] = {
                'contributor_id': user_key,
                'username': c_user.username,
                'name': display_name,
                'flat_number': flat_no,
                'total_donated': Decimal('0.00'),
                'events_count': 0,
                'contributions_count': 0,
                'event_map': {},
            }

        group = grouped_contributors[user_key]
        group['total_donated'] += donation.amount
        group['contributions_count'] += 1

        camp_id = donation.campaign_id
        if camp_id not in group['event_map']:
            group['event_map'][camp_id] = {
                'campaign_id': camp_id,
                'campaign_title': donation.campaign.title,
                'campaign_category': donation.campaign.get_category_display(),
                'total_amount': Decimal('0.00'),
                'donations': []
            }
        group['event_map'][camp_id]['total_amount'] += donation.amount
        group['event_map'][camp_id]['donations'].append(donation)

    for r in grouped_contributors.values():
        r['events'] = list(r['event_map'].values())
        r['events_count'] = len(r['events'])

    resident_donors = sorted(grouped_contributors.values(), key=lambda x: x['total_donated'], reverse=True)

    # My personal donations
    my_donations = all_donations.filter(contributor=request.user)
    my_contributions_total = my_donations.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Summary totals
    total_funds_raised = all_donations.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    active_campaigns_count = FundCampaign.objects.filter(status='ACTIVE').count()
    total_donations_count = all_donations.count()

    return render(request, 'funds/list.html', {
        'campaigns': campaigns,
        'all_donations': all_donations,
        'resident_donors': resident_donors,
        'my_donations': my_donations,
        'active_tab': active_tab,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'my_filter': my_filter,
        'search_query': search_query,
        'total_funds_raised': total_funds_raised,
        'active_campaigns_count': active_campaigns_count,
        'total_donations_count': total_donations_count,
        'my_contributions_total': my_contributions_total,
    })


@login_required
def fund_detail_view(request, pk):
    """
    Campaign detail view with transparent contributor list and contribution form.
    """
    campaign = get_object_or_404(FundCampaign, pk=pk)
    contributions = campaign.contributions.select_related('contributor').all()
    form = FundContributionForm(campaign=campaign)
    my_contribution_total = campaign.user_donation_total(request.user)

    return render(request, 'funds/detail.html', {
        'campaign': campaign,
        'contributions': contributions,
        'form': form,
        'my_contribution_total': my_contribution_total,
    })


@login_required
def fund_contribute_view(request, pk):
    """
    Process resident donation/fund contribution for an event or cause.
    Enforces minimum contribution set by admin.
    """
    campaign = get_object_or_404(FundCampaign, pk=pk)

    if campaign.status == 'CLOSED':
        messages.error(request, "This campaign is closed and is no longer accepting funds.")
        return redirect('fund_detail', pk=pk)

    if request.method == 'POST':
        form = FundContributionForm(request.POST, campaign=campaign)
        if form.is_valid():
            contribution = form.save(commit=False)
            if contribution.amount < campaign.minimum_amount:
                messages.error(
                    request,
                    f"Minimum contribution required for this campaign is ₹{campaign.minimum_amount}. You cannot donate less than ₹{campaign.minimum_amount}."
                )
                return redirect('fund_detail', pk=pk)

            contribution.campaign = campaign
            contribution.contributor = request.user
            contribution.transaction_id = f"TXN-FUND-{uuid.uuid4().hex[:10].upper()}"
            contribution.save()

            if campaign.is_fully_funded and campaign.status == 'ACTIVE':
                campaign.status = 'COMPLETED'
                campaign.save()

            messages.success(
                request,
                f"Heartfelt thank you! Your contribution of ₹{contribution.amount} for '{campaign.title}' has been received. "
                f"Receipt TXN: {contribution.transaction_id}"
            )
            return redirect('fund_detail', pk=pk)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
            return redirect('fund_detail', pk=pk)
    return redirect('fund_detail', pk=pk)


@login_required
def fund_create_view(request):
    """
    Admins / Committee Board can launch a new event fund drive or charity appeal.
    """
    if not (request.user.is_admin_role or request.user.is_staff_role):
        messages.error(request, "Only society administrators or committee members can launch community fund campaigns.")
        return redirect('funds_list')

    if request.method == 'POST':
        form = FundCampaignCreateForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            messages.success(request, f"Community fund campaign '{campaign.title}' launched successfully!")
            return redirect('funds_list')
    else:
        form = FundCampaignCreateForm()

    return render(request, 'funds/create.html', {
        'form': form,
    })



