from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile, HostProfile, CoHostProfile, MarketplaceListing


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    role = forms.ChoiceField(choices=UserProfile.USER_ROLES, required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2", "phone_number", "role")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
            # Create user profile
            user_profile = UserProfile.objects.create(
                user=user,
                phone_number=self.cleaned_data["phone_number"],
                role=self.cleaned_data["role"]
            )
            # Create role-specific profile
            if user_profile.role == 'host':
                HostProfile.objects.create(user_profile=user_profile)
            elif user_profile.role == 'cohost':
                CoHostProfile.objects.create(user_profile=user_profile)
        return user


class HostProfileForm(forms.ModelForm):
    class Meta:
        model = HostProfile
        fields = ['bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }


class CoHostProfileForm(forms.ModelForm):
    class Meta:
        model = CoHostProfile
        fields = ['bio', 'locations', 'experience_years', 'hourly_rate']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'locations': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., New York, Los Angeles, Miami'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'hourly_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


class AddListingForm(forms.ModelForm):
    airbnb_url = forms.URLField(
        label="Airbnb Listing URL",
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://www.airbnb.com/rooms/12345678'
        })
    )
    
    class Meta:
        model = MarketplaceListing
        fields = ['airbnb_url', 'description', 'co_host_requirements']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Describe your property and what makes it special...'
            }),
            'co_host_requirements': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'What are you looking for in a co-host? Experience level, availability, etc.'
            }),
        }


class ProposalForm(forms.Form):
    RATE_TYPE_CHOICES = [
        ('', 'Select rate type'),
        ('fixed', 'Fixed Rate ($/day)'),
        ('percentage', 'Percentage of Revenue (%)'),
    ]

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'form-control',
            'placeholder': 'Introduce yourself and explain why you would be a great co-host for this property...'
        }),
        label="Your Proposal Message"
    )

    tasks = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'tasks_hidden'}),
        label="Selected Tasks"
    )

    rate_type = forms.ChoiceField(
        choices=RATE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'rate_type_select'
        }),
        label="Rate Structure (Optional)"
    )

    offered_rate = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Enter rate',
            'id': 'rate_input'
        }),
        label="Your Rate"
    )


class EditProposalForm(forms.Form):
    RATE_TYPE_CHOICES = [
        ('', 'Select rate type'),
        ('fixed', 'Fixed Rate ($/day)'),
        ('percentage', 'Percentage of Revenue (%)'),
    ]

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'form-control',
            'placeholder': 'Introduce yourself and explain why you would be a great co-host for this property...'
        }),
        label="Your Proposal Message"
    )

    tasks = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'tasks_hidden'}),
        label="Selected Tasks"
    )

    rate_type = forms.ChoiceField(
        choices=RATE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'rate_type_select'
        }),
        label="Rate Structure (Optional)"
    )

    offered_rate = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Enter rate',
            'id': 'rate_input'
        }),
        label="Your Rate"
    )


class MessageForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Type your message here...'
        }),
        label=""
    )


class ReviewForm(forms.Form):
    RATING_CHOICES = [
        (5, '5 stars'),
        (4, '4 stars'),
        (3, '3 stars'),
        (2, '2 stars'),
        (1, '1 star'),
    ]
    rating = forms.ChoiceField(choices=RATING_CHOICES, widget=forms.RadioSelect, label="Rating")
    comment = forms.CharField(
        max_length=1000, required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Share your experience working together...'}),
        label="Review"
    )


class UserInfoForm(forms.Form):
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 555 000 0000'})
    )
    profile_photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )