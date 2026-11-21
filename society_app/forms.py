from django import forms
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import (
    SocietyNotice, ComplaintTicket, TicketComment, VisitorLog, MaintenanceBill,
    FundCampaign, FundContribution
)

User = get_user_model()


class ResidentRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Create strong password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm password'}))
    role_code = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter role authorization code',
            'id': 'id_role_code',
            'autocomplete': 'off',
        })
    )
    lives_here = forms.ChoiceField(
        choices=(
            ('no', 'No - I do not live here'),
            ('yes', 'Yes - I live on premises'),
        ),
        required=False,
        initial='no',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_lives_here',
        })
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 'role',
            'lives_here', 'phone_number', 'flat_number', 'block_tower',
            'family_members_count', 'family_details',
            'vehicle_number', 'face_photo', 'avatar'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Username (e.g. john_doe)'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'name@example.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
            'role': forms.Select(attrs={'class': 'form-select', 'id': 'id_role'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+1 (555) 000-0000'}),
            'flat_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Flat/Unit (e.g. A-402)', 'id': 'id_flat_number'}),
            'block_tower': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Tower / Block (e.g. Tower 1)'}),
            'family_members_count': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Total family members count (e.g. 3)',
                'min': '1',
                'id': 'id_family_members_count'
            }),
            'family_details': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter family member names & ages:\ne.g.\nJane Doe - Age 34 (Spouse)\nTommy Doe - Age 8 (Child)',
                'rows': 3,
                'id': 'id_family_details'
            }),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Vehicle Plate No (Optional)'}),
            'face_photo': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
            'avatar': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        }

    def clean_lives_here(self):
        val = self.data.get('lives_here', 'no')
        if isinstance(val, bool):
            return val
        return str(val).lower() in ['yes', 'true', '1']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user account with this email address already exists. Please sign in instead.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken. Please choose another username.")
        return username

    def clean_flat_number(self):
        flat = self.cleaned_data.get('flat_number', '').strip()
        role = self.data.get('role', 'RESIDENT')
        lives_here_val = str(self.data.get('lives_here', 'yes')).lower()

        if role == 'STAFF':
            # Security Gate Officer: if they do not live here, flat & tower are not required
            if lives_here_val in ['no', 'false', '0']:
                return "Security Gatehouse"
            else:
                if not flat:
                    raise forms.ValidationError("Please specify your residential Flat / Unit Number since you live on premises.")
        elif role == 'ADMIN':
            if not flat:
                return "Admin Office"
        elif role == 'RESIDENT':
            if not flat:
                raise forms.ValidationError("Room / Flat Number is required for resident registration.")

        norm_flat = flat.replace(" ", "").upper()
        existing_users = User.objects.filter(is_active=True).exclude(flat_number='')

        for u in existing_users:
            u_norm = u.flat_number.strip().replace(" ", "").upper()
            if u_norm == norm_flat or u_norm.replace("-", "") == norm_flat.replace("-", ""):
                owner_name = u.get_full_name() or u.username
                raise forms.ValidationError(
                    f"Room / Flat No. '{flat}' is already registered for another resident ({owner_name}, Flat {u.flat_number}). If you believe this is an error, please contact society management."
                )
        return flat

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match.')

        role = cleaned_data.get('role', 'RESIDENT')
        role_code = cleaned_data.get('role_code', '').strip()

        staff_code = getattr(settings, 'STAFF_ACCESS_CODE', 'security01')
        admin_code = getattr(settings, 'ADMIN_ACCESS_CODE', 'admin01')

        if role == 'RESIDENT':
            fam_count = cleaned_data.get('family_members_count')
            if fam_count is None or fam_count < 1:
                self.add_error('family_members_count', "Resident member registration requires family number (at least 1 member).")
            else:
                # Check for dynamic member_name_i and member_age_i from POST data
                member_lines = []
                missing_fields = []
                has_dynamic_fields = any(f'member_name_{i}' in self.data for i in range(1, fam_count + 1))

                if has_dynamic_fields:
                    for i in range(1, fam_count + 1):
                        name = self.data.get(f'member_name_{i}', '').strip()
                        age = self.data.get(f'member_age_{i}', '').strip()
                        if not name and not age:
                            missing_fields.append(f"Member {i} (Name & Age)")
                        elif not name:
                            missing_fields.append(f"Member {i} Name")
                        elif not age:
                            missing_fields.append(f"Member {i} Age")
                        else:
                            member_lines.append(f"{name} - Age {age}")

                    if missing_fields:
                        self.add_error('family_details', f"Please complete all member fields: missing {', '.join(missing_fields)}.")
                    elif member_lines:
                        cleaned_data['family_details'] = "\n".join(member_lines)
                else:
                    fam_details = (cleaned_data.get('family_details') or '').strip()
                    if not fam_details:
                        self.add_error('family_details', "Resident member registration requires description of family members with name and age.")
                    else:
                        cleaned_data['family_details'] = fam_details
        elif role == 'STAFF':
            if not role_code:
                self.add_error('role_code', f"Security Gate Officer / Staff registration requires authorization code (like '{staff_code}').")
            elif role_code != staff_code:
                self.add_error('role_code', f"Invalid security staff code. Authorized code is '{staff_code}'.")
        elif role == 'ADMIN':
            if not role_code:
                self.add_error('role_code', f"Society Admin / Committee Board registration requires authorization code (like '{admin_code}').")
            elif role_code != admin_code:
                self.add_error('role_code', f"Invalid society admin code. Authorized code is '{admin_code}'.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        lives_here_val = str(self.cleaned_data.get('lives_here', 'yes')).lower()

        if user.role == 'ADMIN':
            user.is_staff = True
            user.is_superuser = True
            user.lives_here = True
        elif user.role == 'STAFF':
            user.is_staff = True
            user.is_superuser = False
            if lives_here_val in ['no', 'false', '0']:
                user.lives_here = False
                user.flat_number = "Security Gatehouse"
                if not user.block_tower:
                    user.block_tower = "Security Post"
            else:
                user.lives_here = True
        else:
            user.is_staff = False
            user.is_superuser = False
            user.lives_here = True

        if commit:
            user.save()
        return user


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone_number',
            'flat_number', 'block_tower', 'lives_here', 'family_members_count', 'family_details',
            'vehicle_number', 'emergency_contact', 'avatar', 'face_photo'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'flat_number': forms.TextInput(attrs={'class': 'form-input'}),
            'block_tower': forms.TextInput(attrs={'class': 'form-input'}),
            'lives_here': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'family_members_count': forms.NumberInput(attrs={'class': 'form-input', 'min': '1'}),
            'family_details': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Family members name and age...'}),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-input'}),
            'avatar': forms.FileInput(attrs={'class': 'form-file'}),
            'face_photo': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
        }

    def clean_flat_number(self):
        flat = self.cleaned_data.get('flat_number', '').strip()
        if not flat:
            return flat

    def clean(self):
        cleaned_data = super().clean()
        fam_count = cleaned_data.get('family_members_count')
        if fam_count and fam_count >= 1:
            member_lines = []
            has_dynamic_fields = any(f'member_name_{i}' in self.data for i in range(1, fam_count + 1))
            if has_dynamic_fields:
                for i in range(1, fam_count + 1):
                    name = self.data.get(f'member_name_{i}', '').strip()
                    age = self.data.get(f'member_age_{i}', '').strip()
                    if name and age:
                        member_lines.append(f"{name} - Age {age}")
                if member_lines:
                    cleaned_data['family_details'] = "\n".join(member_lines)
        return cleaned_data

        norm_flat = flat.replace(" ", "").upper()
        existing_users = User.objects.filter(is_active=True).exclude(pk=self.instance.pk).exclude(flat_number='')

        for u in existing_users:
            u_norm = u.flat_number.strip().replace(" ", "").upper()
            if u_norm == norm_flat or u_norm.replace("-", "") == norm_flat.replace("-", ""):
                owner_name = u.get_full_name() or u.username
                raise forms.ValidationError(
                    f"Room / Flat No. '{flat}' is already registered for another resident ({owner_name}, Flat {u.flat_number})."
                )
        return flat

    def clean(self):
        cleaned_data = super().clean()
        fam_count = cleaned_data.get('family_members_count')
        if fam_count and fam_count >= 1:
            member_lines = []
            has_dynamic_fields = any(f'member_name_{i}' in self.data for i in range(1, fam_count + 1))
            if has_dynamic_fields:
                for i in range(1, fam_count + 1):
                    name = self.data.get(f'member_name_{i}', '').strip()
                    age = self.data.get(f'member_age_{i}', '').strip()
                    if name and age:
                        member_lines.append(f"{name} - Age {age}")
                if member_lines:
                    cleaned_data['family_details'] = "\n".join(member_lines)
        return cleaned_data


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
        fields = ['resident', 'amount', 'due_date']
        widgets = {
            'resident': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Amount in ₹'}),
            'due_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.month:
            if instance.due_date:
                instance.month = instance.due_date.strftime("%B %Y")
            else:
                instance.month = timezone.now().strftime("%B %Y")
        if commit:
            instance.save()
        return instance


class FundCampaignCreateForm(forms.ModelForm):
    class Meta:
        model = FundCampaign
        fields = ['title', 'category', 'target_amount', 'minimum_amount', 'end_date', 'description', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Diwali & Cultural Night Festival 2026'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'target_amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Target in ₹ (e.g. 50000.00)', 'min': '1', 'step': '1'}),
            'minimum_amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Minimum contribution in ₹ (e.g. 500.00)', 'min': '1', 'step': '1'}),
            'end_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Describe the event, budget allocation, schedule, and purpose of funds...'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class FundContributionForm(forms.ModelForm):
    def __init__(self, *args, campaign=None, **kwargs):
        self.campaign = campaign
        super().__init__(*args, **kwargs)
        if self.campaign and self.campaign.minimum_amount:
            self.fields['amount'].widget.attrs['min'] = str(self.campaign.minimum_amount)
            self.fields['amount'].widget.attrs['placeholder'] = f"Min ₹{self.campaign.minimum_amount} (e.g. {self.campaign.minimum_amount})"
            self.fields['amount'].help_text = f"Minimum contribution required: ₹{self.campaign.minimum_amount}"

    class Meta:
        model = FundContribution
        fields = ['amount', 'payment_method', 'note', 'is_anonymous']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Contribution amount in ₹ (e.g. 500.00)', 'min': '1', 'step': '1'}),
            'payment_method': forms.Select(choices=(
                ('Instant UPI / GPay / PhonePe', 'Instant UPI (Google Pay / PhonePe / Paytm)'),
                ('Credit / Debit Card', 'Credit / Debit Card (Visa / Mastercard)'),
                ('Net Banking', 'Net Banking Portal'),
                ('Cash / Desk Deposit', 'Direct Cash / Desk Deposit'),
            ), attrs={'class': 'form-select'}),
            'note': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Optional wishing message or note (e.g. Best wishes from Flat A-402!)'}),
            'is_anonymous': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and self.campaign:
            if amount < self.campaign.minimum_amount:
                raise forms.ValidationError(
                    f"Minimum contribution required for this drive is ₹{self.campaign.minimum_amount}. You cannot donate below ₹{self.campaign.minimum_amount}."
                )
        return amount

