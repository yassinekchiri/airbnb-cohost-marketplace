from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit

from .models import (DetailedAirbnbListing, UserProfile, HostProfile, CoHostProfile,
                    MarketplaceListing, Proposal, Message, Task, UserSocialLink,
                    DirectConversation, DirectMessage, Review)
from .forms import (CustomUserCreationForm, HostProfileForm, CoHostProfileForm,
                   AddListingForm, ManualListingForm, ProposalForm, EditProposalForm, MessageForm,
                   UserInfoForm, ReviewForm)
import json
import subprocess
import os
import logging
import ipaddress
from urllib.parse import urlparse
from django.conf import settings

logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

def _validate_scraper_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError("URL must use http or https.")
        if not parsed.netloc or 'airbnb.com' not in parsed.netloc:
            raise ValueError("URL must be an Airbnb listing URL.")
        # Block private/reserved IPs to prevent SSRF
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                raise ValueError("Invalid URL target.")
        except ValueError as e:
            # If it raises here because of the IP check, re-raise it
            if "Invalid URL" in str(e):
                raise
            # Otherwise hostname is a domain name, not an IP — that's fine
    except ValueError:
        raise
    except Exception:
        raise ValueError("Invalid URL format.")


def _validate_image_upload(f):
    if f.size > _MAX_UPLOAD_BYTES:
        raise ValueError("File too large. Maximum size is 5 MB.")
    if f.content_type not in _ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Invalid file type '{f.content_type}'. Allowed: JPEG, PNG, WEBP, GIF.")


def _save_listing_photo(photo_file):
    """Save an uploaded listing photo and return its MEDIA_ROOT-relative path."""
    import uuid as _uuid
    ext = os.path.splitext(photo_file.name)[1].lower() or '.jpg'
    fname = f"listing_{_uuid.uuid4().hex[:16]}{ext}"
    save_dir = os.path.join(settings.MEDIA_ROOT, 'listings', 'listing_images')
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, fname), 'wb') as fh:
        for chunk in photo_file.chunks():
            fh.write(chunk)
    return os.path.join('listings', 'listing_images', fname)

def hello_world(request):
    detailed_listing = None
    error = None
    scrape_performed = False
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'scrape_single':
            listing_url = request.POST.get('listing_url', '').strip()
            
            if not listing_url:
                error = "Please enter a valid Airbnb listing URL"
            elif 'airbnb.com' not in listing_url:
                error = "Please enter a valid Airbnb URL"
            else:
                try:
                    detailed_data = scrape_single_airbnb_listing(listing_url, headless=True)
                    detailed_listing = detailed_data
                    scrape_performed = True
                except Exception:
                    logger.exception("Scrape failed for URL: %s", listing_url)
                    error = "Scraping failed. Please check the URL and try again."
    
    return render(request, 'hello/index.html', {
        'detailed_listing': detailed_listing,
        'error': error,
        'scrape_performed': scrape_performed
    })


# Authentication Views
@ratelimit(key='ip', rate='20/h', method='POST', block=True)
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'hello/register.html', {'form': form})


def custom_login_redirect(request):
    """Custom login redirect based on user role"""
    try:
        if request.user.is_authenticated:
            user_profile = request.user.userprofile
            if user_profile.role == 'host':
                return redirect('host_dashboard')
            elif user_profile.role == 'cohost':
                return redirect('cohost_dashboard')
    except UserProfile.DoesNotExist:
        pass
    return redirect('marketplace_home')


# Public Marketplace Views
def marketplace_home(request):
    """Smart home: redirect authenticated users to their relevant browse page."""
    if request.user.is_authenticated:
        try:
            role = request.user.userprofile.role
            if role == 'cohost':
                # Co-hosts look for properties to manage
                return redirect('listings_marketplace')
            elif role == 'host':
                # Hosts look for co-hosts to hire
                return redirect('cohosts_marketplace')
        except UserProfile.DoesNotExist:
            pass

    # Unauthenticated (or missing profile) → public landing page
    listings = MarketplaceListing.objects.filter(
        status__in=['looking', 'reviewing'], is_active=True
    ).select_related('host__user_profile__user').prefetch_related('tasks_needed')[:6]
    cohosts = CoHostProfile.objects.filter(is_active=True).select_related('user_profile__user', 'user_profile')[:6]
    listings_count = MarketplaceListing.objects.filter(status__in=['looking', 'reviewing'], is_active=True).count()
    cohosts_count = CoHostProfile.objects.filter(is_active=True).count()
    partnerships_count = Proposal.objects.filter(status='accepted').count()
    return render(request, 'hello/marketplace_home.html', {
        'listings': listings,
        'cohosts': cohosts,
        'listings_count': listings_count,
        'cohosts_count': cohosts_count,
        'partnerships_count': partnerships_count,
    })


def listings_marketplace(request):
    """Public view of all listings looking for co-hosts"""
    location_filter = request.GET.get('location', '')
    
    from django.db.models import Case, When, Value, IntegerField
    listings = MarketplaceListing.objects.filter(
        status__in=['looking', 'reviewing', 'found'], is_active=True
    ).select_related('host__user_profile__user').prefetch_related('tasks_needed').annotate(
        status_order=Case(
            When(status='looking', then=Value(0)),
            When(status='reviewing', then=Value(1)),
            When(status='found', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('status_order', '-updated_at')

    if location_filter:
        listings = listings.filter(
            Q(location__icontains=location_filter) |
            Q(title__icontains=location_filter) |
            Q(description__icontains=location_filter) |
            Q(co_host_requirements__icontains=location_filter) |
            Q(property_type__icontains=location_filter)
        )

    paginator = Paginator(listings, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'hello/listings_marketplace.html', {
        'page_obj': page_obj,
        'location_filter': location_filter
    })


def cohost_profile(request, cohost_id):
    """Public profile page for a co-host"""
    cohost = get_object_or_404(
        CoHostProfile.objects.select_related('user_profile__user')
                             .prefetch_related('capabilities', 'user_profile__social_links'),
        id=cohost_id
    )
    managed_listings = Proposal.objects.filter(
        cohost=cohost, status='accepted'
    ).select_related('listing').order_by('-updated_at')

    conversation_proposal_id = None
    can_message_directly = False
    can_review = False
    review_proposal = None
    user_review = None

    if request.user.is_authenticated:
        try:
            viewer = request.user.userprofile
            if viewer.role == 'host':
                p = Proposal.objects.filter(
                    listing__host=viewer.hostprofile,
                    cohost=cohost,
                ).order_by('-updated_at').first()
                if p:
                    conversation_proposal_id = p.id
                    if p.status == 'accepted':
                        existing = Review.objects.filter(reviewer=viewer, proposal=p).first()
                        if existing:
                            user_review = existing
                        else:
                            can_review = True
                            review_proposal = p
                elif not cohost.user_profile.restrict_messaging:
                    can_message_directly = True
        except (UserProfile.DoesNotExist, HostProfile.DoesNotExist):
            pass

    from django.db.models import Avg
    reviews = Review.objects.filter(reviewee=cohost.user_profile).select_related('reviewer__user')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']

    return render(request, 'hello/cohost_profile.html', {
        'cohost': cohost,
        'managed_listings': managed_listings,
        'social_links': cohost.user_profile.social_links.all(),
        'conversation_proposal_id': conversation_proposal_id,
        'can_message_directly': can_message_directly,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'can_review': can_review,
        'review_proposal': review_proposal,
        'user_review': user_review,
    })


def cohosts_marketplace(request):
    """Public view of all co-hosts"""
    location_filter = request.GET.get('location', '')

    cohosts = CoHostProfile.objects.filter(is_active=True).select_related('user_profile__user').prefetch_related('capabilities')

    if location_filter:
        cohosts = cohosts.filter(
            Q(locations__icontains=location_filter) |
            Q(bio__icontains=location_filter) |
            Q(user_profile__user__first_name__icontains=location_filter) |
            Q(user_profile__user__last_name__icontains=location_filter)
        )

    paginator = Paginator(cohosts, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # For hosts: proposal map, pending requests, open-messaging eligibility
    proposal_map    = {}   # cohost_id -> proposal_id  (can message)
    requested_set   = set()  # cohost_ids with a pending host-initiated request
    partnered_set   = set()  # cohost_ids with an accepted (active) partnership
    open_messaging  = set()
    host_listings_json = '[]'

    if request.user.is_authenticated:
        try:
            if request.user.userprofile.role == 'host':
                host_profile    = request.user.userprofile.hostprofile
                page_cohost_ids = [c.id for c in page_obj]

                all_proposals = Proposal.objects.filter(
                    listing__host=host_profile,
                    cohost__in=page_cohost_ids,
                ).order_by('-updated_at').values('cohost_id', 'id', 'initiated_by', 'status')

                for p in all_proposals:
                    cid = p['cohost_id']
                    if p['status'] == 'accepted':
                        partnered_set.add(cid)
                    if p['status'] == 'accepted' or p['initiated_by'] == 'cohost':
                        if cid not in proposal_map:
                            proposal_map[cid] = p['id']
                    elif p['initiated_by'] == 'host' and p['status'] == 'pending':
                        requested_set.add(cid)

                open_messaging = set(
                    CoHostProfile.objects.filter(
                        id__in=page_cohost_ids,
                        user_profile__restrict_messaging=False,
                    ).exclude(id__in=list(proposal_map.keys()) + list(requested_set))
                     .values_list('id', flat=True)
                )

                # Eligible listings for partnership request modal
                eligible = MarketplaceListing.objects.filter(
                    host=host_profile, status__in=['looking', 'reviewing']
                )
                host_listings_json = json.dumps([{
                    'id':       l.id,
                    'title':    l.title,
                    'location': l.location,
                    'photo':    l.get_main_photo_url() or '',
                } for l in eligible])
        except (UserProfile.DoesNotExist, HostProfile.DoesNotExist):
            pass

    return render(request, 'hello/cohosts_marketplace.html', {
        'page_obj':           page_obj,
        'location_filter':    location_filter,
        'proposal_map':       proposal_map,
        'open_messaging':     open_messaging,
        'requested_set':      requested_set,
        'partnered_set':      partnered_set,
        'host_listings_json': host_listings_json,
    })


def listing_detail(request, listing_id):
    """Public view of a specific listing with proposal form for logged-in co-hosts"""
    listing = get_object_or_404(MarketplaceListing, id=listing_id)
    
    # Check if user can propose (is a co-host and hasn't proposed yet)
    can_propose = False
    existing_proposal = None
    
    if request.user.is_authenticated:
        try:
            user_profile = request.user.userprofile
            if user_profile.role == 'cohost':
                cohost_profile = user_profile.cohostprofile
                existing_proposal = Proposal.objects.filter(
                    listing=listing, cohost=cohost_profile
                ).first()
                can_propose = existing_proposal is None and listing.status in ['looking', 'reviewing']
        except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
            pass

    # Handle proposal submission
    if request.method == 'POST' and can_propose:
        form = ProposalForm(request.POST)
        if form.is_valid():
            cohost_profile = request.user.userprofile.cohostprofile
            proposal = Proposal.objects.create(
                listing=listing,
                cohost=cohost_profile,
                message=form.cleaned_data['message'],
                rate_type=form.cleaned_data.get('rate_type'),
                offered_rate=form.cleaned_data.get('offered_rate')
            )

            # Handle tasks
            tasks_data = form.cleaned_data.get('tasks', '')
            if tasks_data:
                try:
                    tasks_list = json.loads(tasks_data)
                    for task_data in tasks_list:
                        task_name = task_data.get('name', '').strip()
                        task_id = task_data.get('id')

                        if task_name:
                            if task_id:
                                # Existing task
                                try:
                                    task = Task.objects.get(id=task_id)
                                    task.usage_count += 1
                                    task.save()
                                    proposal.tasks.add(task)
                                except Task.DoesNotExist:
                                    pass
                            else:
                                # New task
                                task, created = Task.objects.get_or_create(
                                    name=task_name,
                                    defaults={'usage_count': 1}
                                )
                                if not created:
                                    task.usage_count += 1
                                    task.save()
                                proposal.tasks.add(task)
                except json.JSONDecodeError:
                    pass

            messages.success(request, 'Your proposal has been sent to the host!')
            return redirect('listing_detail', listing_id=listing.id)
    else:
        form = ProposalForm()
    
    # Pass co-host's profile capabilities for quick-select in the proposal form
    cohost_profile_tasks = []
    if can_propose:
        try:
            caps = request.user.userprofile.cohostprofile.capabilities.values('id', 'name')
            cohost_profile_tasks = list(caps)
        except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
            pass

    return render(request, 'hello/listing_detail.html', {
        'listing': listing,
        'form': form,
        'can_propose': can_propose,
        'existing_proposal': existing_proposal,
        'cohost_profile_tasks': cohost_profile_tasks,
        'cohost_profile_tasks_json': json.dumps(cohost_profile_tasks),
    })


# Host Dashboard Views
@login_required
def host_dashboard(request):
    """Host dashboard showing their listings and proposals"""
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'host':
            messages.error(request, 'Access denied. Host account required.')
            return redirect('marketplace_home')
        
        host_profile = user_profile.hostprofile
        listings = host_profile.marketplace_listings.prefetch_related('tasks_needed', 'proposals').all()
        
        # Get recent pending proposals
        recent_proposals = Proposal.objects.filter(
            listing__host=host_profile,
            status='pending'
        ).select_related(
            'cohost__user_profile__user',
            'cohost__user_profile',
            'listing'
        ).prefetch_related('cohost__capabilities').order_by('-created_at')[:5]

        # Get accepted proposals = active co-hosts
        active_cohosts = Proposal.objects.filter(
            listing__host=host_profile,
            status='accepted'
        ).select_related(
            'cohost__user_profile__user',
            'listing'
        ).prefetch_related('cohost__capabilities').order_by('listing__title')

        # Which active partnerships has this host already reviewed?
        reviewed_proposal_ids = set(
            Review.objects.filter(
                reviewer=host_profile.user_profile,
                proposal__in=active_cohosts.values_list('id', flat=True)
            ).values_list('proposal_id', flat=True)
        )

        return render(request, 'hello/host_dashboard.html', {
            'host_profile': host_profile,
            'listings': listings,
            'recent_proposals': recent_proposals,
            'active_cohosts': active_cohosts,
            'reviewed_proposal_ids': reviewed_proposal_ids,
        })
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('marketplace_home')


@login_required
@never_cache
@ratelimit(key='user', rate='5/h', method='POST', block=True)
def add_listing(request):
    """Host adds a new listing using the scraper"""
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'host':
            messages.error(request, 'Access denied. Host account required.')
            return redirect('marketplace_home')
        
        host_profile = user_profile.hostprofile

        form = AddListingForm()
        manual_form = ManualListingForm()
        # Which tab to show on (re)render: 'scrape' (default) or 'manual'
        active_mode = 'scrape'

        if request.method == 'POST' and request.POST.get('mode') == 'manual':
            active_mode = 'manual'
            manual_form = ManualListingForm(request.POST, request.FILES)
            if manual_form.is_valid():
                listing = manual_form.save(commit=False)
                listing.host = host_profile

                # Optional photo upload
                photo = manual_form.cleaned_data.get('photo')
                if photo:
                    try:
                        _validate_image_upload(photo)
                        listing.main_photo_path = _save_listing_photo(photo)
                    except ValueError as ve:
                        manual_form.add_error('photo', str(ve))
                        return render(request, 'hello/add_listing.html', {
                            'form': form, 'manual_form': manual_form, 'active_mode': 'manual',
                        })

                # Optional listing URL (any platform) — guard the unique constraint
                listing_url = manual_form.cleaned_data.get('listing_url') or None
                if listing_url and MarketplaceListing.objects.filter(airbnb_url=listing_url).exists():
                    manual_form.add_error('listing_url', 'This listing URL is already in the marketplace.')
                    return render(request, 'hello/add_listing.html', {
                        'form': form, 'manual_form': manual_form, 'active_mode': 'manual',
                    })
                listing.airbnb_url = listing_url
                listing.save()
                manual_form.save_m2m()

                host_profile.total_listings = host_profile.marketplace_listings.count()
                host_profile.save()

                messages.success(request, f'Listing "{listing.title}" added successfully!')
                return redirect('host_dashboard')
            return render(request, 'hello/add_listing.html', {
                'form': form, 'manual_form': manual_form, 'active_mode': 'manual',
            })

        if request.method == 'POST':
            form = AddListingForm(request.POST)
            if form.is_valid():
                airbnb_url = form.cleaned_data['airbnb_url']

                # Validate URL safety (SSRF protection)
                try:
                    _validate_scraper_url(airbnb_url)
                except ValueError as ve:
                    messages.error(request, str(ve))
                    return render(request, 'hello/add_listing.html', {'form': form, 'manual_form': manual_form, 'active_mode': 'scrape'})

                # Check if listing already exists
                if MarketplaceListing.objects.filter(airbnb_url=airbnb_url).exists():
                    messages.error(request, 'This listing is already in the marketplace.')
                    return render(request, 'hello/add_listing.html', {'form': form, 'manual_form': manual_form, 'active_mode': 'scrape'})

                try:
                    # Use standalone scraper script
                    script_path = os.path.join(settings.BASE_DIR, 'standalone_scraper.py')
                    result = subprocess.run([
                        'python', script_path, airbnb_url
                    ], capture_output=True, text=True, timeout=300)
                    
                    if result.returncode != 0:
                        raise Exception(f"Scraper script failed: {result.stderr}")
                    
                    # Parse JSON output
                    scraped_data = json.loads(result.stdout)
                    
                    # Create marketplace listing with downloaded images
                    listing = MarketplaceListing.objects.create(
                        host=host_profile,
                        platform='airbnb',
                        title=scraped_data.get('title', 'Untitled Listing'),
                        location=scraped_data.get('location', ''),
                        airbnb_url=airbnb_url,
                        main_photo_url=scraped_data.get('main_photo_url', ''),
                        main_photo_path=scraped_data.get('main_photo_path', ''),
                        description=form.cleaned_data['description'],
                        co_host_requirements=form.cleaned_data['co_host_requirements'],
                        property_type=scraped_data.get('property_type', ''),
                        guests_capacity=scraped_data.get('guests_capacity', ''),
                        bedrooms=scraped_data.get('bedrooms', ''),
                        bathrooms=scraped_data.get('bathrooms', ''),
                        original_host_name=scraped_data.get('host_name', ''),
                        original_host_id=scraped_data.get('host_id', ''),
                        original_host_photo_url=scraped_data.get('host_photo_url', ''),
                        original_host_photo_path=scraped_data.get('host_photo_path', ''),
                    )
                    
                    # Update host's total listings count
                    host_profile.total_listings = host_profile.marketplace_listings.count()
                    host_profile.save()
                    
                    messages.success(request, f'Listing "{listing.title}" added successfully!')
                    return redirect('host_dashboard')
                    
                except subprocess.TimeoutExpired:
                    logger.error("Scraper timed out for URL: %s (user %s)", airbnb_url, request.user.id)
                    messages.error(request, 'Scraping timed out. The Airbnb listing may be unavailable. Please try again.')
                except json.JSONDecodeError:
                    logger.error("Scraper returned invalid JSON for URL: %s", airbnb_url)
                    messages.error(request, 'Could not read listing data. Please try again.')
                except Exception:
                    logger.exception("Unexpected error scraping URL %s for user %s", airbnb_url, request.user.id)
                    messages.error(request, 'An unexpected error occurred while adding your listing. Please try again.')

        return render(request, 'hello/add_listing.html', {
            'form': form, 'manual_form': manual_form, 'active_mode': active_mode,
        })

    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('marketplace_home')


# Co-Host Dashboard Views
@login_required
def cohost_dashboard(request):
    """Co-host dashboard showing opportunities and their proposals"""
    try:
        user_profile = request.user.userprofile
        if user_profile.role != 'cohost':
            messages.error(request, 'Access denied. Co-host account required.')
            return redirect('marketplace_home')
        
        cohost_profile = user_profile.cohostprofile

        # Open listings the co-host hasn't already proposed to
        already_proposed_ids = cohost_profile.proposals.values_list('listing_id', flat=True)
        open_listings = MarketplaceListing.objects.filter(
            status__in=['looking', 'reviewing'],
            is_active=True,
        ).exclude(id__in=already_proposed_ids)

        # Prefer listings matching the co-host's service areas...
        location_keywords = [loc.strip() for loc in cohost_profile.locations.split(',') if loc.strip()]
        relevant_listings = open_listings
        if location_keywords:
            location_q = Q()
            for keyword in location_keywords:
                location_q |= Q(location__icontains=keyword)
            location_matched = open_listings.filter(location_q)
            # ...but fall back to all open listings when nothing matches (e.g. listings
            # with no location yet) so the co-host always sees real opportunities.
            relevant_listings = location_matched if location_matched.exists() else open_listings

        relevant_listings = relevant_listings.order_by('-created_at')[:6]
        
        # Co-host's own submitted proposals (cohost-initiated, any status)
        my_proposals = cohost_profile.proposals.filter(initiated_by='cohost').select_related(
            'listing', 'listing__host__user_profile__user'
        ).prefetch_related('tasks')

        # Real status counts for the stat cards (template attr lookups like
        # my_proposals.accepted silently render 0, which is misleading).
        accepted_count = my_proposals.filter(status='accepted').count()
        pending_count = my_proposals.filter(status='pending').count()

        # Explicit profile-completeness checklist — list exactly what's missing.
        profile_missing = []
        if not cohost_profile.bio:
            profile_missing.append('bio')
        if not cohost_profile.locations:
            profile_missing.append('service areas')
        if not cohost_profile.experience_years:
            profile_missing.append('years of experience')
        if not cohost_profile.hourly_rate:
            profile_missing.append('daily rate')
        if not user_profile.profile_photo:
            profile_missing.append('profile photo')

        # All active partnerships (accepted, regardless of who initiated)
        active_partnerships = cohost_profile.proposals.filter(
            status='accepted'
        ).select_related('listing__host__user_profile__user', 'listing')

        # Incoming partnership requests from hosts (still pending)
        incoming_requests = Proposal.objects.filter(
            cohost=cohost_profile,
            initiated_by='host',
            status='pending',
        ).select_related(
            'listing__host__user_profile__user',
            'listing__host__user_profile',
            'listing',
        ).order_by('-created_at')

        # Which accepted partnerships has this co-host already reviewed?
        reviewed_proposal_ids = set(
            Review.objects.filter(
                reviewer=user_profile,
                proposal__in=active_partnerships.values_list('id', flat=True)
            ).values_list('proposal_id', flat=True)
        )

        return render(request, 'hello/cohost_dashboard.html', {
            'cohost_profile': cohost_profile,
            'relevant_listings': relevant_listings,
            'my_proposals': my_proposals,
            'accepted_count': accepted_count,
            'pending_count': pending_count,
            'profile_missing': profile_missing,
            'active_partnerships': active_partnerships,
            'incoming_requests': incoming_requests,
            'reviewed_proposal_ids': reviewed_proposal_ids,
        })
        
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('marketplace_home')



def host_profile(request, host_id):
    """Public profile page for a host, showing their info and reviews."""
    from django.db.models import Avg
    host = get_object_or_404(
        HostProfile.objects.select_related('user_profile__user'),
        id=host_id
    )
    reviews = Review.objects.filter(reviewee=host.user_profile).select_related('reviewer__user')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']

    can_review = False
    review_proposal = None
    user_review = None

    if request.user.is_authenticated:
        try:
            viewer = request.user.userprofile
            if viewer.role == 'cohost':
                p = Proposal.objects.filter(
                    listing__host=host,
                    cohost=viewer.cohostprofile,
                    status='accepted',
                ).order_by('-updated_at').first()
                if p:
                    existing = Review.objects.filter(reviewer=viewer, proposal=p).first()
                    if existing:
                        user_review = existing
                    else:
                        can_review = True
                        review_proposal = p
        except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
            pass

    listings = host.marketplace_listings.exclude(status='paused').order_by('-created_at')[:6]

    return render(request, 'hello/host_profile.html', {
        'host': host,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'can_review': can_review,
        'review_proposal': review_proposal,
        'user_review': user_review,
        'listings': listings,
    })


@login_required
def submit_review(request, proposal_id):
    """Submit a review for a completed/active partnership."""
    if request.method != 'POST':
        return redirect('marketplace_home')

    proposal = get_object_or_404(Proposal, id=proposal_id)

    if proposal.status != 'accepted':
        messages.error(request, 'Reviews can only be left for active partnerships.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    try:
        reviewer = request.user.userprofile
    except UserProfile.DoesNotExist:
        messages.error(request, 'Profile not found.')
        return redirect('marketplace_home')

    host_up = proposal.listing.host.user_profile
    cohost_up = proposal.cohost.user_profile

    if reviewer == host_up:
        reviewee = cohost_up
    elif reviewer == cohost_up:
        reviewee = host_up
    else:
        messages.error(request, 'You are not part of this partnership.')
        return redirect('marketplace_home')

    if Review.objects.filter(reviewer=reviewer, proposal=proposal).exists():
        messages.error(request, 'You have already reviewed this partnership.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    rating = request.POST.get('rating', '').strip()
    comment = request.POST.get('comment', '').strip()

    if not rating or not rating.isdigit() or int(rating) not in range(1, 6):
        messages.error(request, 'Please select a rating between 1 and 5.')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    Review.objects.create(
        reviewer=reviewer,
        reviewee=reviewee,
        proposal=proposal,
        rating=int(rating),
        comment=comment,
    )
    messages.success(request, 'Your review has been submitted. Thank you!')
    return redirect(request.META.get('HTTP_REFERER', '/'))


def test_csrf(request):
    """Simple test view for CSRF debugging"""
    return render(request, 'hello/test_form.html')


@ratelimit(key='ip', rate='60/m', method='GET', block=True)
def task_autocomplete(request):
    """API endpoint for task autocomplete suggestions"""
    if request.method == 'GET':
        query = request.GET.get('q', '').strip()

        if len(query) < 1:
            # Return all tasks when no query (for dropdown on focus)
            all_tasks = Task.objects.all().order_by('-usage_count', 'name')[:20]
            tasks_data = []
            for task in all_tasks:
                tasks_data.append({
                    'id': task.id,
                    'name': task.name,
                    'exists': True
                })
            return JsonResponse({'tasks': tasks_data})

        # Search for existing tasks that contain the query
        existing_tasks = Task.objects.filter(
            name__icontains=query
        ).order_by('-usage_count', 'name')[:10]

        tasks_data = []
        for task in existing_tasks:
            tasks_data.append({
                'id': task.id,
                'name': task.name,
                'exists': True
            })

        # If no exact match and query is not empty, suggest creating new task
        exact_match = any(task.name.lower() == query.lower() for task in existing_tasks)
        if not exact_match and query:
            tasks_data.append({
                'id': None,
                'name': query,
                'exists': False
            })

        return JsonResponse({'tasks': tasks_data})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def edit_proposal(request, proposal_id):
    """Edit an existing proposal"""
    proposal = get_object_or_404(Proposal, id=proposal_id)

    # Check if user owns the proposal and it's still pending
    try:
        user_profile = request.user.userprofile
        cohost_profile = user_profile.cohostprofile
        if proposal.cohost != cohost_profile:
            messages.error(request, 'Access denied.')
            return redirect('marketplace_home')

        if proposal.status != 'pending':
            messages.error(request, 'This proposal cannot be edited.')
            return redirect('listing_detail', listing_id=proposal.listing.id)
    except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('marketplace_home')

    if request.method == 'POST':
        form = EditProposalForm(request.POST)
        if form.is_valid():
            # Update proposal
            proposal.message = form.cleaned_data['message']
            proposal.rate_type = form.cleaned_data.get('rate_type')
            proposal.offered_rate = form.cleaned_data.get('offered_rate')

            # Clear existing tasks
            proposal.tasks.clear()

            # Handle tasks
            tasks_data = form.cleaned_data.get('tasks', '')
            if tasks_data:
                try:
                    tasks_list = json.loads(tasks_data)
                    for task_data in tasks_list:
                        task_name = task_data.get('name', '').strip()
                        task_id = task_data.get('id')

                        if task_name:
                            if task_id:
                                # Existing task
                                try:
                                    task = Task.objects.get(id=task_id)
                                    task.usage_count += 1
                                    task.save()
                                    proposal.tasks.add(task)
                                except Task.DoesNotExist:
                                    pass
                            else:
                                # New task
                                task, created = Task.objects.get_or_create(
                                    name=task_name,
                                    defaults={'usage_count': 1}
                                )
                                if not created:
                                    task.usage_count += 1
                                    task.save()
                                proposal.tasks.add(task)
                except json.JSONDecodeError:
                    pass

            proposal.save()
            messages.success(request, 'Your proposal has been updated!')
            return redirect('listing_detail', listing_id=proposal.listing.id)
    else:
        # Pre-populate form with existing data
        existing_tasks = []
        for task in proposal.tasks.all():
            existing_tasks.append({'id': task.id, 'name': task.name})

        initial_data = {
            'message': proposal.message,
            'rate_type': proposal.rate_type,
            'offered_rate': proposal.offered_rate,
            'tasks': json.dumps(existing_tasks)
        }
        form = EditProposalForm(initial=initial_data)

    return render(request, 'hello/edit_proposal.html', {
        'form': form,
        'proposal': proposal,
        'listing': proposal.listing,
        'existing_tasks': json.dumps(existing_tasks) if 'existing_tasks' in locals() else '[]'
    })


@login_required
@login_required
def accept_proposal(request, proposal_id):
    """Host accepts a co-host proposal"""
    if request.method != 'POST':
        return redirect('host_dashboard')
    proposal = get_object_or_404(Proposal, id=proposal_id)
    try:
        host_profile = request.user.userprofile.hostprofile
        if proposal.listing.host != host_profile:
            messages.error(request, 'Access denied.')
            return redirect('host_dashboard')
    except (UserProfile.DoesNotExist, HostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('host_dashboard')

    proposal.status = 'accepted'
    proposal.save()
    proposal.listing.status = 'found'
    proposal.listing.save()
    messages.success(request, f'You accepted the proposal from {proposal.cohost.user_profile.user.get_full_name() or proposal.cohost.user_profile.user.username}!')
    return redirect('host_dashboard')


@login_required
def decline_proposal(request, proposal_id):
    """Host declines a co-host proposal"""
    if request.method != 'POST':
        return redirect('host_dashboard')
    proposal = get_object_or_404(Proposal, id=proposal_id)
    try:
        host_profile = request.user.userprofile.hostprofile
        if proposal.listing.host != host_profile:
            messages.error(request, 'Access denied.')
            return redirect('host_dashboard')
    except (UserProfile.DoesNotExist, HostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('host_dashboard')

    proposal.status = 'declined'
    proposal.save()
    messages.success(request, 'Proposal declined.')
    return redirect('host_dashboard')


@login_required
def withdraw_proposal(request, proposal_id):
    """Withdraw an existing proposal"""
    proposal = get_object_or_404(Proposal, id=proposal_id)

    # Check if user owns the proposal and it's still pending
    try:
        user_profile = request.user.userprofile
        cohost_profile = user_profile.cohostprofile
        if proposal.cohost != cohost_profile:
            messages.error(request, 'Access denied.')
            return redirect('marketplace_home')

        if proposal.status != 'pending':
            messages.error(request, 'This proposal cannot be withdrawn.')
            return redirect('listing_detail', listing_id=proposal.listing.id)
    except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('marketplace_home')

    if request.method == 'POST':
        proposal.status = 'withdrawn'
        proposal.save()
        messages.success(request, 'Your proposal has been withdrawn.')

    return redirect('listing_detail', listing_id=proposal.listing.id)


# ── Messaging ────────────────────────────────────────────────────────────────

@login_required
def inbox(request):
    user = request.user
    conversations = []

    # ── Proposal-based conversations ──
    proposals = Proposal.objects.filter(
        Q(listing__host__user_profile__user=user) |
        Q(cohost__user_profile__user=user)
    ).select_related(
        'listing', 'listing__host__user_profile', 'listing__host__user_profile__user',
        'cohost__user_profile', 'cohost__user_profile__user',
    ).prefetch_related('messages__sender')

    for proposal in proposals:
        msgs = list(proposal.messages.all())
        last_msg = msgs[-1] if msgs else None
        unread = sum(1 for m in msgs if not m.is_read and m.sender != user)
        is_host = proposal.listing.host.user_profile.user == user
        other_profile = proposal.cohost.user_profile if is_host else proposal.listing.host.user_profile
        conversations.append({
            'type': 'proposal',
            'proposal': proposal,
            'last_message': last_msg,
            'unread': unread,
            'other_profile': other_profile,
            'url_id': proposal.id,
        })

    # ── Direct conversations ──
    direct_convs = (
        DirectConversation.objects.filter(participants=user)
        .prefetch_related('messages__sender', 'participants__userprofile')
    )
    for conv in direct_convs:
        msgs = list(conv.messages.all())
        last_msg = msgs[-1] if msgs else None
        unread = sum(1 for m in msgs if not m.is_read and m.sender != user)
        other_user = conv.participants.exclude(id=user.id).first()
        other_profile = getattr(other_user, 'userprofile', None) if other_user else None
        conversations.append({
            'type': 'direct',
            'conversation': conv,
            'last_message': last_msg,
            'unread': unread,
            'other_profile': other_profile,
            'url_id': conv.id,
        })

    conversations.sort(
        key=lambda c: c['last_message'].created_at if c['last_message'] else
            (c['proposal'].created_at if c['type'] == 'proposal' else c['conversation'].created_at),
        reverse=True,
    )
    return render(request, 'hello/inbox.html', {'conversations': conversations})


@login_required
def direct_conversation(request, conversation_id):
    """Direct message thread — not tied to a proposal."""
    conv = get_object_or_404(DirectConversation, id=conversation_id)
    user = request.user

    if not conv.participants.filter(id=user.id).exists():
        messages.error(request, 'Access denied.')
        return redirect('inbox')

    conv.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

    other_user = conv.participants.exclude(id=user.id).first()
    other_profile = getattr(other_user, 'userprofile', None)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            DirectMessage.objects.create(conversation=conv, sender=user, content=content)
            conv.save()
        return redirect('direct_conversation', conversation_id=conversation_id)

    thread_messages = list(conv.messages.select_related('sender').all())
    last_message_id = thread_messages[-1].id if thread_messages else 0
    return render(request, 'hello/direct_conversation.html', {
        'conversation': conv,
        'other_profile': other_profile,
        'thread_messages': thread_messages,
        'last_message_id': last_message_id,
    })


@login_required
def api_poll_direct_messages(request):
    try:
        conversation_id = int(request.GET.get('conversation_id', 0))
        after_id        = int(request.GET.get('after', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid params'}, status=400)

    conv = get_object_or_404(DirectConversation, id=conversation_id)
    user = request.user
    if not conv.participants.filter(id=user.id).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)

    new_msgs = conv.messages.filter(id__gt=after_id).select_related('sender').order_by('created_at')
    new_msgs.filter(is_read=False).exclude(sender=user).update(is_read=True)

    data = [{
        'id': m.id,
        'content': m.content,
        'is_own': m.sender_id == user.id,
        'sender_name': m.sender.get_full_name() or m.sender.username,
        'time': m.created_at.strftime('%H:%M'),
        'iso': m.created_at.isoformat(),
    } for m in new_msgs]
    return JsonResponse({'messages': data})


@login_required
@ratelimit(key='user', rate='60/h', method='POST', block=True)
def conversation(request, proposal_id):
    proposal = get_object_or_404(
        Proposal.objects.select_related(
            'listing', 'listing__host__user_profile__user', 'listing__host__user_profile',
            'cohost__user_profile__user', 'cohost__user_profile',
        ), id=proposal_id
    )
    user = request.user
    is_host   = proposal.listing.host.user_profile.user == user
    is_cohost = proposal.cohost.user_profile.user == user
    if not is_host and not is_cohost:
        messages.error(request, 'Access denied.')
        return redirect('inbox')

    proposal.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)
    other_profile = proposal.cohost.user_profile if is_host else proposal.listing.host.user_profile

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(proposal=proposal, sender=user, content=content)
            proposal.save()
        return redirect('conversation', proposal_id=proposal_id)

    thread_messages = list(proposal.messages.select_related('sender').all())
    last_message_id = thread_messages[-1].id if thread_messages else 0
    return render(request, 'hello/conversation.html', {
        'proposal': proposal,
        'other_profile': other_profile,
        'thread_messages': thread_messages,
        'last_message_id': last_message_id,
        'is_host': is_host,
    })


@login_required
def api_poll_messages(request):
    try:
        proposal_id = int(request.GET.get('proposal_id', 0))
        after_id    = int(request.GET.get('after', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid params'}, status=400)

    proposal = get_object_or_404(Proposal, id=proposal_id)
    user = request.user
    is_host   = proposal.listing.host.user_profile.user == user
    is_cohost = proposal.cohost.user_profile.user == user
    if not is_host and not is_cohost:
        return JsonResponse({'error': 'Access denied'}, status=403)

    new_msgs = proposal.messages.filter(id__gt=after_id).select_related('sender').order_by('created_at')
    new_msgs.filter(is_read=False).exclude(sender=user).update(is_read=True)

    data = [{
        'id': m.id,
        'content': m.content,
        'is_own': m.sender_id == user.id,
        'sender_name': m.sender.get_full_name() or m.sender.username,
        'time': m.created_at.strftime('%H:%M'),
        'iso': m.created_at.isoformat(),
    } for m in new_msgs]
    return JsonResponse({'messages': data})


@login_required
def contact_user(request, cohost_id):
    """Route to the right conversation: proposal-based first, then direct if privacy allows."""
    cohost = get_object_or_404(CoHostProfile, id=cohost_id)
    user = request.user
    other_user = cohost.user_profile.user

    # Proposal-based conversation takes priority
    proposal = Proposal.objects.filter(
        listing__host__user_profile__user=user,
        cohost=cohost,
    ).order_by('-updated_at').first()
    if proposal:
        return redirect('conversation', proposal_id=proposal.id)

    # No proposal — check if open messaging is allowed
    if not cohost.user_profile.restrict_messaging:
        conv = (
            DirectConversation.objects.filter(participants=user)
            .filter(participants=other_user)
            .first()
        )
        if not conv:
            conv = DirectConversation.objects.create()
            conv.participants.add(user, other_user)
        return redirect('direct_conversation', conversation_id=conv.id)

    # Restricted — silently redirect to their profile with no alarming messages
    return redirect('cohost_profile', cohost_id=cohost_id)


@login_required
def send_partnership_request(request, cohost_id):
    """Host sends a partnership request (invitation) to a co-host for a specific listing."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    cohost = get_object_or_404(CoHostProfile, id=cohost_id)

    try:
        host_profile = request.user.userprofile.hostprofile
    except (UserProfile.DoesNotExist, HostProfile.DoesNotExist):
        return JsonResponse({'error': 'Host account required.'}, status=403)

    listing_id = request.POST.get('listing_id', '').strip()
    message    = request.POST.get('message', '').strip()

    if not listing_id:
        return JsonResponse({'error': 'Please select a listing.'}, status=400)

    listing = get_object_or_404(MarketplaceListing, id=listing_id, host=host_profile)

    existing = Proposal.objects.filter(listing=listing, cohost=cohost).first()
    if existing:
        if existing.status == 'accepted':
            return JsonResponse({'error': 'You already have an active partnership for this listing.'}, status=400)
        if existing.initiated_by == 'cohost' and existing.status == 'pending':
            return JsonResponse({'error': 'This co-host already applied to this listing — check your pending proposals.'}, status=400)
        return JsonResponse({'error': 'A request already exists for this listing.'}, status=400)

    Proposal.objects.create(
        listing=listing,
        cohost=cohost,
        message=message or f"Hi! I'd love to have you co-host my property \"{listing.title}\". Let's connect!",
        initiated_by='host',
    )
    return JsonResponse({'success': True})


@login_required
def accept_partnership_request(request, proposal_id):
    """Co-host accepts a host-initiated partnership request."""
    if request.method != 'POST':
        return redirect('cohost_dashboard')
    proposal = get_object_or_404(Proposal, id=proposal_id, initiated_by='host', status='pending')
    try:
        cohost_profile = request.user.userprofile.cohostprofile
        if proposal.cohost != cohost_profile:
            messages.error(request, 'Access denied.')
            return redirect('cohost_dashboard')
    except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('cohost_dashboard')

    proposal.status = 'accepted'
    proposal.save()
    proposal.listing.status = 'found'
    proposal.listing.save()
    host_name = (proposal.listing.host.user_profile.user.get_full_name()
                 or proposal.listing.host.user_profile.user.username)
    messages.success(request, f'Partnership with {host_name} accepted! You can now message them.')
    return redirect('cohost_dashboard')


@login_required
def decline_partnership_request(request, proposal_id):
    """Co-host declines a host-initiated partnership request."""
    if request.method != 'POST':
        return redirect('cohost_dashboard')
    proposal = get_object_or_404(Proposal, id=proposal_id, initiated_by='host', status='pending')
    try:
        cohost_profile = request.user.userprofile.cohostprofile
        if proposal.cohost != cohost_profile:
            messages.error(request, 'Access denied.')
            return redirect('cohost_dashboard')
    except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('cohost_dashboard')

    proposal.status = 'declined'
    proposal.save()
    messages.success(request, 'Partnership request declined.')
    return redirect('cohost_dashboard')


@login_required
def api_unread_count(request):
    user = request.user
    proposal_unread = Message.objects.filter(
        Q(proposal__listing__host__user_profile__user=user) |
        Q(proposal__cohost__user_profile__user=user),
        is_read=False,
    ).exclude(sender=user).count()
    direct_unread = DirectMessage.objects.filter(
        conversation__participants=user,
        is_read=False,
    ).exclude(sender=user).count()
    return JsonResponse({'unread': proposal_unread + direct_unread})


@login_required
def edit_listing(request, listing_id):
    """Host edits one of their listings or syncs it from the source platform."""
    listing = get_object_or_404(MarketplaceListing, id=listing_id)
    try:
        host_profile = request.user.userprofile.hostprofile
        if listing.host != host_profile:
            messages.error(request, 'Access denied.')
            return redirect('host_dashboard')
    except (UserProfile.DoesNotExist, HostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('host_dashboard')

    # ── AJAX: re-scrape and return diff ──────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'sync':
        if not listing.airbnb_url or listing.platform != 'airbnb':
            return JsonResponse({'error': 'This listing has no Airbnb URL to sync. Edit the details manually instead.'}, status=400)
        try:
            script_path = os.path.join(settings.BASE_DIR, 'standalone_scraper.py')
            result = subprocess.run(
                ['python', script_path, listing.airbnb_url],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                return JsonResponse({'error': f'Scraper failed: {result.stderr[:300]}'}, status=500)

            scraped = json.loads(result.stdout)

            # Fields that can be synced
            SYNCABLE = {
                'title':          {'label': 'Title',         'old': listing.title},
                'location':       {'label': 'Location',      'old': listing.location},
                'property_type':  {'label': 'Property type', 'old': listing.property_type},
                'guests_capacity':{'label': 'Guests',        'old': listing.guests_capacity},
                'bedrooms':       {'label': 'Bedrooms',      'old': listing.bedrooms},
                'bathrooms':      {'label': 'Bathrooms',     'old': listing.bathrooms},
                'main_photo_url': {'label': 'Photo URL',     'old': listing.main_photo_url},
            }
            changes = []
            for field, meta in SYNCABLE.items():
                new_val = scraped.get(field, '')
                if new_val and new_val != meta['old']:
                    changes.append({
                        'field': field,
                        'label': meta['label'],
                        'old':   meta['old'],
                        'new':   new_val,
                    })

            return JsonResponse({
                'changes': changes,
                'raw': scraped,
                'no_changes': len(changes) == 0,
            })
        except subprocess.TimeoutExpired:
            return JsonResponse({'error': 'Scraper timed out. Please try again.'}, status=504)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Scraper returned invalid data.'}, status=500)
        except Exception:
            logger.exception("Sync scrape failed for listing %s", listing_id)
            return JsonResponse({'error': 'An unexpected error occurred.'}, status=500)

    # ── Regular POST: save edits ──────────────────────────────────────────────
    if request.method == 'POST':
        # Basic fields
        listing.title             = request.POST.get('title', listing.title).strip()
        listing.location          = request.POST.get('location', listing.location).strip()
        listing.property_type     = request.POST.get('property_type', listing.property_type).strip()
        listing.guests_capacity   = request.POST.get('guests_capacity', listing.guests_capacity).strip()
        listing.bedrooms          = request.POST.get('bedrooms', listing.bedrooms).strip()
        listing.bathrooms         = request.POST.get('bathrooms', listing.bathrooms).strip()
        listing.description       = request.POST.get('description', listing.description).strip()
        listing.co_host_requirements = request.POST.get('co_host_requirements', listing.co_host_requirements).strip()
        listing.status            = request.POST.get('status', listing.status)

        # Photo: new upload takes priority over URL override
        photo_file = request.FILES.get('main_photo')
        if photo_file:
            try:
                _validate_image_upload(photo_file)
            except ValueError as ve:
                messages.error(request, str(ve))
                return redirect('edit_listing', listing_id=listing_id)
            import hashlib as _hashlib
            ext = os.path.splitext(photo_file.name)[1] or '.jpg'
            seed = listing.airbnb_url or f'listing-{listing.id}'
            fname = f"listing_{_hashlib.md5(seed.encode()).hexdigest()[:10]}_custom{ext}"
            save_dir = os.path.join(settings.MEDIA_ROOT, 'listings', 'listing_images')
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, fname)
            with open(save_path, 'wb') as fh:
                for chunk in photo_file.chunks():
                    fh.write(chunk)
            listing.main_photo_path = os.path.join('listings', 'listing_images', fname)
            listing.main_photo_url  = ''
        elif request.POST.get('main_photo_url'):
            listing.main_photo_url  = request.POST.get('main_photo_url').strip()
            listing.main_photo_path = ''

        listing.save()

        # Tasks needed
        tasks_json = request.POST.get('tasks_needed_data', '[]')
        try:
            tasks_list = json.loads(tasks_json)
            listing.tasks_needed.clear()
            for item in tasks_list:
                tname = item.get('name', '').strip()
                tid   = item.get('id')
                if not tname:
                    continue
                if tid:
                    try:
                        task = Task.objects.get(id=tid)
                        listing.tasks_needed.add(task)
                    except Task.DoesNotExist:
                        pass
                else:
                    task, created = Task.objects.get_or_create(
                        name=tname, defaults={'usage_count': 1}
                    )
                    if not created:
                        task.usage_count += 1
                        task.save()
                    listing.tasks_needed.add(task)
        except json.JSONDecodeError:
            pass

        messages.success(request, 'Listing updated successfully!')
        return redirect('host_dashboard')

    # ── GET: render form ─────────────────────────────────────────────────────
    existing_tasks_needed = list(listing.tasks_needed.values('id', 'name'))
    existing_ids = {t['id'] for t in existing_tasks_needed}

    # Popular tasks for the quick-select chips (top 20 by usage + any already selected)
    popular_tasks = list(
        Task.objects.order_by('-usage_count', 'name')[:20].values('id', 'name')
    )
    # Ensure already-selected tasks appear in the chip panel even if not in top 20
    for t in existing_tasks_needed:
        if not any(p['id'] == t['id'] for p in popular_tasks):
            popular_tasks.append(t)

    source_label = listing.get_platform_display() if listing.platform else 'Airbnb'

    return render(request, 'hello/edit_listing.html', {
        'listing': listing,
        'tasks_needed_json': json.dumps(existing_tasks_needed),
        'popular_tasks_json': json.dumps(popular_tasks),
        'existing_task_ids_json': json.dumps(list(existing_ids)),
        'source_label': source_label,
    })


@login_required
def cohost_end_partnership(request, proposal_id):
    """Co-host withdraws from an active partnership"""
    if request.method != 'POST':
        return redirect('cohost_dashboard')
    proposal = get_object_or_404(Proposal, id=proposal_id)
    try:
        cohost_profile = request.user.userprofile.cohostprofile
        if proposal.cohost != cohost_profile:
            messages.error(request, 'Access denied.')
            return redirect('cohost_dashboard')
    except (UserProfile.DoesNotExist, CoHostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('cohost_dashboard')

    if proposal.status != 'accepted':
        messages.error(request, 'This partnership is not active.')
        return redirect('cohost_dashboard')

    host_name = proposal.listing.host.user_profile.user.get_full_name() or proposal.listing.host.user_profile.user.username
    proposal.status = 'withdrawn'
    proposal.save()
    proposal.listing.status = 'looking'
    proposal.listing.save()
    messages.success(request, f'You have left the partnership with {host_name}. Their listing is now open again.')
    return redirect('cohost_dashboard')


@login_required
def end_partnership(request, proposal_id):
    """Host ends an active co-host partnership"""
    if request.method != 'POST':
        return redirect('host_dashboard')
    proposal = get_object_or_404(Proposal, id=proposal_id)
    try:
        host_profile = request.user.userprofile.hostprofile
        if proposal.listing.host != host_profile:
            messages.error(request, 'Access denied.')
            return redirect('host_dashboard')
    except (UserProfile.DoesNotExist, HostProfile.DoesNotExist):
        messages.error(request, 'Access denied.')
        return redirect('host_dashboard')

    if proposal.status != 'accepted':
        messages.error(request, 'This partnership is not active.')
        return redirect('host_dashboard')

    cohost_name = proposal.cohost.user_profile.user.get_full_name() or proposal.cohost.user_profile.user.username
    proposal.status = 'declined'
    proposal.save()
    proposal.listing.status = 'looking'
    proposal.listing.save()
    messages.success(request, f'Partnership with {cohost_name} has been ended. Your listing is now open for new co-hosts.')
    return redirect('host_dashboard')


@login_required
def edit_profile(request):
    """Edit profile for both hosts and co-hosts"""
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        messages.error(request, 'User profile not found.')
        return redirect('marketplace_home')

    role = user_profile.role

    if role == 'host':
        role_profile = user_profile.hostprofile
        RoleForm = HostProfileForm
    else:
        role_profile = user_profile.cohostprofile
        RoleForm = CoHostProfileForm

    if request.method == 'POST':
        user_form = UserInfoForm(request.POST, request.FILES)
        role_form = RoleForm(request.POST, instance=role_profile)

        if user_form.is_valid() and role_form.is_valid():
            # Validate profile photo before saving anything
            raw_photo = request.FILES.get('profile_photo')
            if raw_photo:
                try:
                    _validate_image_upload(raw_photo)
                except ValueError as ve:
                    messages.error(request, str(ve))
                    return redirect('edit_profile')

            user = request.user
            user.first_name = user_form.cleaned_data['first_name']
            user.last_name = user_form.cleaned_data['last_name']
            user.email = user_form.cleaned_data['email']
            user.save()

            user_profile.phone_number = user_form.cleaned_data['phone_number']
            if user_form.cleaned_data.get('profile_photo'):
                user_profile.profile_photo = user_form.cleaned_data['profile_photo']
            elif request.POST.get('remove_profile_photo'):
                user_profile.profile_photo.delete(save=False)
                user_profile.profile_photo = None
            user_profile.restrict_messaging = request.POST.get('restrict_messaging') == 'on'
            user_profile.save()

            role_form.save()

            # Save capabilities (co-host only)
            if role == 'cohost':
                cap_json = request.POST.get('profile_tasks_data', '[]')
                try:
                    cap_data = json.loads(cap_json)
                    role_profile.capabilities.clear()
                    for item in cap_data:
                        task_name = item.get('name', '').strip()
                        task_id   = item.get('id')
                        if not task_name:
                            continue
                        if task_id:
                            try:
                                task = Task.objects.get(id=task_id)
                                role_profile.capabilities.add(task)
                            except Task.DoesNotExist:
                                pass
                        else:
                            task, created = Task.objects.get_or_create(
                                name=task_name,
                                defaults={'usage_count': 1}
                            )
                            if not created:
                                task.usage_count += 1
                                task.save()
                            role_profile.capabilities.add(task)
                except json.JSONDecodeError:
                    pass

            # Save social links
            links_json = request.POST.get('social_links_data', '[]')
            try:
                links_data = json.loads(links_json)
                user_profile.social_links.all().delete()
                for link in links_data:
                    platform = link.get('platform', '').strip()
                    url = link.get('url', '').strip()
                    if platform and url:
                        UserSocialLink.objects.create(
                            user_profile=user_profile,
                            platform=platform,
                            url=url,
                        )
            except json.JSONDecodeError:
                pass

            messages.success(request, 'Your profile has been updated successfully!')
            if role == 'host':
                return redirect('host_dashboard')
            else:
                return redirect('cohost_dashboard')
    else:
        user_form = UserInfoForm(initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone_number': user_profile.phone_number,
        })
        role_form = RoleForm(instance=role_profile)

    existing_links = list(user_profile.social_links.values('platform', 'url'))
    profile_tasks  = list(role_profile.capabilities.values('id', 'name')) if role == 'cohost' else []

    return render(request, 'hello/edit_profile.html', {
        'user_form': user_form,
        'role_form': role_form,
        'role': role,
        'existing_links_json': json.dumps(existing_links),
        'profile_tasks_json': json.dumps(profile_tasks),
    })


def privacy_policy(request):
    return render(request, 'hello/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'hello/terms_of_service.html')


def contact(request):
    submitted = False
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_body = request.POST.get('message', '').strip()
        if name and email and message_body:
            from django.core.mail import send_mail
            from django.conf import settings as django_settings
            try:
                send_mail(
                    subject=f'[CoHostr Contact] {subject or "New message"}',
                    message=f'From: {name} <{email}>\n\n{message_body}',
                    from_email=django_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[django_settings.DEFAULT_FROM_EMAIL],
                    fail_silently=False,
                )
            except Exception:
                logger.exception('Contact form email failed')
            submitted = True
    return render(request, 'hello/contact.html', {'submitted': submitted})
