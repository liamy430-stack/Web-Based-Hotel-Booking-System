from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta

# ============================================================================
# USER MODELS
# ============================================================================

class CustomUser(AbstractUser):
    """Extended User model with role flags and additional info."""
    ROLE_CHOICES = [
        ('guest', 'Guest'),
        ('staff', 'Staff'),
        ('admin', 'Admin'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='guest')
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"
    
    @property
    def is_staff_or_admin(self):
        return self.role in ['staff', 'admin']


# ============================================================================
# ROOM MODELS
# ============================================================================

class Amenity(models.Model):
    """Amenities available in rooms (WiFi, AC, Pool, etc.)."""
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, help_text="CSS class or emoji")
    
    class Meta:
        verbose_name_plural = 'Amenities'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class RoomType(models.Model):
    """Room type category: Single, Double, Suite, etc."""
    CAPACITY_CHOICES = [(i, i) for i in range(1, 9)]
    
    name = models.CharField(max_length=100, unique=True)  # Single, Double, Suite
    description = models.TextField(blank=True)
    base_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    capacity = models.IntegerField(choices=CAPACITY_CHOICES, default=2)
    amenities = models.ManyToManyField(Amenity, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} (₱{self.base_price}/night, {self.capacity} guests)"


class Room(models.Model):
    """Individual room instance."""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Maintenance'),
        ('blocked', 'Blocked'),
    ]
    
    room_number = models.CharField(max_length=50, unique=True)
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='rooms')
    floor = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['room_number']
        unique_together = ('room_number',)
    
    def __str__(self):
        return f"Room {self.room_number} ({self.room_type.name})"


class RoomImage(models.Model):
    """Images for rooms."""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='rooms/%Y/%m/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_main = models.BooleanField(default=False, help_text="Primary image for listings")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-is_main', 'uploaded_at']
    
    def __str__(self):
        return f"Image for {self.room.room_number}"


class RoomRate(models.Model):
    """Seasonal or special rates for room types."""
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='rates')
    start_date = models.DateField()
    end_date = models.DateField()
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    reason = models.CharField(
        max_length=100, blank=True,
        help_text="e.g., 'Summer Season', 'Holiday Rate'"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = 'Room Rates'
    
    def __str__(self):
        return f"{self.room_type.name}: ₱{self.price} ({self.start_date} to {self.end_date})"
    
    def is_active(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date


# ============================================================================
# BOOKING & PAYMENT MODELS
# ============================================================================

class Booking(models.Model):
    """Guest booking/reservation."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bookings', help_text="Null for walk-in guests"
    )
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    check_in = models.DateField()
    check_out = models.DateField()
    guest_name = models.CharField(max_length=200)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)
    num_guests = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-check_in']
        indexes = [
            models.Index(fields=['status', 'check_in']),
        ]
    
    def __str__(self):
        return f"Booking: {self.room.room_number} ({self.check_in} - {self.check_out})"
    
    def get_num_nights(self):
        """Calculate number of nights."""
        return (self.check_out - self.check_in).days
    
    def is_overlapping(self):
        """Check if booking overlaps with other confirmed/pending bookings."""
        qs = Booking.objects.filter(
            room=self.room,
            status__in=['pending', 'confirmed', 'checked_in'],
            check_in__lt=self.check_out,
            check_out__gt=self.check_in
        ).exclude(pk=self.pk)
        return qs.exists()
    
    def can_cancel(self):
        """Check if booking can still be cancelled."""
        if self.status in ['checked_in', 'checked_out', 'cancelled']:
            return False
        return (self.check_in - timezone.now().date()).days > 1


class Payment(models.Model):
    """Payment record for bookings."""
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card/Stripe'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider_ref = models.CharField(max_length=200, blank=True, help_text="Stripe/Bank ref ID")
    notes = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"₱{self.amount} - {self.booking} ({self.method})"


class PromoCode(models.Model):
    """Promotional codes for discounts."""
    DISCOUNT_CHOICES = [
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateField()
    valid_to = models.DateField()
    is_active = models.BooleanField(default=True)
    max_uses = models.IntegerField(null=True, blank=True, help_text="Null = unlimited")
    times_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-valid_from']
    
    def __str__(self):
        return f"{self.code} - {self.discount_value} {self.discount_type}"
    
    def is_valid_now(self):
        today = timezone.now().date()
        if not self.is_active:
            return False
        if not (self.valid_from <= today <= self.valid_to):
            return False
        if self.max_uses and self.times_used >= self.max_uses:
            return False
        return True