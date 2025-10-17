from django.contrib import admin
from django.utils.html import format_html
from .models import (
    CustomUser, Amenity, RoomType, Room, RoomImage,
    RoomRate, Booking, Payment, PromoCode
)

# ============================================================================
# USER ADMIN
# ============================================================================

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'get_full_name', 'role', 'phone', 'is_verified', 'date_joined')
    list_filter = ('role', 'is_verified', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = (
        ('Account Info', {'fields': ('username', 'email', 'password')}),
        ('Personal', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Status', {'fields': ('role', 'is_verified', 'is_active')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )


# ============================================================================
# ROOM MODELS ADMIN
# ============================================================================

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_price', 'capacity', 'num_rooms', 'num_amenities')
    list_filter = ('capacity', 'created_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('amenities',)
    
    def num_rooms(self, obj):
        return obj.rooms.count()
    num_rooms.short_description = 'Rooms'
    
    def num_amenities(self, obj):
        return obj.amenities.count()
    num_amenities.short_description = 'Amenities'


class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 1
    fields = ('image', 'alt_text', 'is_main', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'floor', 'status_badge', 'is_active')
    list_filter = ('status', 'is_active', 'room_type', 'floor')
    search_fields = ('room_number', 'room_type__name')
    inlines = [RoomImageInline]
    fieldsets = (
        ('Room Info', {'fields': ('room_number', 'room_type', 'floor')}),
        ('Status', {'fields': ('status', 'is_active')}),
        ('Dates', {'fields': ('created_at',)}),
    )
    readonly_fields = ('created_at',)
    
    def status_badge(self, obj):
        colors = {
            'available': '#28a745',
            'occupied': '#dc3545',
            'maintenance': '#ffc107',
            'blocked': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(RoomRate)
class RoomRateAdmin(admin.ModelAdmin):
    list_display = ('room_type', 'price', 'start_date', 'end_date', 'reason', 'is_active_now')
    list_filter = ('room_type', 'start_date', 'end_date')
    search_fields = ('room_type__name', 'reason')
    fieldsets = (
        ('Room & Price', {'fields': ('room_type', 'price')}),
        ('Duration', {'fields': ('start_date', 'end_date')}),
        ('Details', {'fields': ('reason',)}),
    )
    
    def is_active_now(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            '#28a745' if obj.is_active() else '#dc3545',
            'Active' if obj.is_active() else 'Inactive'
        )
    is_active_now.short_description = 'Active Now'


# ============================================================================
# BOOKING & PAYMENT ADMIN
# ============================================================================

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1
    fields = ('amount', 'method', 'status', 'provider_ref', 'paid_at')
    readonly_fields = ('created_at',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'guest_name', 'check_in', 'check_out', 'status_badge', 'total_price')
    list_filter = ('status', 'check_in', 'room__room_type')
    search_fields = ('guest_name', 'guest_email', 'room__room_number')
    readonly_fields = ('created_at', 'updated_at', 'num_nights', 'overlapping')
    inlines = [PaymentInline]
    actions = ['confirm_booking', 'cancel_booking']
    
    fieldsets = (
        ('Guest Info', {'fields': ('user', 'guest_name', 'guest_email', 'guest_phone')}),
        ('Booking Details', {'fields': ('room', 'check_in', 'check_out', 'num_guests', 'num_nights')}),
        ('Status & Price', {'fields': ('status', 'total_price')}),
        ('Notes', {'fields': ('notes',)}),
        ('Validation', {'fields': ('overlapping',)}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'confirmed': '#28a745',
            'checked_in': '#17a2b8',
            'checked_out': '#6c757d',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def num_nights(self, obj):
        return obj.get_num_nights()
    num_nights.short_description = 'Nights'
    
    def overlapping(self, obj):
        if obj.is_overlapping():
            return format_html('<span style="color: #dc3545; font-weight: bold;">⚠️ OVERLAPPING</span>')
        return format_html('<span style="color: #28a745;">✓ Valid</span>')
    overlapping.short_description = 'Booking Validity'
    
    def confirm_booking(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='confirmed')
        self.message_user(request, f'{updated} booking(s) confirmed.')
    confirm_booking.short_description = 'Mark selected as Confirmed'
    
    def cancel_booking(self, request, queryset):
        updated = queryset.filter(status__in=['pending', 'confirmed']).update(status='cancelled')
        self.message_user(request, f'{updated} booking(s) cancelled.')
    cancel_booking.short_description = 'Mark selected as Cancelled'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'method', 'status_badge', 'paid_at')
    list_filter = ('status', 'method', 'paid_at', 'created_at')
    search_fields = ('booking__id', 'booking__guest_name', 'provider_ref')
    readonly_fields = ('created_at',)
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'completed': '#28a745',
            'failed': '#dc3545',
            'refunded': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_display', 'valid_from', 'valid_to', 'is_valid_now_badge', 'times_used', 'max_uses')
    list_filter = ('discount_type', 'is_active', 'valid_from', 'valid_to')
    search_fields = ('code', 'description')
    fieldsets = (
        ('Code & Discount', {'fields': ('code', 'discount_type', 'discount_value')}),
        ('Validity', {'fields': ('valid_from', 'valid_to', 'is_active')}),
        ('Usage', {'fields': ('max_uses', 'times_used')}),
        ('Description', {'fields': ('description',)}),
    )
    
    def discount_display(self, obj):
        if obj.discount_type == 'percentage':
            return f"{obj.discount_value}%"
        return f"₱{obj.discount_value}"
    discount_display.short_description = 'Discount'
    
    def is_valid_now_badge(self, obj):
        valid = obj.is_valid_now()
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            '#28a745' if valid else '#dc3545',
            '✓ Valid' if valid else '✗ Expired'
        )
    is_valid_now_badge.short_description = 'Valid Now'