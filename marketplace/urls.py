from django.urls import path
from . import views, admin_views

urlpatterns = [
    # Admin Control Panel paths
    path('admin-dashboard/', admin_views.admin_dashboard_home, name='admin_dashboard_home'),
    path('admin-dashboard/products/', admin_views.admin_products_list, name='admin_products_list'),
    path('admin-dashboard/products/create/', admin_views.admin_create_product, name='admin_create_product'),
    path('admin-dashboard/products/toggle/<int:pk>/<str:field>/', admin_views.admin_toggle_product, name='admin_toggle_product'),
    path('admin-dashboard/products/status/<int:pk>/', admin_views.admin_update_product_status, name='admin_update_product_status'),
    path('admin-dashboard/products/delete/<int:pk>/', admin_views.admin_delete_product, name='admin_delete_product'),
    path('admin-dashboard/requests/', admin_views.admin_requests_list, name='admin_requests_list'),
    path('admin-dashboard/requests/status/<int:pk>/', admin_views.admin_update_request_status, name='admin_update_request_status'),
    path('admin-dashboard/requests/delete/<int:pk>/', admin_views.admin_delete_request, name='admin_delete_request'),
    path('admin-dashboard/users/', admin_views.admin_users_list, name='admin_users_list'),
    path('admin-dashboard/users/toggle-staff/<int:pk>/', admin_views.admin_toggle_user_staff, name='admin_toggle_user_staff'),
    path('admin-dashboard/users/delete/<int:pk>/', admin_views.admin_delete_user, name='admin_delete_user'),
    path('admin-dashboard/categories/', admin_views.admin_categories_list, name='admin_categories_list'),
    path('admin-dashboard/categories/delete/<int:pk>/', admin_views.admin_delete_category, name='admin_delete_category'),
    path('admin-dashboard/banners/', admin_views.admin_banners_list, name='admin_banners_list'),
    path('admin-dashboard/banners/delete/<int:pk>/', admin_views.admin_delete_banner, name='admin_delete_banner'),

    path('', views.home_feed, name='home_feed'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('product/<int:pk>/update-status/', views.update_product_status, name='update_product_status'),
    path('product/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('product/create/', views.create_product, name='create_product'),
    path('product/create-bundle/', views.create_bundle, name='create_bundle'),
    path('chat/initiate/<int:product_id>/', views.initiate_chat, name='initiate_chat'),
    path('chat/room/<int:thread_id>/', views.chat_room, name='chat_room'),
    path('chat/api/<int:thread_id>/send/', views.api_send_message, name='api_send_message'),
    path('chat/api/<int:thread_id>/get/', views.api_get_messages, name='api_get_messages'),
    path('chat/api/notifications/', views.api_notifications, name='api_notifications'),
    path('chats/', views.inbox_view, name='inbox'),
    
    # Student requests paths
    path('requests/', views.requests_feed, name='requests_feed'),
    path('requests/create/', views.create_request, name='create_request'),
    path('requests/delete/<int:request_id>/', views.delete_request_view, name='delete_request'),
    path('requests/initiate/<int:request_id>/', views.initiate_request_chat, name='initiate_request_chat'),
    
    # Profile paths
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Auth paths
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('forgot-password/verify/', views.verify_otp_view, name='verify_otp'),
    path('flash-sales/', views.flash_sales_view, name='flash_sales'),
    path('bundles/', views.bundles_view, name='bundles'),

    # PWA — service worker must be served from root scope
    path('chat/message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('chat/thread/<int:thread_id>/delete/', views.delete_thread, name='delete_thread'),
    path('sw.js', views.service_worker, name='service_worker'),
]
