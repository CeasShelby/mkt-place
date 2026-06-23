import urllib.parse
import io
import os
from PIL import Image
from django.core.files.base import ContentFile
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

def resize_image_field(image_field, max_size=(800, 800)):
    if not image_field:
        return None
    try:
        if hasattr(image_field, 'open'):
            try:
                image_field.open()
            except Exception:
                pass
        # Seek to 0 to read from the beginning
        image_field.seek(0)
        # Open using PIL
        img = Image.open(image_field)
        if img.width > max_size[0] or img.height > max_size[1]:
            # Determine format - check if name is png or mode indicates transparency
            filename = getattr(image_field, 'name', '') or ''
            is_png = filename.lower().endswith('.png') or img.mode in ('RGBA', 'LA')
            img_format = 'PNG' if is_png else (img.format or 'JPEG')
            
            # For transparent images, convert RGBA/LA to RGB with a white background if saving as JPEG
            if img.mode in ('RGBA', 'LA') and img_format in ('JPEG', 'JPG'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB' and img_format in ('JPEG', 'JPG'):
                img = img.convert('RGB')
                
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            temp_handle = io.BytesIO()
            if img_format == 'PNG':
                img.save(temp_handle, format='PNG')
            else:
                img.save(temp_handle, format=img_format, quality=85)
            temp_handle.seek(0)
            
            # Update the field's file content name extension if format changed to PNG
            base_name, ext = os.path.splitext(os.path.basename(image_field.name))
            new_ext = '.png' if img_format == 'PNG' else ext
            new_file = ContentFile(temp_handle.read(), name=f"{base_name}{new_ext}")
            return new_file
    except Exception as e:
        print(f"Error resizing image: {e}")
    return None

def make_image_background_transparent_floodfill(image_field, tolerance=35):
    if not image_field:
        return None
    try:
        if hasattr(image_field, 'open'):
            try:
                image_field.open()
            except Exception:
                pass
        # Seek to 0 to read from the beginning
        image_field.seek(0)
        from PIL import ImageDraw
        img = Image.open(image_field)

        img = img.convert("RGBA")
        width, height = img.size
        
        # Create a mask initialized to 0 (foreground)
        mask = Image.new("L", (width, height), 0)
        
        # Border points: 4 corners + 4 edge centers to detect backgrounds that are not perfectly clean
        border_points = [
            (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
            (width // 2, 0), (width // 2, height - 1),
            (0, height // 2), (width - 1, height // 2)
        ]
        
        filled_any = False
        for x, y in border_points:
            pixel = img.getpixel((x, y))
            # Average of R, G, B channels
            brightness = sum(pixel[:3]) / 3
            # Only floodfill if the pixel is not transparent and is relatively light/off-white (brightness > 180)
            if (len(pixel) < 4 or pixel[3] > 0) and brightness > 180:
                ImageDraw.floodfill(mask, (x, y), 255, thresh=tolerance)
                filled_any = True
                
        # If no border points were light colored, we don't apply the mask
        if not filled_any:
            return None
        
        # Convert pixels where mask is 255 to transparent
        datas = img.getdata()
        mask_datas = mask.getdata()
        newData = []
        for i in range(len(datas)):
            if mask_datas[i] == 255:
                newData.append((255, 255, 255, 0)) # transparent
            else:
                newData.append(datas[i])
        
        img.putdata(newData)
        
        # Save as PNG to preserve transparency
        temp_handle = io.BytesIO()
        img.save(temp_handle, format='PNG')
        temp_handle.seek(0)
        
        # Get base name and change extension to png
        base_name = os.path.splitext(os.path.basename(image_field.name))[0]
        new_file = ContentFile(temp_handle.read(), name=f"{base_name}_transparent.png")
        return new_file
    except Exception as e:
        print(f"Error in background removal: {e}")
    return None

def remove_background_via_api(image_field):
    api_key = os.getenv('REMOVE_BG_API_KEY')
    if not api_key:
        return None
    try:
        import requests
        if hasattr(image_field, 'open'):
            try:
                image_field.open()
            except Exception:
                pass
        image_field.seek(0)
        image_bytes = image_field.read()
        image_field.seek(0)
        
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            files={'image_file': image_bytes},
            data={'size': 'auto'},
            headers={'X-Api-Key': api_key},
            timeout=15
        )
        if response.status_code == 200:
            base_name = os.path.splitext(os.path.basename(image_field.name))[0]
            new_file = ContentFile(response.content, name=f"{base_name}_transparent.png")
            return new_file
        else:
            print(f"Error from remove.bg API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception during remove.bg API call: {e}")
    return None

class Profile(models.Model):
    HOSTEL_CHOICES = [
        ('main_campus', 'Main Campus'),
        ('laroo', 'Laroo'),
        ('pece', 'Pece'),
        ('for_god', 'For God'),
        ('custom_corner', 'Custom Corner'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(verbose_name='Phone Number', max_length=20, unique=True)
    hostel_or_area = models.CharField(
        max_length=50,
        choices=HOSTEL_CHOICES,
        default='main_campus'
    )
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        if self.profile_picture:
            resized = resize_image_field(self.profile_picture, (300, 300))
            if resized:
                self.profile_picture = resized
        super().save(*args, **kwargs)

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('sold', 'Sold'),
        ('archived', 'Archived'),
    ]
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.PositiveIntegerField(help_text="Price in UGX")
    image = models.ImageField(upload_to='products/')
    is_featured = models.BooleanField(default=False)
    is_bundle = models.BooleanField(default=False)
    is_flash_sale = models.BooleanField(default=False)
    flash_sale_price = models.PositiveIntegerField(null=True, blank=True, help_text="Special price during Flash Sale Hour")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        force_process = kwargs.pop('force_image_process', False)
        
        is_new_image = False
        if not self.pk:
            is_new_image = True
        else:
            try:
                orig = Product.objects.get(pk=self.pk)
                if orig.image != self.image:
                    is_new_image = True
            except Product.DoesNotExist:
                is_new_image = True

        if (is_new_image or force_process) and self.image:
            transparent_img = remove_background_via_api(self.image)
            if not transparent_img:
                transparent_img = make_image_background_transparent_floodfill(self.image)
            if transparent_img:
                self.image = transparent_img
            resized = resize_image_field(self.image, (800, 800))
            if resized:
                self.image = resized
        super().save(*args, **kwargs)

    @property
    def bundle_total_individual_price(self):
        if not self.is_bundle:
            return 0
        return sum(item.estimated_price or 0 for item in self.bundle_items.all())

    @property
    def bundle_savings(self):
        if not self.is_bundle:
            return 0
        total_indiv = self.bundle_total_individual_price
        if total_indiv > self.price:
            return total_indiv - self.price
        return 0

    def get_current_price(self):
        if self.is_flash_sale:
            from django.utils import timezone
            import datetime
            local_now = timezone.localtime(timezone.now())
            if local_now.weekday() == 4 and datetime.time(18, 0) <= local_now.time() <= datetime.time(20, 0):
                return self.flash_sale_price
        return self.price

    @property
    def flash_sale_discount_percent(self):
        if not self.price or not self.flash_sale_price:
            return 0
        discount = self.price - self.flash_sale_price
        return int((discount / self.price) * 100)

    @property
    def whatsapp_link(self):
        first_name = self.seller.first_name if self.seller.first_name else self.seller.username
        phone_number = self.seller.profile.phone_number if hasattr(self.seller, 'profile') else ""
        
        # Clean the phone number for WhatsApp wa.me links
        # 1. Remove all non-digits (spaces, dashes, parentheses, +, etc.)
        cleaned_phone = "".join(c for c in phone_number if c.isdigit())
        
        # 2. Standardize prefix to international Gulu format (Uganda = 256)
        if cleaned_phone.startswith('0'):
            # Convert e.g. 0771234567 to 256771234567
            cleaned_phone = '256' + cleaned_phone[1:]
        elif not cleaned_phone.startswith('256') and len(cleaned_phone) == 9:
            # If 9 digits and not starting with 256, prepend it
            cleaned_phone = '256' + cleaned_phone
            
        current_p = self.get_current_price()
        message = f"Hi {first_name}, I saw your listing for '{self.title}' ({current_p} UGX) on the Campus Marketplace. Is it still available?"
        encoded_message = urllib.parse.quote(message)
        return f"https://wa.me/{cleaned_phone}?text={encoded_message}"

class BundleItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bundle_items')
    name = models.CharField(max_length=150)
    estimated_price = models.PositiveIntegerField(help_text="Estimated price if sold individually", null=True, blank=True)

    def __str__(self):
        return f"{self.name} (for bundle: {self.product.title})"

class ItemRequest(models.Model):
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='item_requests')
    title = models.CharField(max_length=200)
    description = models.TextField()
    budget = models.PositiveIntegerField(help_text="Budget in UGX")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='item_requests')
    image = models.ImageField(upload_to='requests/', null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('open', 'Open'), ('fulfilled', 'Fulfilled'), ('cancelled', 'Cancelled')],
        default='open'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Request: {self.title} by {self.requester.username}"

    def save(self, *args, **kwargs):
        force_process = kwargs.pop('force_image_process', False)
        
        is_new_image = False
        if not self.pk:
            is_new_image = True
        else:
            try:
                orig = ItemRequest.objects.get(pk=self.pk)
                if orig.image != self.image:
                    is_new_image = True
            except ItemRequest.DoesNotExist:
                is_new_image = True

        if (is_new_image or force_process) and self.image:
            transparent_img = remove_background_via_api(self.image)
            if not transparent_img:
                transparent_img = make_image_background_transparent_floodfill(self.image)
            if transparent_img:
                self.image = transparent_img
            resized = resize_image_field(self.image, (800, 800))
            if resized:
                self.image = resized
        super().save(*args, **kwargs)

class ChatThread(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_threads')
    item_request = models.ForeignKey(ItemRequest, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_threads')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_threads')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_threads')

    class Meta:
        unique_together = (
            ('product', 'buyer', 'seller'),
            ('item_request', 'buyer', 'seller'),
        )

    def __str__(self):
        title = self.product.title if self.product else (self.item_request.title if self.item_request else "Request")
        return f"Chat for {title} between {self.buyer.username} and {self.seller.username}"

class Message(models.Model):
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.sender.username} in Thread {self.thread_id} at {self.created_at}"


from django.utils import timezone

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_otps')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        # Valid for 10 minutes
        return (timezone.now() - self.created_at).total_seconds() < 600

    def __str__(self):
        return f"OTP for {self.user.username} (Created: {self.created_at})"


class BannerImage(models.Model):
    CARD_CHOICES = [
        ('big_card', 'Big Hero Card'),
        ('flash_sales', 'Flash Sales Card'),
        ('requests', 'Requests Card'),
        ('bundles', 'Setup Bundles Card'),
    ]
    card_type = models.CharField(max_length=20, choices=CARD_CHOICES)
    image = models.ImageField(upload_to='banners/')
    order = models.PositiveIntegerField(default=0, help_text="Order of display for big card slideshow")

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.get_card_type_display()} Image ({self.id})"

    def save(self, *args, **kwargs):
        force_process = kwargs.pop('force_image_process', False)
        
        is_new_image = False
        if not self.pk:
            is_new_image = True
        else:
            try:
                orig = BannerImage.objects.get(pk=self.pk)
                if orig.image != self.image:
                    is_new_image = True
            except BannerImage.DoesNotExist:
                is_new_image = True

        if (is_new_image or force_process) and self.image:
            transparent_img = remove_background_via_api(self.image)
            if not transparent_img:
                transparent_img = make_image_background_transparent_floodfill(self.image)
            if transparent_img:
                self.image = transparent_img
        super().save(*args, **kwargs)


