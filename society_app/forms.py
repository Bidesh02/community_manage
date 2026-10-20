from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import SocietyNotice, ComplaintTicket, TicketComment, VisitorLog, MaintenanceBill

User = get_user_model()


class ResidentRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Create strong password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm password'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'flat_number', 'block_tower', 'vehicle_number', 'face_photo', 'avatar']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username (e.g. john_doe)'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'name@example.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+1 (555) 000-0000'}),
            'flat_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Flat/Unit (e.g. A-402)'}),
            'block_tower': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Tower / Block (e.g. Tower 1)'}),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Vehicle Plate No (Optional)'}),
            'face_photo': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
            'avatar': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'flat_number', 'block_tower', 'vehicle_number', 'emergency_contact', 'avatar', 'face_photo']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'flat_number': forms.TextInput(attrs={'class': 'form-input'}),
            'block_tower': forms.TextInput(attrs={'class': 'form-input'}),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-input'}),
            'avatar': forms.FileInput(attrs={'class': 'form-file'}),
            'face_photo': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        }


class ComplaintTicketForm(forms.ModelForm):
    class Meta:
        model = ComplaintTicket
        fields = ['title', 'category', 'priority', 'description', 'attachment']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Brief summary (e.g. Pipe leakage under kitchen sink)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Detailed description of the issue...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        }


class TicketStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = ComplaintTicket
        fields = ['status', 'assigned_staff', 'resolution_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_staff': forms.Select(attrs={'class': 'form-select'}),
            'resolution_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Notes on repair actions, technician schedule, or completion details...'}),
        }


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Add a response or update...'}),
        }


class SocietyNoticeForm(forms.ModelForm):
    class Meta:
        model = SocietyNotice
        fields = ['title', 'category', 'is_pinned', 'content', 'attachment']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Announcement Title'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'content': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 5, 'placeholder': 'Write announcement details here...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-file'}),
        }


class VisitorCheckinForm(forms.ModelForm):
    class Meta:
        model = VisitorLog
        fields = ['visitor_name', 'phone_number', 'purpose', 'flat_number', 'visiting_resident', 'vehicle_number', 'entry_type']
        widgets = {
            'visitor_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Phone Number'}),
            'purpose': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Guest / Amazon Delivery / Plumbing'}),
            'flat_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Target Flat (e.g. A-402)'}),
            'visiting_resident': forms.Select(attrs={'class': 'form-select'}),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Vehicle Plate No (Optional)'}),
            'entry_type': forms.Select(attrs={'class': 'form-select'}),
        }


class MaintenanceBillCreateForm(forms.ModelForm):
    class Meta:
        model = MaintenanceBill
        fields = ['resident', 'month', 'amount', 'due_date']
        widgets = {
            'resident': forms.Select(attrs={'class': 'form-select'}),
            'month': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. November 2026'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Amount in $'}),
            'due_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }
