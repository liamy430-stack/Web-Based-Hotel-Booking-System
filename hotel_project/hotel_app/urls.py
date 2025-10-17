from django.urls import path
from . import views

urlpatterns = [
    # Home & Room Listing
    path('', views.home, name='home'),
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/<int:room_id>/', views.room_detail, name='room_detail'),
    
    # Booking
    path('book/<int:room_id>/', views.create_booking, name='create_booking'),
    path('booking/<int:booking_id>/confirm/', views.booking_confirm, name='booking_confirm'),
    path('check-availability/', views.check_availability, name='check_availability'),
    
    # Payment
    path('booking/<int:booking_id>/payment/', views.create_payment, name='create_payment'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # User Account
    path('account/bookings/', views.user_bookings, name='user_bookings'),
    path('account/profile/', views.user_profile, name='user_profile'),
    
    # Staff/Admin
    path('staff/dashboard/', views.dashboard, name='dashboard'),
    path('staff/bookings/', views.manage_bookings, name='manage_bookings'),
    path('staff/booking/<int:booking_id>/status/', views.update_booking_status, name='update_booking_status'),
]