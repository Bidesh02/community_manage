from rest_framework import serializers
from .models import User, SocietyNotice, ComplaintTicket, TicketComment, MaintenanceBill, VisitorLog, BiometricGateLog


class UserSummarySerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'role', 'role_display', 'flat_number', 'block_tower', 'phone_number', 'avatar', 'vehicle_number']


class SocietyNoticeSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = SocietyNotice
        fields = ['id', 'title', 'content', 'category', 'category_display', 'is_pinned', 'author', 'author_name', 'attachment', 'created_at']


class TicketCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = TicketComment
        fields = ['id', 'ticket', 'author', 'author_name', 'message', 'created_at']


class ComplaintTicketSerializer(serializers.ModelSerializer):
    resident_name = serializers.CharField(source='resident.get_full_name', read_only=True)
    resident_flat = serializers.CharField(source='resident.flat_number', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    comments = TicketCommentSerializer(many=True, read_only=True)

    class Meta:
        model = ComplaintTicket
        fields = [
            'id', 'ticket_number', 'resident', 'resident_name', 'resident_flat',
            'title', 'description', 'category', 'category_display',
            'priority', 'priority_display', 'status', 'status_display',
            'attachment', 'assigned_staff', 'resolution_notes', 'created_at', 'resolved_at', 'comments'
        ]


class MaintenanceBillSerializer(serializers.ModelSerializer):
    resident_name = serializers.CharField(source='resident.get_full_name', read_only=True)
    resident_flat = serializers.CharField(source='resident.flat_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MaintenanceBill
        fields = ['id', 'bill_number', 'resident', 'resident_name', 'resident_flat', 'month', 'amount', 'due_date', 'status', 'status_display', 'paid_date', 'payment_method', 'transaction_id']


class VisitorLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    entry_type_display = serializers.CharField(source='get_entry_type_display', read_only=True)

    class Meta:
        model = VisitorLog
        fields = ['id', 'visitor_name', 'phone_number', 'purpose', 'visiting_resident', 'flat_number', 'vehicle_number', 'entry_type', 'entry_type_display', 'status', 'status_display', 'entry_time', 'exit_time', 'pass_code']


class BiometricGateLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiometricGateLog
        fields = ['id', 'user', 'recognized_name', 'matched_role', 'confidence_score', 'gate_name', 'timestamp', 'access_granted', 'notes']
