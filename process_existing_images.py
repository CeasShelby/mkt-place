import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campus_marketplace.settings')
django.setup()

from marketplace.models import Product, BannerImage, ItemRequest

print("Starting background removal process on existing products...")
for product in Product.objects.all():
    if product.image:
        print(f"Processing product image: {product.title} (ID: {product.id})")
        try:
            # Re-saving runs the make_image_background_transparent_floodfill
            product.save()
            print(f"-> Successfully processed {product.title}")
        except Exception as e:
            print(f"-> Error processing product {product.id}: {e}")

print("Processing background removal on existing item requests...")
for req in ItemRequest.objects.all():
    if req.image:
        print(f"Processing request image: {req.title} (ID: {req.id})")
        try:
            req.save()
            print(f"-> Successfully processed {req.title}")
        except Exception as e:
            print(f"-> Error processing request {req.id}: {e}")

print("Processing background removal on existing banner images...")
for banner in BannerImage.objects.all():
    if banner.image:
        print(f"Processing banner image ID: {banner.id}")
        try:
            banner.save()
            print(f"-> Successfully processed banner {banner.id}")
        except Exception as e:
            print(f"-> Error processing banner {banner.id}: {e}")

print("All existing images processed!")
