from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from functools import wraps

from .models import Product, Category, ChatThread, Message, Profile, ItemRequest, BannerImage

def staff_required(view_func):
    """
    Decorator to ensure user is logged in and is a staff member.
    """
    @login_required
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("You do not have administrative access.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@staff_required
def admin_dashboard_home(request):
    """
    Home page of the admin control panel showing site stats and recent activities.
    """
    total_products = Product.objects.count()
    total_requests = ItemRequest.objects.count()
    total_users = User.objects.count()
    total_chats = ChatThread.objects.count()
    total_messages = Message.objects.count()

    recent_products = Product.objects.all().order_by('-created_at')[:5]
    recent_requests = ItemRequest.objects.all().order_by('-created_at')[:5]
    recent_users = User.objects.all().order_by('-date_joined')[:5]

    context = {
        'active_page': 'dashboard',
        'total_products': total_products,
        'total_requests': total_requests,
        'total_users': total_users,
        'total_chats': total_chats,
        'total_messages': total_messages,
        'recent_products': recent_products,
        'recent_requests': recent_requests,
        'recent_users': recent_users,
    }
    return render(request, 'marketplace/admin_dashboard.html', context)


@staff_required
def admin_products_list(request):
    """
    Manage products page (list, filter, search, quick toggles).
    """
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()

    products = Product.objects.all()

    if query:
        products = products.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(seller__username__icontains=query) |
            Q(seller__first_name__icontains=query)
        )

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if status_filter:
        products = products.filter(status=status_filter)

    products = products.order_by('-created_at')
    categories = Category.objects.all()

    context = {
        'active_page': 'products',
        'products': products,
        'categories': categories,
        'selected_category': category_slug,
        'selected_status': status_filter,
        'query': query,
    }
    return render(request, 'marketplace/admin_products.html', context)


@staff_required
def admin_toggle_product(request, pk, field):
    """
    Toggle boolean flags or edit fields (featured, flash sale) of a product.
    Only supports POST to prevent unauthorized state manipulation.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    product = get_object_or_404(Product, pk=pk)
    
    if field == 'featured':
        product.is_featured = not product.is_featured
        product.save()
        messages.success(request, f"Product '{product.title}' featured status updated.")
    elif field == 'flash_sale':
        product.is_flash_sale = not product.is_flash_sale
        # If toggling flash sale ON, make sure it has a flash sale price
        if product.is_flash_sale and not product.flash_sale_price:
            product.flash_sale_price = int(product.price * 0.8)  # default 20% discount if missing
        product.save()
        messages.success(request, f"Product '{product.title}' flash sale status updated.")
    
    return redirect('admin_products_list')


@staff_required
def admin_update_product_status(request, pk):
    """
    Update the status (available, sold, archived) of a product.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    product = get_object_or_404(Product, pk=pk)
    new_status = request.POST.get('status', '').strip()
    
    if new_status in ['available', 'sold', 'archived']:
        product.status = new_status
        product.save()
        messages.success(request, f"Status of '{product.title}' updated to {new_status}.")
    else:
        messages.error(request, "Invalid status choice.")
        
    return redirect('admin_products_list')


@staff_required
def admin_delete_product(request, pk):
    """
    Delete a product from the database.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    product = get_object_or_404(Product, pk=pk)
    title = product.title
    product.delete()
    messages.success(request, f"Product '{title}' has been deleted.")
    return redirect('admin_products_list')


@staff_required
def admin_requests_list(request):
    """
    Manage item requests page.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    item_requests = ItemRequest.objects.all()

    if query:
        item_requests = item_requests.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(requester__username__icontains=query) |
            Q(requester__first_name__icontains=query)
        )

    if status_filter:
        item_requests = item_requests.filter(status=status_filter)

    item_requests = item_requests.order_by('-created_at')

    context = {
        'active_page': 'requests',
        'item_requests': item_requests,
        'selected_status': status_filter,
        'query': query,
    }
    return render(request, 'marketplace/admin_requests.html', context)


@staff_required
def admin_update_request_status(request, pk):
    """
    Update request status (open, fulfilled, cancelled).
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    item_request = get_object_or_404(ItemRequest, pk=pk)
    new_status = request.POST.get('status', '').strip()
    
    if new_status in ['open', 'fulfilled', 'cancelled']:
        item_request.status = new_status
        item_request.save()
        messages.success(request, f"Status of request '{item_request.title}' updated to {new_status}.")
    else:
        messages.error(request, "Invalid status choice.")
        
    return redirect('admin_requests_list')


@staff_required
def admin_delete_request(request, pk):
    """
    Delete an item request.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    item_request = get_object_or_404(ItemRequest, pk=pk)
    title = item_request.title
    item_request.delete()
    messages.success(request, f"Request '{title}' has been deleted.")
    return redirect('admin_requests_list')


@staff_required
def admin_users_list(request):
    """
    Manage users page.
    """
    query = request.GET.get('q', '').strip()
    staff_filter = request.GET.get('is_staff', '').strip()

    users = User.objects.all()

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(email__icontains=query) |
            Q(profile__phone_number__icontains=query)
        )

    if staff_filter == 'yes':
        users = users.filter(is_staff=True)
    elif staff_filter == 'no':
        users = users.filter(is_staff=False)

    users = users.order_by('-date_joined')

    context = {
        'active_page': 'users',
        'users': users,
        'selected_staff': staff_filter,
        'query': query,
    }
    return render(request, 'marketplace/admin_users.html', context)


@staff_required
def admin_toggle_user_staff(request, pk):
    """
    Toggle is_staff status of a user. Prevents self-demotion.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        messages.error(request, "You cannot modify your own administrative status.")
    else:
        user.is_staff = not user.is_staff
        user.save()
        status_str = "promoted to staff" if user.is_staff else "removed from staff"
        messages.success(request, f"User '{user.username}' has been {status_str}.")
        
    return redirect('admin_users_list')


@staff_required
def admin_delete_user(request, pk):
    """
    Delete a user and their profile from the database. Prevents self-deletion.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
    else:
        username = user.username
        user.delete()
        messages.success(request, f"User '{username}' has been deleted.")
        
    return redirect('admin_users_list')


@staff_required
def admin_categories_list(request):
    """
    List and manage categories.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "Category name cannot be empty.")
        elif Category.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Category '{name}' already exists.")
        else:
            category = Category.objects.create(name=name)
            messages.success(request, f"Category '{category.name}' created successfully.")
        return redirect('admin_categories_list')

    categories = Category.objects.all().order_by('name')
    
    context = {
        'active_page': 'categories',
        'categories': categories,
    }
    return render(request, 'marketplace/admin_categories.html', context)


@staff_required
def admin_delete_category(request, pk):
    """
    Delete a category.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    category.delete()
    messages.success(request, f"Category '{name}' has been deleted.")
    return redirect('admin_categories_list')


@staff_required
def admin_banners_list(request):
    """
    List currently uploaded card backgrounds and handle uploading of new ones.
    """
    if request.method == 'POST':
        card_type = request.POST.get('card_type', '').strip()
        image = request.FILES.get('image')
        order = request.POST.get('order', '0').strip()
        
        if not card_type or not image:
            messages.error(request, "Card Type and Background Image are required.")
        else:
            try:
                order_num = int(order) if order else 0
                banner = BannerImage.objects.create(
                    card_type=card_type,
                    image=image,
                    order=order_num
                )
                messages.success(request, f"New background image uploaded for {banner.get_card_type_display()}.")
            except Exception as e:
                messages.error(request, f"Error uploading background: {str(e)}")
        return redirect('admin_banners_list')

    # Group banners by card type or fetch all
    banners = BannerImage.objects.all()
    
    # Pre-split to make rendering easy
    big_card_banners = banners.filter(card_type='big_card')
    flash_banners = banners.filter(card_type='flash_sales')
    requests_banners = banners.filter(card_type='requests')
    bundles_banners = banners.filter(card_type='bundles')

    context = {
        'active_page': 'banners',
        'big_card_banners': big_card_banners,
        'flash_banners': flash_banners,
        'requests_banners': requests_banners,
        'bundles_banners': bundles_banners,
        'card_choices': BannerImage.CARD_CHOICES,
    }
    return render(request, 'marketplace/admin_banners.html', context)


@staff_required
def admin_delete_banner(request, pk):
    """
    Delete a banner image from database and storage.
    """
    if request.method != 'POST':
        raise PermissionDenied("Only POST requests are allowed.")
        
    banner = get_object_or_404(BannerImage, pk=pk)
    card_display = banner.get_card_type_display()
    
    # Delete image file from media storage
    if banner.image:
        banner.image.delete(save=False)
        
    banner.delete()
    messages.success(request, f"Background image for {card_display} deleted.")
    return redirect('admin_banners_list')


@staff_required
def admin_create_product(request):
    """
    Form to allow admin to add a product listing, including uploading an image.
    """
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip()
        category_id = request.POST.get('category', '').strip()
        seller_id = request.POST.get('seller', '').strip()
        status = request.POST.get('status', 'available').strip()
        is_featured = request.POST.get('is_featured') == 'on'
        is_flash_sale = request.POST.get('is_flash_sale') == 'on'
        flash_sale_price = request.POST.get('flash_sale_price', '').strip()
        image = request.FILES.get('image')

        if not title or not price or not category_id or not seller_id or not image:
            messages.error(request, "Title, Category, Price, Seller, and Product Image are required.")
        else:
            try:
                price = int(price)
                category = get_object_or_404(Category, id=category_id)
                seller = get_object_or_404(User, id=seller_id)
                
                flash_price_val = None
                if is_flash_sale and flash_sale_price:
                    flash_price_val = int(flash_sale_price)
                elif is_flash_sale:
                    flash_price_val = int(price * 0.8)  # default 20% discount
                
                product = Product.objects.create(
                    seller=seller,
                    category=category,
                    title=title,
                    description=description,
                    price=price,
                    image=image,
                    status=status,
                    is_featured=is_featured,
                    is_flash_sale=is_flash_sale,
                    flash_sale_price=flash_price_val
                )
                messages.success(request, f"Product '{product.title}' has been successfully created.")
                return redirect('admin_products_list')
            except Exception as e:
                messages.error(request, f"Error creating product: {str(e)}")

    categories = Category.objects.all().order_by('name')
    users = User.objects.all().order_by('username')
    
    context = {
        'active_page': 'products',
        'categories': categories,
        'users': users,
    }
    return render(request, 'marketplace/admin_create_product.html', context)


