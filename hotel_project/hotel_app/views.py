from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from datetime import datetime, timedelta
from django.db import models


from .models import Room, RoomType, Booking, Payment, CustomUser
from .forms import BookingForm, UserRegisterForm, UserLoginForm

# ============================================================================
# USER VIEWS (AUTH)
# ============================================================================

def register(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created! You can now login.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    
    context = {'form': form}
    return render(request, 'hotel_app/register.html', context)


def user_login(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()
    
    context = {'form': form}
    return render(request, 'hotel_app/login.html', context)


@login_required(login_url='login')
def user_logout(request):
    """User logout view."""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required(login_url='login')
def user_bookings(request):
    """Display user's bookings."""
    bookings = request.user.bookings.all().order_by('-check_in')
    
    context = {
        'bookings': bookings,
    }
    return render(request, 'hotel_app/user_bookings.html', context)


@login_required(login_url='login')
def user_profile(request):
    """User profile view."""
    user = request.user
    
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        user.save()
        messages.success(request, 'Profile updated.')
        return redirect('user_profile')
    
    context = {'user': user}
    return render(request, 'hotel_app/user_profile.html', context)


# ============================================================================
# PAYMENT VIEWS
# ============================================================================

@login_required(login_url='login')
def create_payment(request, booking_id):
    """Create payment record for booking."""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Ensure user is owner or staff
    if booking.user != request.user and not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    if request.method == 'POST':
        method = request.POST.get('method')
        amount = request.POST.get('amount')
        
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError('Amount must be positive.')
            
            payment = Payment.objects.create(
                booking=booking,
                amount=amount,
                method=method,
                status='completed',
                paid_at=datetime.now()
            )
            
            # Update booking status
            if booking.status == 'pending':
                booking.status = 'confirmed'
                booking.save()
            
            messages.success(request, 'Payment recorded successfully.')
            return redirect('booking_confirm', booking_id=booking.id)
        
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
    
    context = {
        'booking': booking,
        'methods': Payment.METHOD_CHOICES,
    }
    return render(request, 'hotel_app/create_payment.html', context)


# ============================================================================
# STAFF/ADMIN VIEWS
# ============================================================================

def staff_required(view_func):
    """Decorator to require staff access."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            messages.error(request, 'Staff access required.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


@staff_required
def dashboard(request):
    """Staff dashboard with analytics."""
    today = datetime.now().date()
    
    # Stats
    total_bookings = Booking.objects.count()
    confirmed_bookings = Booking.objects.filter(status='confirmed').count()
    checked_in = Booking.objects.filter(status='checked_in').count()
    revenue = Payment.objects.filter(status='completed').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    # Recent bookings
    recent_bookings = Booking.objects.order_by('-created_at')[:10]
    
    # Today's check-ins/outs
    todays_checkins = Booking.objects.filter(check_in=today, status__in=['confirmed', 'checked_in'])
    todays_checkouts = Booking.objects.filter(check_out=today, status__in=['checked_in'])
    
    context = {
        'total_bookings': total_bookings,
        'confirmed_bookings': confirmed_bookings,
        'checked_in': checked_in,
        'revenue': revenue,
        'recent_bookings': recent_bookings,
        'todays_checkins': todays_checkins,
        'todays_checkouts': todays_checkouts,
    }
    return render(request, 'hotel_app/dashboard.html', context)


@staff_required
def manage_bookings(request):
    """List and manage all bookings."""
    bookings = Booking.objects.select_related('room', 'user').order_by('-check_in')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        bookings = bookings.filter(status=status)
    
    context = {
        'bookings': bookings,
        'status_choices': Booking.STATUS_CHOICES,
        'selected_status': status,
    }
    return render(request, 'hotel_app/manage_bookings.html', context)


@staff_required
@require_http_methods(['POST'])
def update_booking_status(request, booking_id):
    """Update booking status via AJAX or form."""
    booking = get_object_or_404(Booking, id=booking_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(Booking.STATUS_CHOICES):
        booking.status = new_status
        booking.save()
        messages.success(request, f'Booking status updated to {booking.get_status_display()}.')
    
    return redirect('manage_bookings')
    HOME & LISTING 
    VIEWS
# ============================================================================

def home(request):
    """Home page with search bar and featured rooms."""
    featured_rooms = Room.objects.filter(
        is_active=True,
        status='available'
    ).select_related('room_type')[:6]
    
    room_types = RoomType.objects.all()
    
    context = {
        'featured_rooms': featured_rooms,
        'room_types': room_types,
    }
    return render(request, 'hotel_app/home.html', context)


def room_list(request):
    """List all available rooms with optional search filters."""
    rooms = Room.objects.filter(is_active=True).select_related('room_type')
    
    # Filter by room type
    room_type_id = request.GET.get('room_type')
    if room_type_id:
        rooms = rooms.filter(room_type_id=room_type_id)
    
    # Filter by capacity (guests)
    capacity = request.GET.get('capacity')
    if capacity:
        try:
            capacity = int(capacity)
            rooms = rooms.filter(room_type__capacity__gte=capacity)
        except ValueError:
            pass
    
    # Filter by status
    status = request.GET.get('status', 'available')
    if status:
        rooms = rooms.filter(status=status)
    
    room_types = RoomType.objects.all()
    
    context = {
        'rooms': rooms,
        'room_types': room_types,
        'selected_room_type': room_type_id,
        'selected_capacity': capacity,
        'selected_status': status,
    }
    return render(request, 'hotel_app/room_list.html', context)


def room_detail(request, room_id):
    """Display room details, amenities, and images."""
    room = get_object_or_404(Room, id=room_id, is_active=True)
    room_type = room.room_type
    images = room.images.all()
    main_image = images.filter(is_main=True).first()
    
    # Get current seasonal rate or use base price
    today = datetime.now().date()
    seasonal_rate = room_type.rates.filter(
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    current_price = seasonal_rate.price if seasonal_rate else room_type.base_price
    
    context = {
        'room': room,
        'room_type': room_type,
        'images': images,
        'main_image': main_image,
        'current_price': current_price,
        'seasonal_rate': seasonal_rate,
    }
    return render(request, 'hotel_app/room_detail.html', context)


# ============================================================================
# BOOKING VIEWS
# ============================================================================

def check_availability(request):
    """AJAX endpoint to check room availability."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    try:
        check_in_str = request.POST.get('check_in')
        check_out_str = request.POST.get('check_out')
        room_type_id = request.POST.get('room_type_id')
        capacity = int(request.POST.get('capacity', 1))
        
        check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
        check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        
        # Validation
        if check_in >= check_out:
            return JsonResponse({'error': 'Check-out must be after check-in'}, status=400)
        
        if check_in < datetime.now().date():
            return JsonResponse({'error': 'Check-in cannot be in the past'}, status=400)
        
        # Find available rooms
        booked_rooms = Booking.objects.filter(
            status__in=['confirmed', 'checked_in'],
            check_in__lt=check_out,
            check_out__gt=check_in
        ).values_list('room_id', flat=True)
        
        available_rooms = Room.objects.filter(
            is_active=True,
            status='available',
            room_type_id=room_type_id,
            room_type__capacity__gte=capacity
        ).exclude(id__in=booked_rooms)
        
        num_available = available_rooms.count()
        num_nights = (check_out - check_in).days
        
        return JsonResponse({
            'available': num_available > 0,
            'count': num_available,
            'nights': num_nights,
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='login')
def create_booking(request, room_id):
    """Create a new booking for a room."""
    room = get_object_or_404(Room, id=room_id, is_active=True)
    
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            # Check availability
            check_in = form.cleaned_data['check_in']
            check_out = form.cleaned_data['check_out']
            num_guests = form.cleaned_data['num_guests']
            
            if num_guests > room.room_type.capacity:
                messages.error(request, f'Room capacity is {room.room_type.capacity} guests.')
                return redirect('room_detail', room_id=room.id)
            
            # Check for overlapping bookings
            overlap = Booking.objects.filter(
                room=room,
                status__in=['confirmed', 'checked_in'],
                check_in__lt=check_out,
                check_out__gt=check_in
            ).exists()
            
            if overlap:
                messages.error(request, 'Room is not available for those dates.')
                return redirect('room_detail', room_id=room.id)
            
            # Calculate price
            num_nights = (check_out - check_in).days
            today = datetime.now().date()
            seasonal_rate = room.room_type.rates.filter(
                start_date__lte=today,
                end_date__gte=today
            ).first()
            
            nightly_rate = seasonal_rate.price if seasonal_rate else room.room_type.base_price
            total_price = num_nights * nightly_rate
            
            # Create booking
            booking = form.save(commit=False)
            booking.user = request.user
            booking.room = room
            booking.total_price = total_price
            booking.guest_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
            booking.guest_email = request.user.email
            booking.save()
            
            messages.success(request, 'Booking created! Proceed to payment.')
            return redirect('booking_confirm', booking_id=booking.id)
    else:
        form = BookingForm()
    
    context = {
        'form': form,
        'room': room,
    }
    return render(request, 'hotel_app/create_booking.html', context)


def booking_confirm(request, booking_id):
    """Display booking confirmation details."""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Ensure user can only view their own booking
    if request.user.is_authenticated and booking.user != request.user:
        if not request.user.is_staff:
            messages.error(request, 'Access denied.')
            return redirect('home')
    
    num_nights = booking.get_num_nights()
    
    context = {
        'booking': booking,
        'num_nights': num_nights,
    }
    return render(request, 'hotel_app/booking_confirm.html', context)


# ============================================================================
#