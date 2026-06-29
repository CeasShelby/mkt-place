import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campus_marketplace.settings')
django.setup()

from marketplace.models import Product, BannerImage, ItemRequest, Profile

print("Starting clean_media_paths using direct DB updates...")

def clean_path(name):
    if name and (name.startswith('media/') or name.startswith('media\\')):
        return name[6:]
    return name

# 1. Clean Products
cleaned_products_count = 0
for p in Product.objects.all():
    if p.image:
        old_name = p.image.name
        new_name = clean_path(old_name)
        if old_name != new_name:
            Product.objects.filter(pk=p.pk).update(image=new_name)
            cleaned_products_count += 1
print(f"Cleaned {cleaned_products_count} Product image paths.")

# 2. Clean Banners
cleaned_banners_count = 0
for b in BannerImage.objects.all():
    if b.image:
        old_name = b.image.name
        new_name = clean_path(old_name)
        if old_name != new_name:
            BannerImage.objects.filter(pk=b.pk).update(image=new_name)
            cleaned_banners_count += 1
print(f"Cleaned {cleaned_banners_count} BannerImage image paths.")

# 3. Clean ItemRequests
cleaned_requests_count = 0
for r in ItemRequest.objects.all():
    if r.image:
        old_name = r.image.name
        new_name = clean_path(old_name)
        if old_name != new_name:
            ItemRequest.objects.filter(pk=r.pk).update(image=new_name)
            cleaned_requests_count += 1
print(f"Cleaned {cleaned_requests_count} ItemRequest image paths.")

# 4. Clean Profiles
cleaned_profiles_count = 0
for prof in Profile.objects.all():
    if prof.profile_picture:
        old_name = prof.profile_picture.name
        new_name = clean_path(old_name)
        if old_name != new_name:
            Profile.objects.filter(pk=prof.pk).update(profile_picture=new_name)
            cleaned_profiles_count += 1
print(f"Cleaned {cleaned_profiles_count} Profile picture paths.")

print("Image path cleaning completed successfully!")
