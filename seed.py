import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "campus_marketplace.settings")
django.setup()

from django.contrib.auth.models import User
from marketplace.models import Category, Product, Profile, BundleItem

# Create static directory to silence staticfiles warning
os.makedirs("static", exist_ok=True)
print("Created 'static' directory.")

# 1. Create categories
categories = [
    ("Textbooks", "textbooks"),
    ("Electronics", "electronics"),
    ("Hostel Furniture", "furniture"),
    ("Services", "services"),
    ("Room Setup Bundles", "bundles"),
    ("Clothing", "clothing"),
    ("Shoes", "shoes"),
    ("Kitchenware", "kitchenware"),
    ("Others", "others"),
]

for name, slug in categories:
    cat, created = Category.objects.get_or_create(name=name, defaults={"slug": slug})
    if created:
        print(f"Created category: {name}")


# 2. Create users & profiles
def create_student(
    username, password, first_name, email, phone, hostel, is_admin=False
):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first_name,
            "email": email,
            "is_staff": is_admin,
            "is_superuser": is_admin,
        },
    )
    if created:
        user.set_password(password)
        user.save()
        Profile.objects.create(user=user, phone_number=phone, hostel_or_area=hostel)
        print(f"Created student user: {username} (pass: {password})")
    return user


admin = create_student(
    "admin",
    "admin123",
    "Admin",
    "admin@simplymkt.com",
    "256770000000",
    "main_campus",
    is_admin=True,
)
buyer = create_student(
    "buyer",
    "studentpass",
    "Okello",
    "okello@gulu.ac.ug",
    "256770000001",
    "laroo",
    is_admin=False,
)
seller = create_student(
    "seller",
    "studentpass",
    "Akena",
    "akena@gulu.ac.ug",
    "256770000002",
    "main_campus",
    is_admin=False,
)

# 3. Create products with dummy pillow images
try:
    from PIL import Image
    import io
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    def save_dummy_image(name, color):
        img = Image.new("RGB", (300, 300), color=color)
        f = io.BytesIO()
        img.save(f, format="PNG")
        f.seek(0)
        # Save using Django's default_storage (saves locally in dev, uploads to Cloudinary in prod)
        if not default_storage.exists(name):
            default_storage.save(name, ContentFile(f.read()))
            print(f"Saved image to storage: {name}")
        else:
            print(f"Image already exists in storage: {name}")

    save_dummy_image("products/hp.png", "#10b981")
    save_dummy_image("products/book.png", "#3b82f6")
    save_dummy_image("products/bed.png", "#f59e0b")

    print("Generated dummy listing images.")
except Exception as e:
    print("Could not generate dummy images via Pillow:", e)

cat_elec = Category.objects.filter(slug="electronics").first()
cat_books = Category.objects.filter(slug="textbooks").first()
cat_furn = Category.objects.filter(slug="furniture").first()

p1, created1 = Product.objects.get_or_create(
    title="HP EliteBook 840 G5",
    defaults={
        "seller": seller,
        "category": cat_elec,
        "description": "Core i5 8th Gen, 8GB RAM, 256GB SSD. Ideal for Gulu computer science students. Clean keyboard and screen.",
        "price": 1200000,
        "image": "products/hp.png",
        "is_featured": True,
        "status": "available",
    },
)
if created1:
    print("Created featured product HP laptop")

p2, created2 = Product.objects.get_or_create(
    title="Calculus: Early Transcendentals",
    defaults={
        "seller": seller,
        "category": cat_books,
        "description": "10th Edition by Howard Anton. Hardcover. Very useful for Engineering and Math students.",
        "price": 45000,
        "image": "products/book.png",
        "is_featured": False,
        "status": "available",
    },
)
if created2:
    print("Created product Calculus book")

p3, created3 = Product.objects.get_or_create(
    title="Single Size Wooden Bed",
    defaults={
        "seller": seller,
        "category": cat_furn,
        "description": "Strong wood, fits well in small hostel rooms. Sold with or without mattress. Pick up from Laroo.",
        "price": 150000,
        "image": "products/bed.png",
        "is_featured": False,
        "status": "available",
    },
)
if created3:
    print("Created product wooden bed")

cat_bundles = Category.objects.filter(slug="bundles").first()

p4, created4 = Product.objects.get_or_create(
    title="Complete Laroo Room Setup Bundle",
    defaults={
        "seller": seller,
        "category": cat_bundles,
        "description": "Selling my entire room's contents as a single discounted bundle. Perfect for freshers moving to the Laroo area. Everything is in excellent condition and ready to move in!",
        "price": 350000,
        "image": "products/bed.png",
        "is_featured": True,
        "is_bundle": True,
        "status": "available",
    },
)
if created4:
    print("Created room setup bundle")
    BundleItem.objects.get_or_create(
        product=p4, name="Double Wooden Bed & Mattress", estimated_price=250000
    )
    BundleItem.objects.get_or_create(
        product=p4, name="Plastic Basin & Bucket Set", estimated_price=15000
    )
    BundleItem.objects.get_or_create(
        product=p4, name="Cooking Utensils & Plates", estimated_price=40000
    )
    BundleItem.objects.get_or_create(
        product=p4, name="Sony Subwoofer System", estimated_price=120000
    )
    print("Created bundle items")

# 4. Create Flash Sale items
cat_elec = Category.objects.filter(slug="electronics").first()
cat_shoes = Category.objects.filter(slug="shoes").first()

p_flash1, created_flash1 = Product.objects.get_or_create(
    title="Oraimo 20000mAh Power Bank",
    defaults={
        "seller": seller,
        "category": cat_elec,
        "description": "High capacity power bank with fast charging support. Keeps your devices running during Gulu load-shedding.",
        "price": 75000,
        "image": "products/hp.png",
        "is_featured": False,
        "is_flash_sale": True,
        "flash_sale_price": 35000,
        "status": "available",
    },
)
if created_flash1:
    print("Created flash sale power bank")

p_flash2, created_flash2 = Product.objects.get_or_create(
    title="Adidas Run Sneakers",
    defaults={
        "seller": seller,
        "category": cat_shoes,
        "description": "Comfortable campus walking shoes. Breathable mesh, size 42. Extremely lightweight.",
        "price": 120000,
        "image": "products/bed.png",
        "is_featured": False,
        "is_flash_sale": True,
        "flash_sale_price": 60000,
        "status": "available",
    },
)
if created_flash2:
    print("Created flash sale sneakers")

p_flash3, created_flash3 = Product.objects.get_or_create(
    title="Bluetooth Subwoofer Speaker",
    defaults={
        "seller": seller,
        "category": cat_elec,
        "description": "Compact portable speaker with high bass output. Bluetooth 5.0, rechargeable battery.",
        "price": 180000,
        "image": "products/hp.png",
        "is_featured": False,
        "is_flash_sale": True,
        "flash_sale_price": 90000,
        "status": "available",
    },
)
if created_flash3:
    print("Created flash sale subwoofer")

print("Seeding completed successfully!")
