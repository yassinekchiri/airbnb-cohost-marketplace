from django.contrib import admin
from django.utils.translation import gettext_lazy as _


def _activate(modeladmin, request, queryset):
    queryset.update(is_active=True)
_activate.short_description = _("Mark selected as active")


def _deactivate(modeladmin, request, queryset):
    queryset.update(is_active=False)
_deactivate.short_description = _("Mark selected as inactive")
from .models import (
    AirbnbListing, DetailedAirbnbListing,
    UserProfile, HostProfile, CoHostProfile,
    MarketplaceListing, Task, Proposal, Message,
    DirectConversation, DirectMessage, Review, UserSocialLink,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_verified', 'phone_number', 'created_at')
    list_filter = ('role', 'is_verified')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)


@admin.register(HostProfile)
class HostProfileAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'total_listings')
    search_fields = ('user_profile__user__username', 'user_profile__user__email')
    raw_id_fields = ('user_profile',)


@admin.register(CoHostProfile)
class CoHostProfileAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'locations', 'experience_years', 'hourly_rate', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('user_profile__user__username', 'locations')
    filter_horizontal = ('capabilities',)
    raw_id_fields = ('user_profile',)
    actions = [_activate, _deactivate]


@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'location', 'platform', 'status', 'is_active', 'host', 'created_at', 'updated_at')
    list_filter = ('status', 'is_active', 'platform', 'property_type')
    search_fields = ('title', 'location', 'airbnb_url')
    filter_horizontal = ('tasks_needed',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    actions = [_activate, _deactivate]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ('cohost', 'listing', 'status', 'rate_type', 'offered_rate', 'initiated_by', 'created_at')
    list_filter = ('status', 'rate_type', 'initiated_by')
    search_fields = ('cohost__user_profile__user__username', 'listing__title')
    filter_horizontal = ('tasks',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'usage_count', 'created_at')
    search_fields = ('name',)
    ordering = ('-usage_count',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'proposal', 'created_at', 'is_read')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'content')
    readonly_fields = ('created_at',)


@admin.register(DirectConversation)
class DirectConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at')
    filter_horizontal = ('participants',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'created_at', 'is_read')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'content')
    readonly_fields = ('created_at',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'reviewee', 'rating', 'proposal', 'created_at')
    list_filter = ('rating',)
    search_fields = ('reviewer__user__username', 'reviewee__user__username')
    readonly_fields = ('created_at',)


@admin.register(UserSocialLink)
class UserSocialLinkAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'platform', 'url')
    list_filter = ('platform',)
    search_fields = ('user_profile__user__username',)


@admin.register(AirbnbListing)
class AirbnbListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'location', 'price', 'scraped_at')
    search_fields = ('title', 'location')
    readonly_fields = ('scraped_at',)


@admin.register(DetailedAirbnbListing)
class DetailedAirbnbListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'host_name', 'location', 'scraped_at')
    search_fields = ('title', 'host_name', 'location')
    readonly_fields = ('scraped_at',)
