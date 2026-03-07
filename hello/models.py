from django.db import models
from django.contrib.auth.models import User
import os
from django.utils import timezone

class AirbnbListing(models.Model):
    title = models.CharField(max_length=500)
    location = models.CharField(max_length=200)
    price = models.CharField(max_length=100)
    rating = models.CharField(max_length=50, blank=True)
    listing_url = models.URLField(max_length=1000)
    image_url = models.URLField(max_length=1000, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)
    search_location = models.CharField(max_length=200)
    
    def __str__(self):
        return f"{self.title} - {self.location}"
    
    class Meta:
        ordering = ['-scraped_at']

class DetailedAirbnbListing(models.Model):
    title = models.CharField(max_length=500)
    main_photo_url = models.URLField(max_length=1000, blank=True)
    listing_url = models.URLField(max_length=1000, unique=True)
    
    # Host information
    host_name = models.CharField(max_length=200, blank=True)
    host_id = models.CharField(max_length=100, blank=True)
    host_profile_url = models.URLField(max_length=1000, blank=True)
    host_photo_url = models.URLField(max_length=1000, blank=True)
    host_verified = models.BooleanField(default=False)
    host_superhost = models.BooleanField(default=False)
    host_years_hosting = models.CharField(max_length=50, blank=True)
    host_reviews_count = models.CharField(max_length=50, blank=True)
    host_response_rate = models.CharField(max_length=50, blank=True)
    host_response_time = models.CharField(max_length=100, blank=True)
    host_languages = models.TextField(blank=True)
    host_description = models.TextField(blank=True)
    host_location = models.CharField(max_length=200, blank=True)
    host_joined_date = models.CharField(max_length=100, blank=True)
    
    
    # Additional details
    property_type = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)
    guests_capacity = models.CharField(max_length=50, blank=True)
    bedrooms = models.CharField(max_length=50, blank=True)
    bathrooms = models.CharField(max_length=50, blank=True)
    
    scraped_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title[:50]}... - {self.host_name}"
    
    class Meta:
        ordering = ['-scraped_at']


# User Profile Models for Marketplace
class UserProfile(models.Model):
    USER_ROLES = [
        ('host', 'Host'),
        ('cohost', 'Co-Host'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=USER_ROLES)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    restrict_messaging = models.BooleanField(
        default=False,
        help_text="When enabled, only users with an active proposal or partnership can message you."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class HostProfile(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, help_text="Tell co-hosts about yourself and your properties")
    total_listings = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Host: {self.user_profile.user.get_full_name() or self.user_profile.user.username}"


class CoHostProfile(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, help_text="Describe your co-hosting experience and services")
    locations = models.CharField(max_length=500, help_text="Cities/areas where you can co-host")
    airbnb_profile_url = models.URLField(blank=True, help_text="Your Airbnb host profile URL")
    experience_years = models.IntegerField(default=0, help_text="Years of co-hosting experience")
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Your daily rate (optional)")
    capabilities = models.ManyToManyField('Task', blank=True, related_name='cohost_profiles', help_text="Tasks/services you offer")
    
    def __str__(self):
        return f"Co-Host: {self.user_profile.user.get_full_name() or self.user_profile.user.username}"


# Enhanced Listing Model for Marketplace
class MarketplaceListing(models.Model):
    STATUS_CHOICES = [
        ('looking', 'Looking for Co-Host'),
        ('reviewing', 'Reviewing Proposals'),
        ('found', 'Co-Host Found'),
        ('paused', 'Paused'),
    ]
    
    # Link to host
    host = models.ForeignKey(HostProfile, on_delete=models.CASCADE, related_name='marketplace_listings')
    
    # Basic listing info (from scraper)
    title = models.CharField(max_length=500)
    location = models.CharField(max_length=200)
    airbnb_url = models.URLField(max_length=1000, unique=True)
    main_photo_url = models.URLField(max_length=1000, blank=True)
    main_photo_path = models.CharField(max_length=500, blank=True, help_text="Local path to downloaded listing image")
    
    # Marketplace specific
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='looking')
    description = models.TextField(blank=True, help_text="Additional details about the co-hosting opportunity")
    co_host_requirements = models.TextField(blank=True, help_text="What kind of co-host are you looking for?")
    
    # Scraped data (from DetailedAirbnbListing)
    property_type = models.CharField(max_length=100, blank=True)
    guests_capacity = models.CharField(max_length=50, blank=True)
    bedrooms = models.CharField(max_length=50, blank=True)
    bathrooms = models.CharField(max_length=50, blank=True)
    
    # Host info from scraper
    original_host_name = models.CharField(max_length=200, blank=True)
    original_host_id = models.CharField(max_length=100, blank=True)
    original_host_photo_url = models.URLField(max_length=1000, blank=True)
    original_host_photo_path = models.CharField(max_length=500, blank=True, help_text="Local path to downloaded host image")
    
    # Tasks the host is looking for a co-host to handle
    tasks_needed = models.ManyToManyField(
        'Task', blank=True, related_name='listings_needed',
        help_text="Tasks you need your co-host to handle"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_main_photo_url(self):
        """Get the main photo URL, preferring local path over remote URL"""
        if self.main_photo_path and os.path.exists(self.main_photo_path):
            return f"/media/{self.main_photo_path.replace('media/', '')}"
        elif self.main_photo_url:
            return self.main_photo_url
        return None
        
    def get_host_photo_url(self):
        """Get the host photo URL, preferring local path over remote URL"""
        if self.original_host_photo_path and os.path.exists(self.original_host_photo_path):
            return f"/media/{self.original_host_photo_path.replace('media/', '')}"
        elif self.original_host_photo_url:
            return self.original_host_photo_url
        return None

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    class Meta:
        ordering = ['-created_at']


# Task System
class Task(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Task name (e.g., 'Guest Check-in', 'Cleaning')")
    description = models.TextField(blank=True, help_text="Optional description of the task")
    created_at = models.DateTimeField(auto_now_add=True)
    usage_count = models.IntegerField(default=0, help_text="Number of times this task has been selected")

    class Meta:
        ordering = ['-usage_count', 'name']

    def __str__(self):
        return self.name


# Proposals System
class Proposal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('withdrawn', 'Withdrawn'),
    ]

    RATE_TYPE_CHOICES = [
        ('fixed', 'Fixed Rate'),
        ('percentage', 'Percentage of Revenue'),
    ]

    INITIATED_BY_CHOICES = [
        ('cohost', 'Co-Host'),
        ('host',   'Host'),
    ]

    listing = models.ForeignKey(MarketplaceListing, on_delete=models.CASCADE, related_name='proposals')
    cohost = models.ForeignKey(CoHostProfile, on_delete=models.CASCADE, related_name='proposals')

    message = models.TextField(help_text="Introduce yourself and explain your co-hosting approach")
    tasks = models.ManyToManyField(Task, blank=True, help_text="Tasks you can handle for this property")
    rate_type = models.CharField(max_length=20, choices=RATE_TYPE_CHOICES, null=True, blank=True, help_text="Type of rate structure")
    offered_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Your proposed rate (daily amount or percentage)")
    initiated_by = models.CharField(max_length=10, choices=INITIATED_BY_CHOICES, default='cohost',
                                    help_text="Who initiated this proposal")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Proposal from {self.cohost} for {self.listing.title}"
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['listing', 'cohost']  # One proposal per co-host per listing


# Messaging System
class Message(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Message from {self.sender.username} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['created_at']


# Direct Messaging (open messaging between any two connected users)
class DirectConversation(models.Model):
    participants = models.ManyToManyField(User, related_name='direct_conversations')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def other_participant(self, user):
        return self.participants.exclude(id=user.id).first()


class DirectMessage(models.Model):
    conversation = models.ForeignKey(DirectConversation, on_delete=models.CASCADE, related_name='messages')
    sender       = models.ForeignKey(User, on_delete=models.CASCADE)
    content      = models.TextField()
    created_at   = models.DateTimeField(auto_now_add=True)
    is_read      = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"DM from {self.sender.username} at {self.created_at:%Y-%m-%d %H:%M}"


class UserSocialLink(models.Model):
    PLATFORM_CHOICES = [
        ('airbnb',      'Airbnb'),
        ('booking',     'Booking.com'),
        ('vrbo',        'VRBO'),
        ('tripadvisor', 'TripAdvisor'),
        ('expedia',     'Expedia'),
        ('linkedin',    'LinkedIn'),
        ('other',       'Other'),
    ]

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='social_links')
    platform     = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    url          = models.URLField(max_length=500)

    class Meta:
        ordering = ['platform']

    def __str__(self):
        return f"{self.get_platform_display()} — {self.user_profile}"
