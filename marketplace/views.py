import json
import random
import urllib.parse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import cache_control
from django.db.models import Q
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.contrib import messages
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings

from .models import Product, Category, ChatThread, Message, Profile, PasswordResetOTP, BundleItem, ItemRequest, BannerImage

from django.utils import timezone
import datetime

def get_flash_sale_status():
    now = timezone.now()
    local_now = timezone.localtime(now)
    
    # Friday is weekday 4 in python (Mon=0, Tue=1, Wed=2, Thu=3, Fri=4)
    weekday = local_now.weekday()
    current_time = local_now.time()
    
    if weekday == 4:
        if current_time < datetime.time(18, 0):
            days_ahead = 0
        elif current_time > datetime.time(20, 0):
            days_ahead = 7
        else:
            days_ahead = 0
    else:
        days_ahead = 4 - weekday
        if days_ahead < 0:
            days_ahead += 7
            
    next_start = local_now.replace(hour=18, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_ahead)
    is_active = (weekday == 4 and datetime.time(18, 0) <= current_time <= datetime.time(20, 0))
    
    if is_active:
        end_time = local_now.replace(hour=20, minute=0, second=0, microsecond=0)
    else:
        end_time = next_start.replace(hour=20)
        
    return {
        'is_active': is_active,
        'next_start': next_start,
        'end_time': end_time,
    }

def home_feed(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()

    products = Product.objects.filter(status='available')
    categories = Category.objects.all()

    if query:
        products = products.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    if category_slug:
        if category_slug == 'flash':
            products = products.filter(is_flash_sale=True)
        else:
            products = products.filter(category__slug=category_slug)

    # Separate bundles from standard products
    bundles = products.filter(is_bundle=True).order_by('-created_at')
    standard_products = products.filter(is_bundle=False)

    # Fetch flash sale status
    flash_status = get_flash_sale_status()
    # Filter flash sale products to stand out in their own container
    flash_products = standard_products.filter(is_flash_sale=True)
    if category_slug != 'flash':
        standard_products = standard_products.filter(is_flash_sale=False)

    featured_products = standard_products.filter(is_featured=True)
    recent_products = standard_products.filter(is_featured=False).order_by('-created_at')

    # Fetch custom hero banners
    custom_big_banners = BannerImage.objects.filter(card_type='big_card')
    custom_flash_banners = BannerImage.objects.filter(card_type='flash_sales')
    custom_request_banners = BannerImage.objects.filter(card_type='requests')
    custom_bundle_banners = BannerImage.objects.filter(card_type='bundles')

    context = {
        'bundles': bundles,
        'featured_products': featured_products,
        'recent_products': recent_products,
        'categories': categories,
        'selected_category': category_slug,
        'query': query,
        'flash_status': flash_status,
        'flash_products': flash_products,
        'open_requests_count': ItemRequest.objects.filter(status='open').count(),
        'active_flash_count': flash_products.count(),
        'active_bundles_count': bundles.count(),
        'custom_big_banners': custom_big_banners,
        'custom_flash_banners': custom_flash_banners,
        'custom_request_banners': custom_request_banners,
        'custom_bundle_banners': custom_bundle_banners,
    }
    return render(request, 'marketplace/home.html', context)

def flash_sales_view(request):
    flash_status = get_flash_sale_status()
    # Filter flash sale products to stand out on their own page
    flash_products = Product.objects.filter(is_flash_sale=True, status='available').order_by('-created_at')
    
    # Custom banner images
    custom_flash_banners = BannerImage.objects.filter(card_type='flash_sales')

    context = {
        'flash_status': flash_status,
        'flash_products': flash_products,
        'active_flash_count': flash_products.count(),
        'custom_flash_banners': custom_flash_banners,
    }
    return render(request, 'marketplace/flash_sales.html', context)

def bundles_view(request):
    # Filter bundles to stand out on their own page
    bundles = Product.objects.filter(is_bundle=True, status='available').order_by('-created_at')
    
    # Custom banner images
    custom_bundle_banners = BannerImage.objects.filter(card_type='bundles')

    context = {
        'bundles': bundles,
        'active_bundles_count': bundles.count(),
        'custom_bundle_banners': custom_bundle_banners,
    }
    return render(request, 'marketplace/bundles.html', context)

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    flash_status = get_flash_sale_status()
    is_flash_active = product.is_flash_sale and flash_status['is_active']
    flash_savings = 0
    if is_flash_active:
        flash_savings = product.price - product.flash_sale_price
        
    context = {
        'product': product,
        'whatsapp_link': product.whatsapp_link,
        'is_flash_active': is_flash_active,
        'flash_status': flash_status,
        'flash_savings': flash_savings,
    }
    return render(request, 'marketplace/product_detail.html', context)

@login_required
def initiate_chat(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Check if a ChatThread exists for the current user (buyer), the product's seller, and the product.
    # If not, create it.
    thread, _ = ChatThread.objects.get_or_create(
        product=product,
        buyer=request.user,
        seller=product.seller
    )
    return redirect('chat_room', thread_id=thread.id)

@login_required
def chat_room(request, thread_id):
    thread = get_object_or_404(ChatThread, id=thread_id)
    
    # If request user is not buyer or seller, return 403
    if request.user != thread.buyer and request.user != thread.seller:
        raise PermissionDenied("You are not authorized to view this chat.")

    # Set incoming unread messages to is_read=True
    thread.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    
    messages = thread.messages.all()
    
    context = {
        'thread': thread,
        'chat_messages': messages,
        'other_user': thread.seller if request.user == thread.buyer else thread.buyer,
    }
    return render(request, 'marketplace/chat_room.html', context)

@login_required
def api_send_message(request, thread_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
        
    thread = get_object_or_404(ChatThread, id=thread_id)
    if request.user != thread.buyer and request.user != thread.seller:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    text = ""
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
        except json.JSONDecodeError:
            pass
    else:
        text = request.POST.get('text', '').strip()

    if not text:
        return JsonResponse({'error': 'Message text is empty'}, status=400)

    message = Message.objects.create(
        thread=thread,
        sender=request.user,
        text=text
    )
    return JsonResponse({
        'status': 'success',
        'message': {
            'id': message.id,
            'sender': message.sender.username,
            'text': message.text,
            'created_at': message.created_at.strftime('%I:%M %p'),
        }
    })

@login_required
def api_get_messages(request, thread_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)
        
    thread = get_object_or_404(ChatThread, id=thread_id)
    if request.user != thread.buyer and request.user != thread.seller:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    last_id = request.GET.get('last_id')
    messages = thread.messages.all()
    
    if last_id:
        try:
            last_id = int(last_id)
            messages = messages.filter(id__gt=last_id)
        except ValueError:
            pass
            
    # Mark newly fetched incoming messages as read since they are being polled in the chat view
    messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'sender': msg.sender.username,
            'sender_name': msg.sender.first_name if msg.sender.first_name else msg.sender.username,
            'text': msg.text,
            'is_read': msg.is_read,
            'is_sender': msg.sender == request.user,
            'created_at': msg.created_at.strftime('%I:%M %p'),
        })
        
    return JsonResponse({'messages': messages_data})

@login_required
def api_notifications(request):
    """
    API endpoint to fetch the list of recent conversations/unread notifications
    for the dropdown menu in the header.
    """
    threads = ChatThread.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user)
    ).distinct()
    
    notifications_data = []
    total_unread_count = 0
    
    for thread in threads:
        unread_count = thread.messages.filter(is_read=False).exclude(sender=request.user).count()
        total_unread_count += unread_count
        
        last_msg = thread.messages.last()
        other_user = thread.seller if request.user == thread.buyer else thread.buyer
        
        # Determine notification icon/thumbnail
        item_title = ""
        item_image_url = None
        item_type = "chat"
        
        if thread.product:
            item_title = thread.product.title
            if thread.product.image:
                item_image_url = thread.product.image.url
            item_type = "product"
        elif thread.item_request:
            item_title = f"Request: {thread.item_request.title}"
            if thread.item_request.image:
                item_image_url = thread.item_request.image.url
            item_type = "request"
            
        time_str = ""
        sort_time = thread.id
        if last_msg:
            sort_time = last_msg.created_at.timestamp()
            from django.utils.timesince import timesince
            try:
                time_str = f"{timesince(last_msg.created_at).split(',')[0]} ago"
            except Exception:
                time_str = last_msg.created_at.strftime('%I:%M %p')
        else:
            time_str = "No messages"
            
        # User details
        other_profile = getattr(other_user, 'profile', None)
        avatar_url = other_profile.profile_picture.url if other_profile and other_profile.profile_picture else None
        
        notifications_data.append({
            'thread_id': thread.id,
            'other_user_name': other_user.first_name or other_user.username,
            'other_user_initials': other_user.username[:2].upper(),
            'other_user_avatar': avatar_url,
            'last_message_text': last_msg.text if last_msg else "Started a conversation.",
            'last_message_time': time_str,
            'unread_count': unread_count,
            'item_title': item_title,
            'item_image': item_image_url,
            'item_type': item_type,
            'sort_time': sort_time
        })
        
    # Sort: unread first, then by sort_time descending
    notifications_data.sort(key=lambda x: (x['unread_count'] > 0, x['sort_time']), reverse=True)
    
    return JsonResponse({
        'notifications': notifications_data[:5],  # Top 5 recent/unread threads
        'global_unread_count': total_unread_count
    })

def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard_home')
        return redirect('home_feed')
        
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            if user.is_staff:
                return redirect('admin_dashboard_home')
            return redirect('home_feed')
        else:
            error = "Invalid username or password."
            
    return render(request, 'marketplace/auth.html', {'action': 'login', 'error': error})

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home_feed')
        
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        hostel_or_area = request.POST.get('hostel_or_area', 'main_campus')
        
        if not username or not password or not phone_number or not first_name:
            error = "Username, First Name, Password, and Phone Number are required."
        elif User.objects.filter(username=username).exists():
            error = "Username already exists."
        elif Profile.objects.filter(phone_number=phone_number).exists():
            error = "Phone number is already registered."
        else:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name
                    )
                    Profile.objects.create(
                        user=user,
                        phone_number=phone_number,
                        hostel_or_area=hostel_or_area
                    )
                auth_login(request, user)
                return redirect('home_feed')
            except Exception as e:
                error = f"Error creating account: {str(e)}"
                
    return render(request, 'marketplace/auth.html', {
        'action': 'signup',
        'error': error,
        'hostel_choices': Profile.HOSTEL_CHOICES
    })

def logout_view(request):
    auth_logout(request)
    return redirect('home_feed')

@login_required
def create_product(request):
    error = None
    categories = Category.objects.all()
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip()
        category_id = request.POST.get('category', '').strip()
        image = request.FILES.get('image')

        if not title or not price or not category_id or not image:
            error = "Title, Category, Price, and Product Image are required."
        else:
            try:
                price = int(price)
                if category_id == '__new__':
                    new_category_name = request.POST.get('new_category_name', '').strip()
                    if not new_category_name:
                        raise ValueError("Please specify the new category name.")
                    category = Category.objects.filter(name__iexact=new_category_name).first()
                    if not category:
                        category = Category.objects.create(name=new_category_name)
                else:
                    category = Category.objects.get(id=category_id)
                product = Product.objects.create(
                    seller=request.user,
                    category=category,
                    title=title,
                    description=description,
                    price=price,
                    image=image,
                    status='available'
                )
                return redirect('product_detail', pk=product.pk)
            except Exception as e:
                error = f"Error listing product: {str(e)}"

    return render(request, 'marketplace/create_product.html', {
        'categories': categories,
        'error': error
    })

@login_required
def create_bundle(request):
    error = None
    categories = Category.objects.all()
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip()
        category_id = request.POST.get('category', '').strip()
        image = request.FILES.get('image')
        
        # Bundle items from POST
        item_names = request.POST.getlist('item_name[]')
        item_prices = request.POST.getlist('item_price[]')

        if not title or not price or not category_id or not image:
            error = "Title, Category, Price, and Product Image are required."
        elif not item_names or not [name for name in item_names if name.strip()]:
            error = "You must list at least one item in the bundle."
        else:
            try:
                price = int(price)
                if category_id == '__new__':
                    new_category_name = request.POST.get('new_category_name', '').strip()
                    if not new_category_name:
                        raise ValueError("Please specify the new category name.")
                    category = Category.objects.filter(name__iexact=new_category_name).first()
                    if not category:
                        category = Category.objects.create(name=new_category_name)
                else:
                    category = Category.objects.get(id=category_id)
                
                with transaction.atomic():
                    product = Product.objects.create(
                        seller=request.user,
                        category=category,
                        title=title,
                        description=description,
                        price=price,
                        image=image,
                        is_bundle=True,
                        status='available'
                    )
                    
                    for name, est_price in zip(item_names, item_prices):
                        name = name.strip()
                        if name:
                            est_p = None
                            if est_price.strip():
                                try:
                                    est_p = int(est_price.strip())
                                except ValueError:
                                    pass
                            BundleItem.objects.create(
                                product=product,
                                name=name,
                                estimated_price=est_p
                            )
                            
                return redirect('product_detail', pk=product.pk)
            except Exception as e:
                error = f"Error listing bundle: {str(e)}"

    return render(request, 'marketplace/create_bundle.html', {
        'categories': categories,
        'error': error
    })

@login_required
def inbox_view(request):
    threads = ChatThread.objects.filter(
        Q(buyer=request.user) | Q(seller=request.user)
    )
    
    threads_list = list(threads)
    for thread in threads_list:
        thread.other_user = thread.seller if request.user == thread.buyer else thread.buyer
        thread.unread_count = thread.messages.filter(is_read=False).exclude(sender=request.user).count()
        thread.last_message = thread.messages.last()
        
    # Sort threads by the creation time of the last message (most recent first)
    threads_list.sort(key=lambda t: t.last_message.created_at if t.last_message else t.id, reverse=True)
        
    return render(request, 'marketplace/inbox.html', {'threads': threads_list})

def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('home_feed')
        
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        if not username or not email:
            error = "Username and email address are required."
        else:
            user_qs = User.objects.filter(username__iexact=username, email__iexact=email)
            if not user_qs.exists():
                error = "No account found with this username and email address combination."
            else:
                user = user_qs.first()
                otp = f"{random.randint(100000, 999999)}"
                PasswordResetOTP.objects.create(user=user, otp=otp)
                try:
                    send_mail(
                        'Password Reset OTP - simply marketplace',
                        f'Hi {user.first_name or user.username},\n\nYour one-time password reset OTP is {otp}.\n\nThis code is valid for 10 minutes.\n\nBest regards,\nThe simply Team',
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=False,
                    )
                    messages.success(request, f"A verification code has been sent to {user.email}.")
                    return redirect(f"{reverse('verify_otp')}?email={urllib.parse.quote(user.email)}&username={urllib.parse.quote(user.username)}")
                except Exception as e:
                    error = f"Error sending verification email: {str(e)}"
                    
    return render(request, 'marketplace/forgot_password.html', {'error': error})

def verify_otp_view(request):
    if request.user.is_authenticated:
        return redirect('home_feed')
        
    email = request.GET.get('email', '').strip()
    username = request.GET.get('username', '').strip()
    error = None
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        username = request.POST.get('username', '').strip()
        otp = request.POST.get('otp', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        if not email or not username or not otp or not password or not confirm_password:
            error = "All fields are required."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            user_qs = User.objects.filter(username__iexact=username, email__iexact=email)
            if not user_qs.exists():
                error = "Invalid reset request."
            else:
                user = user_qs.first()
                otp_record = PasswordResetOTP.objects.filter(user=user).order_by('-created_at').first()
                if not otp_record or otp_record.otp != otp:
                    error = "Invalid or incorrect OTP code."
                elif not otp_record.is_valid():
                    error = "This verification code has expired. Please request a new one."
                else:
                    user.set_password(password)
                    user.save()
                    PasswordResetOTP.objects.filter(user=user).delete()
                    messages.success(request, "Your password has been reset successfully. You can now login.")
                    return redirect('login')
                    
    return render(request, 'marketplace/verify_otp.html', {'email': email, 'username': username, 'error': error})

def requests_feed(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()

    item_requests = ItemRequest.objects.filter(status='open')
    categories = Category.objects.all()

    if query:
        item_requests = item_requests.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    if category_slug:
        item_requests = item_requests.filter(category__slug=category_slug)

    item_requests = item_requests.order_by('-created_at')

    context = {
        'item_requests': item_requests,
        'categories': categories,
        'selected_category': category_slug,
        'query': query,
    }
    return render(request, 'marketplace/requests_feed.html', context)

@login_required
def create_request(request):
    error = None
    categories = Category.objects.all()
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        budget = request.POST.get('budget', '').strip()
        category_id = request.POST.get('category', '').strip()
        image = request.FILES.get('image')

        if not title or not budget or not category_id:
            error = "Title, Category, and Budget are required."
        else:
            try:
                budget = int(budget)
                if category_id == '__new__':
                    new_category_name = request.POST.get('new_category_name', '').strip()
                    if not new_category_name:
                        raise ValueError("Please specify the new category name.")
                    category = Category.objects.filter(name__iexact=new_category_name).first()
                    if not category:
                        category = Category.objects.create(name=new_category_name)
                else:
                    category = Category.objects.get(id=category_id)
                ItemRequest.objects.create(
                    requester=request.user,
                    category=category,
                    title=title,
                    description=description,
                    budget=budget,
                    image=image,
                    status='open'
                )
                return redirect('requests_feed')
            except Exception as e:
                error = f"Error posting request: {str(e)}"

    return render(request, 'marketplace/create_request.html', {
        'categories': categories,
        'error': error
    })

@login_required
def delete_request_view(request, request_id):
    if request.method != 'POST':
        messages.error(request, "POST method required to delete request.")
        return redirect('requests_feed')
        
    item_request = get_object_or_404(ItemRequest, id=request_id)
    if item_request.requester != request.user:
        raise PermissionDenied("You are not authorized to delete this request.")
        
    item_request.delete()
    messages.success(request, "Your wishlist request has been deleted successfully.")
    return redirect('requests_feed')

@login_required
def initiate_request_chat(request, request_id):
    item_request = get_object_or_404(ItemRequest, id=request_id)
    
    # You cannot fulfill your own request
    if item_request.requester == request.user:
        messages.error(request, "You cannot initiate a fulfillment chat for your own request.")
        return redirect('requests_feed')
    
    # Get or create thread. Buyer is request creator, Seller is the fulfiller (current user)
    thread, created = ChatThread.objects.get_or_create(
        item_request=item_request,
        buyer=item_request.requester,
        seller=request.user
    )
    
    # If the thread was just created, create an initial message
    if created:
        Message.objects.create(
            thread=thread,
            sender=request.user,
            text=f"Hi {item_request.requester.first_name or item_request.requester.username}, I saw your request for '{item_request.title}' (Budget: {item_request.budget} UGX) and I think I can fulfill it! Let's chat."
        )
        
    return redirect('chat_room', thread_id=thread.id)


@login_required
def edit_profile(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user, phone_number=f"temp_{request.user.id}")
        
    error = None
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        hostel_or_area = request.POST.get('hostel_or_area', '').strip()
        profile_picture = request.FILES.get('profile_picture')
        remove_picture = request.POST.get('remove_picture') == 'true'
        
        if not first_name or not phone_number or not hostel_or_area:
            error = "First Name, Phone Number, and Hostel or Area are required."
        else:
            try:
                if Profile.objects.filter(phone_number=phone_number).exclude(id=profile.id).exists():
                    raise ValueError("Phone number is already registered by another user.")
                
                with transaction.atomic():
                    request.user.first_name = first_name
                    request.user.save()
                    
                    profile.phone_number = phone_number
                    profile.hostel_or_area = hostel_or_area
                    
                    if remove_picture:
                        if profile.profile_picture:
                            profile.profile_picture.delete(save=False)
                        profile.profile_picture = None
                    elif profile_picture:
                        profile.profile_picture = profile_picture
                        
                    profile.save()
                
                messages.success(request, "Your profile has been updated successfully!")
                return redirect('edit_profile')
            except Exception as e:
                error = str(e)
                
    return render(request, 'marketplace/edit_profile.html', {
        'profile': profile,
        'hostel_choices': Profile.HOSTEL_CHOICES,
        'error': error
    })


@login_required
def update_product_status(request, pk):
    """
    Allow product sellers to update the availability status of their items.
    """
    if request.method != 'POST':
        return redirect('product_detail', pk=pk)
        
    product = get_object_or_404(Product, pk=pk)
    
    if product.seller != request.user:
        messages.error(request, "You are not authorized to update this listing's status.")
        return redirect('product_detail', pk=pk)
        
    new_status = request.POST.get('status', '').strip()
    if new_status in ['available', 'sold', 'archived']:
        product.status = new_status
        product.save()
        if new_status == 'available':
            messages.success(request, f"Your product '{product.title}' has been relisted as available.")
        else:
            messages.success(request, f"Your product '{product.title}' is now marked as {new_status} and hidden from feeds.")
    else:
        messages.error(request, "Invalid status choice.")
        
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('product_detail', pk=pk)


@cache_control(no_cache=True, must_revalidate=True)
def service_worker(request):
    """Serves the PWA service worker JS from the root scope (/sw.js)."""
    import os
    from django.conf import settings
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    with open(sw_path, 'r') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')


@login_required
def delete_message(request, message_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
        
    message = get_object_or_404(Message, id=message_id)
    if message.sender != request.user:
        return JsonResponse({'error': 'Unauthorized: You can only delete your own messages.'}, status=403)
        
    message.delete()
    return JsonResponse({'status': 'success'})


@login_required
def delete_thread(request, thread_id):
    if request.method != 'POST':
        messages.error(request, "POST method required to delete conversation.")
        return redirect('inbox')
        
    thread = get_object_or_404(ChatThread, id=thread_id)
    if request.user != thread.buyer and request.user != thread.seller:
        messages.error(request, "You are not authorized to delete this conversation.")
        return redirect('inbox')
        
    thread.delete()
    messages.success(request, "Conversation deleted successfully.")
    return redirect('inbox')
