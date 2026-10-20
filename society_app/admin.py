from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SocietyNotice, ComplaintTicket, TicketComment, MaintenanceBill, VisitorLog, BiometricGateLog


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'role', 'flat_number', 'block_tower', 'phone_number', 'is_active')
    list_filter = ('role', 'block_tower', 'is_staff', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Society Resident Info', {
            'fields': ('role', 'phone_number', 'flat_number', 'block_tower', 'avatar', 'face_photo', 'face_encoding', 'vehicle_number', 'emergency_contact', 'is_verified_resident'),
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Society Resident Info', {
            'fields': ('role', 'phone_number', 'flat_number', 'block_tower', 'vehicle_number'),
        }),
    )


@admin.register(SocietyNotice)
class SocietyNoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_pinned', 'author', 'created_at')
    list_filter = ('category', 'is_pinned', 'created_at')
    search_fields = ('title', 'content')


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 1


@admin.register(ComplaintTicket)
class ComplaintTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'title', 'resident', 'category', 'priority', 'status', 'assigned_staff', 'created_at')
    list_filter = ('category', 'priority', 'status', 'created_at')
    search_fields = ('ticket_number', 'title', 'description', 'resident__username', 'resident__flat_number')
    inlines = [TicketCommentInline]


@admin.register(MaintenanceBill)
class MaintenanceBillAdmin(admin.ModelAdmin):
    list_display = ('bill_number', 'resident', 'month', 'amount', 'due_date', 'status', 'paid_date')
    list_filter = ('status', 'month', 'due_date')
    search_fields = ('bill_number', 'resident__username', 'resident__flat_number', 'transaction_id')


@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display = ('visitor_name', 'phone_number', 'purpose', 'flat_number', 'entry_type', 'status', 'entry_time', 'exit_time')
    list_filter = ('entry_type', 'status', 'entry_time')
    search_fields = ('visitor_name', 'phone_number', 'flat_number', 'vehicle_number', 'pass_code')


@admin.register(BiometricGateLog)
class BiometricGateLogAdmin(admin.ModelAdmin):
    list_display = ('recognized_name', 'matched_role', 'confidence_score', 'gate_name', 'timestamp', 'access_granted')
    list_filter = ('matched_role', 'access_granted', 'gate_name', 'timestamp')
    search_fields = ('recognized_name', 'notes')
