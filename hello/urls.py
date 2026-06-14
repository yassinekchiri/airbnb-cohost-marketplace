from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Legacy scraper (keep for now)
    path('scraper/', views.hello_world, name='scraper'),
    
    # Public Marketplace
    path('', views.marketplace_home, name='marketplace_home'),
    path('listings/', views.listings_marketplace, name='listings_marketplace'),
    path('cohosts/', views.cohosts_marketplace, name='cohosts_marketplace'),
    path('listing/<int:listing_id>/', views.listing_detail, name='listing_detail'),
    path('cohost/<int:cohost_id>/', views.cohost_profile, name='cohost_profile'),
    path('host/<int:host_id>/', views.host_profile, name='host_profile'),
    path('review/submit/<int:proposal_id>/', views.submit_review, name='submit_review'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='hello/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(http_method_names=['get', 'post'], next_page='marketplace_home'), name='logout'),
    path('login-redirect/', views.custom_login_redirect, name='custom_login_redirect'),
    
    # Host Dashboard
    path('host/dashboard/', views.host_dashboard, name='host_dashboard'),
    path('host/add-listing/', views.add_listing, name='add_listing'),
    path('listing/<int:listing_id>/edit/', views.edit_listing, name='edit_listing'),
    
    # Co-Host Dashboard
    path('cohost/dashboard/', views.cohost_dashboard, name='cohost_dashboard'),
    
    # Test CSRF
    path('test-csrf/', views.test_csrf, name='test_csrf'),

    # Proposal Management
    path('proposal/<int:proposal_id>/edit/', views.edit_proposal, name='edit_proposal'),
    path('proposal/<int:proposal_id>/accept/', views.accept_proposal, name='accept_proposal'),
    path('proposal/<int:proposal_id>/decline/', views.decline_proposal, name='decline_proposal'),
    path('proposal/<int:proposal_id>/withdraw/', views.withdraw_proposal, name='withdraw_proposal'),
    path('proposal/<int:proposal_id>/end-partnership/', views.end_partnership, name='end_partnership'),
    path('proposal/<int:proposal_id>/leave-partnership/', views.cohost_end_partnership, name='cohost_end_partnership'),
    path('proposal/<int:proposal_id>/accept-request/', views.accept_partnership_request, name='accept_partnership_request'),
    path('proposal/<int:proposal_id>/decline-request/', views.decline_partnership_request, name='decline_partnership_request'),
    path('cohost/<int:cohost_id>/request-partnership/', views.send_partnership_request, name='send_partnership_request'),

    # Profile
    path('profile/edit/', views.edit_profile, name='edit_profile'),

    # Messaging
    path('messages/', views.inbox, name='inbox'),
    path('messages/<int:proposal_id>/', views.conversation, name='conversation'),
    path('messages/direct/<int:conversation_id>/', views.direct_conversation, name='direct_conversation'),
    path('contact/<int:cohost_id>/', views.contact_user, name='contact_user'),

    # API endpoints
    path('api/tasks/autocomplete/', views.task_autocomplete, name='task_autocomplete'),
    path('api/messages/poll/', views.api_poll_messages, name='api_poll_messages'),
    path('api/messages/poll-direct/', views.api_poll_direct_messages, name='api_poll_direct_messages'),
    path('api/messages/unread/', views.api_unread_count, name='api_unread_count'),
]