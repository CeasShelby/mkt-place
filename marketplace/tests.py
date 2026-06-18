from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Category, Product, Profile, ChatThread, Message, PasswordResetOTP, BundleItem, ItemRequest, BannerImage
import urllib.parse

class MarketplaceTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create users & profiles
        self.buyer_user = User.objects.create_user(
            username='testbuyer',
            password='testpassword',
            first_name='BuyerName'
        )
        self.buyer_profile = Profile.objects.create(
            user=self.buyer_user,
            phone_number='256770000001',
            hostel_or_area='laroo'
        )
        
        self.seller_user = User.objects.create_user(
            username='testseller',
            password='testpassword',
            first_name='SellerName'
        )
        self.seller_profile = Profile.objects.create(
            user=self.seller_user,
            phone_number='256770000002',
            hostel_or_area='main_campus'
        )
        
        # Create category
        self.category = Category.objects.create(name='Electronics')
        
        # Create sample image
        self.dummy_image = SimpleUploadedFile(
            name='test_image.jpg',
            content=b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
            content_type='image/jpeg'
        )
        
        # Create products
        self.product = Product.objects.create(
            seller=self.seller_user,
            category=self.category,
            title='iPhone 11',
            description='Slightly used black iPhone 11',
            price=1500000,
            image=self.dummy_image,
            is_featured=True,
            status='available'
        )

    def test_category_slugify(self):
        # Category should automatically slugify on save
        cat = Category.objects.create(name='Hostel & Living Essentials')
        self.assertEqual(cat.slug, 'hostel-living-essentials')

    def test_whatsapp_link_property(self):
        expected_msg = "Hi SellerName, I saw your listing for 'iPhone 11' (1500000 UGX) on the Campus Marketplace. Is it still available?"
        encoded_msg = urllib.parse.quote(expected_msg)
        expected_link = f"https://wa.me/256770000002?text={encoded_msg}"
        self.assertEqual(self.product.whatsapp_link, expected_link)

    def test_home_feed_view(self):
        response = self.client.get(reverse('home_feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPhone 11')
        
        # Test category filtering
        response_filtered = self.client.get(reverse('home_feed') + '?category=electronics')
        self.assertEqual(response_filtered.status_code, 200)
        self.assertContains(response_filtered, 'iPhone 11')

        response_empty = self.client.get(reverse('home_feed') + '?category=other')
        self.assertEqual(response_empty.status_code, 200)
        self.assertNotContains(response_empty, 'iPhone 11')

    def test_home_feed_separates_bundles_and_standard_listings(self):
        bundle = Product.objects.create(
            seller=self.seller_user,
            category=self.category,
            title='Separated Bundle Package',
            description='Mattress and basin',
            price=200000,
            image=self.dummy_image,
            is_bundle=True,
            status='available'
        )
        
        response = self.client.get(reverse('home_feed'))
        self.assertEqual(response.status_code, 200)
        
        self.assertIn(bundle, response.context['bundles'])
        self.assertNotIn(bundle, response.context['featured_products'])
        self.assertNotIn(bundle, response.context['recent_products'])
        self.assertNotIn(self.product, response.context['bundles'])

    def test_product_detail_view(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPhone 11')
        self.assertContains(response, '1,500,000 UGX')
        self.assertContains(response, 'Seller: SellerName')

    def test_initiate_chat_unauthenticated(self):
        response = self.client.get(reverse('initiate_chat', args=[self.product.id]))
        self.assertEqual(response.status_code, 302) # Redirect to login

    def test_initiate_chat_authenticated(self):
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('initiate_chat', args=[self.product.id]))
        
        # Verify thread was created
        thread = ChatThread.objects.get(product=self.product, buyer=self.buyer_user, seller=self.seller_user)
        self.assertIsNotNone(thread)
        
        # Redirect to chat room
        self.assertRedirects(response, reverse('chat_room', args=[thread.id]))

    def test_chat_room_authorization(self):
        thread = ChatThread.objects.create(product=self.product, buyer=self.buyer_user, seller=self.seller_user)
        
        # Unauthenticated: redirect to login
        response = self.client.get(reverse('chat_room', args=[thread.id]))
        self.assertEqual(response.status_code, 302)

        # Authenticated as buyer: 200 OK
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('chat_room', args=[thread.id]))
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # Authenticated as random user: 403 Forbidden
        random_user = User.objects.create_user(username='random', password='testpassword')
        self.client.login(username='random', password='testpassword')
        response = self.client.get(reverse('chat_room', args=[thread.id]))
        self.assertEqual(response.status_code, 403)

    def test_api_send_and_get_messages(self):
        thread = ChatThread.objects.create(product=self.product, buyer=self.buyer_user, seller=self.seller_user)
        
        self.client.login(username='testbuyer', password='testpassword')
        
        # Send a message
        response = self.client.post(
            reverse('api_send_message', args=[thread.id]),
            data={'text': 'Hello, is it negotiable?'},
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        # Retrieve messages
        response_get = self.client.get(reverse('api_get_messages', args=[thread.id]))
        self.assertEqual(response_get.status_code, 200)
        messages_data = response_get.json()['messages']
        self.assertEqual(len(messages_data), 1)
        self.assertEqual(messages_data[0]['text'], 'Hello, is it negotiable?')
        self.assertEqual(messages_data[0]['sender'], 'testbuyer')
        
        # Retrieve messages with last_id filtering
        last_id = messages_data[0]['id']
        response_get_filtered = self.client.get(reverse('api_get_messages', args=[thread.id]) + f'?last_id={last_id}')
        self.assertEqual(len(response_get_filtered.json()['messages']), 0)

    def test_create_product_view_unauthenticated(self):
        response = self.client.get(reverse('create_product'))
        self.assertEqual(response.status_code, 302)

    def test_create_product_view_authenticated_get(self):
        self.client.login(username='testseller', password='testpassword')
        response = self.client.get(reverse('create_product'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'List a New Item')

    def test_create_product_view_authenticated_post(self):
        self.client.login(username='testseller', password='testpassword')
        post_data = {
            'title': 'Test Textbook',
            'description': 'Description here',
            'price': '35000',
            'category': self.category.id,
            'image': self.dummy_image
        }
        response = self.client.post(reverse('create_product'), data=post_data)
        new_product = Product.objects.get(title='Test Textbook')
        self.assertRedirects(response, reverse('product_detail', args=[new_product.pk]))

    def test_inbox_view_unauthenticated(self):
        response = self.client.get(reverse('inbox'))
        self.assertEqual(response.status_code, 302)

    def test_inbox_view_authenticated(self):
        thread = ChatThread.objects.create(product=self.product, buyer=self.buyer_user, seller=self.seller_user)
        Message.objects.create(thread=thread, sender=self.buyer_user, text="Interested in buying!")

        self.client.login(username='testseller', password='testpassword')
        response = self.client.get(reverse('inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPhone 11')
        self.assertContains(response, 'BuyerName')
        self.assertContains(response, 'Interested in buying!')

    def test_forgot_password_email_lookup_failure(self):
        response = self.client.post(reverse('forgot_password'), {'email': 'unknown@student.gu.ac.ug'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No account found with this email address.')

    def test_forgot_password_success_creates_otp_and_sends_email(self):
        self.buyer_user.email = 'buyer@student.gu.ac.ug'
        self.buyer_user.save()
        
        response = self.client.post(reverse('forgot_password'), {'email': 'buyer@student.gu.ac.ug'})
        self.assertEqual(response.status_code, 302)
        
        otp_record = PasswordResetOTP.objects.filter(user=self.buyer_user).first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(len(otp_record.otp), 6)
        
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(otp_record.otp, mail.outbox[0].body)

    def test_verify_otp_and_reset_password_success(self):
        self.buyer_user.email = 'buyer@student.gu.ac.ug'
        self.buyer_user.save()
        
        otp_record = PasswordResetOTP.objects.create(user=self.buyer_user, otp='987654')
        
        response = self.client.post(reverse('verify_otp'), {
            'email': 'buyer@student.gu.ac.ug',
            'otp': '987654',
            'password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        self.assertEqual(response.status_code, 302)
        
        self.buyer_user.refresh_from_db()
        self.assertTrue(self.buyer_user.check_password('newpassword123'))
        self.assertFalse(PasswordResetOTP.objects.filter(user=self.buyer_user).exists())

    def test_verify_otp_invalid_or_expired(self):
        self.buyer_user.email = 'buyer@student.gu.ac.ug'
        self.buyer_user.save()
        
        from django.utils import timezone
        import datetime
        otp_record = PasswordResetOTP.objects.create(user=self.buyer_user, otp='987654')
        PasswordResetOTP.objects.filter(id=otp_record.id).update(created_at=timezone.now() - datetime.timedelta(minutes=11))
        
        response = self.client.post(reverse('verify_otp'), {
            'email': 'buyer@student.gu.ac.ug',
            'otp': '987654',
            'password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'expired')
        
        otp_record_new = PasswordResetOTP.objects.create(user=self.buyer_user, otp='111222')
        response = self.client.post(reverse('verify_otp'), {
            'email': 'buyer@student.gu.ac.ug',
            'otp': '000000',
            'password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid or incorrect OTP code.')

    def test_bundle_properties(self):
        bundle_product = Product.objects.create(
            seller=self.seller_user,
            category=self.category,
            title='Laroo Student Room Setup',
            description='Mattress, subwoofer, basin',
            price=200000,
            image=self.dummy_image,
            is_bundle=True,
            status='available'
        )
        BundleItem.objects.create(product=bundle_product, name='Super Double Mattress', estimated_price=150000)
        BundleItem.objects.create(product=bundle_product, name='Sony Subwoofer Speaker', estimated_price=80000)
        BundleItem.objects.create(product=bundle_product, name='Basin & Bucket', estimated_price=20000)

        # Check total individual price (150k + 80k + 20k = 250k)
        self.assertEqual(bundle_product.bundle_total_individual_price, 250000)
        # Check savings (250k - 200k = 50k)
        self.assertEqual(bundle_product.bundle_savings, 50000)

    def test_create_bundle_view_authenticated_post(self):
        self.client.login(username='testseller', password='testpassword')
        post_data = {
            'title': 'Laroo Setup Bundle Pack',
            'description': 'Full room details.',
            'price': '300000',
            'category': self.category.id,
            'image': self.dummy_image,
            'item_name[]': ['Sony Subwoofer System', 'Wooden bed frame'],
            'item_price[]': ['120000', '250000']
        }
        response = self.client.post(reverse('create_bundle'), data=post_data)
        
        # Verify redirect
        new_bundle = Product.objects.get(title='Laroo Setup Bundle Pack')
        self.assertRedirects(response, reverse('product_detail', args=[new_bundle.pk]))
        
        # Verify fields and items
        self.assertTrue(new_bundle.is_bundle)
        items = new_bundle.bundle_items.all()
        self.assertEqual(items.count(), 2)
        self.assertEqual(items.filter(name='Sony Subwoofer System').first().estimated_price, 120000)
        self.assertEqual(items.filter(name='Wooden bed frame').first().estimated_price, 250000)
        self.assertEqual(new_bundle.bundle_savings, 70000)

    def test_requests_feed_view(self):
        # Create a wanted item request
        req = ItemRequest.objects.create(
            requester=self.buyer_user,
            title='Needed: lab coat',
            description='White color, size L',
            budget=25000,
            category=self.category,
            status='open'
        )
        response = self.client.get(reverse('requests_feed'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Needed: lab coat')
        self.assertContains(response, '25,000 UGX')

    def test_create_request_view_authenticated_post(self):
        self.client.login(username='testbuyer', password='testpassword')
        post_data = {
            'title': 'Desperately need calculator',
            'description': 'Casio FX-991EX',
            'budget': '40000',
            'category': self.category.id,
        }
        response = self.client.post(reverse('create_request'), data=post_data)
        
        # Verify redirect
        self.assertRedirects(response, reverse('requests_feed'))
        new_req = ItemRequest.objects.get(title='Desperately need calculator')
        self.assertEqual(new_req.budget, 40000)
        self.assertEqual(new_req.requester, self.buyer_user)
        self.assertFalse(new_req.image)

    def test_initiate_request_chat_authenticated(self):
        # Create request by buyer
        req = ItemRequest.objects.create(
            requester=self.buyer_user,
            title='Needed: lab coat',
            description='White color, size L',
            budget=25000,
            category=self.category,
            status='open'
        )
        
        # Login as seller (fulfiller)
        self.client.login(username='testseller', password='testpassword')
        response = self.client.get(reverse('initiate_request_chat', args=[req.id]))
        
        # Verify chat thread was created
        thread = ChatThread.objects.get(item_request=req, buyer=self.buyer_user, seller=self.seller_user)
        self.assertIsNotNone(thread)
        self.assertRedirects(response, reverse('chat_room', args=[thread.id]))
        
        # Verify auto-generated first message exists
        first_msg = thread.messages.first()
        self.assertIsNotNone(first_msg)
        self.assertIn("Needed: lab coat", first_msg.text)
        self.assertIn("25000 UGX", first_msg.text)

    def test_dynamic_category_creation_product(self):
        self.client.login(username='testseller', password='testpassword')
        post_data = {
            'title': 'Test Item in New Cat',
            'description': 'Description here',
            'price': '10000',
            'category': '__new__',
            'new_category_name': 'Clothing',
            'image': self.dummy_image
        }
        response = self.client.post(reverse('create_product'), data=post_data)
        
        # Verify category was created
        cat = Category.objects.get(name='Clothing')
        self.assertEqual(cat.slug, 'clothing')
        
        # Verify product is linked to it
        prod = Product.objects.get(title='Test Item in New Cat')
        self.assertEqual(prod.category, cat)

    def test_dynamic_category_creation_bundle(self):
        self.client.login(username='testseller', password='testpassword')
        post_data = {
            'title': 'Test Bundle in New Cat',
            'description': 'Description here',
            'price': '30000',
            'category': '__new__',
            'new_category_name': 'Shoes',
            'image': self.dummy_image,
            'item_name[]': ['Running Shoes'],
            'item_price[]': ['40000']
        }
        response = self.client.post(reverse('create_bundle'), data=post_data)
        
        # Verify category was created
        cat = Category.objects.get(name='Shoes')
        self.assertEqual(cat.slug, 'shoes')
        
        # Verify bundle is linked to it
        prod = Product.objects.get(title='Test Bundle in New Cat')
        self.assertEqual(prod.category, cat)

    def test_dynamic_category_creation_request(self):
        self.client.login(username='testbuyer', password='testpassword')
        post_data = {
            'title': 'Test Request in New Cat',
            'description': 'Description here',
            'budget': '5000',
            'category': '__new__',
            'new_category_name': 'Kitchenware'
        }
        response = self.client.post(reverse('create_request'), data=post_data)
        
        # Verify category was created
        cat = Category.objects.get(name='Kitchenware')
        self.assertEqual(cat.slug, 'kitchenware')
        
        # Verify request is linked to it
        req = ItemRequest.objects.get(title='Test Request in New Cat')
        self.assertEqual(req.category, cat)

    def test_dynamic_category_case_insensitivity(self):
        self.client.login(username='testseller', password='testpassword')
        
        # Create 'Clothing' category
        cat_initial = Category.objects.create(name='Clothing')
        
        # Submit new product with 'clothing' (lowercase)
        post_data = {
            'title': 'Test Item 2',
            'description': 'Description',
            'price': '10000',
            'category': '__new__',
            'new_category_name': 'clothing',
            'image': self.dummy_image
        }
        response = self.client.post(reverse('create_product'), data=post_data)
        
        # Verify that NO duplicate category was created
        self.assertEqual(Category.objects.filter(name__iexact='clothing').count(), 1)
        
        # Verify product is linked to existing category
        prod = Product.objects.get(title='Test Item 2')
        self.assertEqual(prod.category, cat_initial)

    def test_image_auto_resizing_on_product_save(self):
        from PIL import Image
        import io
        import os
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        img_io = io.BytesIO()
        large_img = Image.new('RGB', (1200, 1200), color='blue')
        large_img.save(img_io, format='JPEG')
        img_io.seek(0)
        
        large_uploaded_image = SimpleUploadedFile(
            name='large_image.jpg',
            content=img_io.read(),
            content_type='image/jpeg'
        )
        
        product = Product.objects.create(
            seller=self.seller_user,
            category=self.category,
            title='Large Image Test',
            description='Test description',
            price=20000,
            image=large_uploaded_image
        )
        
        with Image.open(product.image.path) as saved_img:
            self.assertTrue(saved_img.width <= 800)
            self.assertTrue(saved_img.height <= 800)
            self.assertEqual(saved_img.width, saved_img.height)
        
        if os.path.exists(product.image.path):
            os.remove(product.image.path)

    def test_edit_profile_view_get_authenticated(self):
        self.client.login(username='testseller', password='testpassword')
        response = self.client.get(reverse('edit_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profile Settings')
        self.assertContains(response, self.seller_profile.phone_number)

    def test_edit_profile_view_post_updates_profile(self):
        self.client.login(username='testseller', password='testpassword')
        
        from PIL import Image
        import io
        import os
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        img_io = io.BytesIO()
        large_img = Image.new('RGB', (600, 600), color='green')
        large_img.save(img_io, format='JPEG')
        img_io.seek(0)
        large_avatar = SimpleUploadedFile(
            name='avatar.jpg',
            content=img_io.read(),
            content_type='image/jpeg'
        )
        
        post_data = {
            'first_name': 'NewSellerName',
            'phone_number': '256779999999',
            'hostel_or_area': 'laroo',
            'profile_picture': large_avatar
        }
        
        response = self.client.post(reverse('edit_profile'), data=post_data)
        self.assertRedirects(response, reverse('edit_profile'))
        
        self.seller_user.refresh_from_db()
        self.seller_profile.refresh_from_db()
        
        self.assertEqual(self.seller_user.first_name, 'NewSellerName')
        self.assertEqual(self.seller_profile.phone_number, '256779999999')
        self.assertEqual(self.seller_profile.hostel_or_area, 'laroo')
        self.assertTrue(self.seller_profile.profile_picture)
        
        with Image.open(self.seller_profile.profile_picture.path) as avatar_img:
            self.assertTrue(avatar_img.width <= 300)
            self.assertTrue(avatar_img.height <= 300)
        
        # Test picture deletion
        avatar_path = self.seller_profile.profile_picture.path
        post_data_remove = {
            'first_name': 'NewSellerName',
            'phone_number': '256779999999',
            'hostel_or_area': 'laroo',
            'remove_picture': 'true'
        }
        response = self.client.post(reverse('edit_profile'), data=post_data_remove)
        self.assertRedirects(response, reverse('edit_profile'))
        
        self.seller_profile.refresh_from_db()
        self.assertFalse(self.seller_profile.profile_picture)
        self.assertFalse(os.path.exists(avatar_path))

    def test_get_flash_sale_status_active(self):
        from unittest.mock import patch
        import datetime
        from django.utils import timezone

        # Friday 19:00 Kampala time (which is Friday 16:00 UTC since Kampala is UTC+3)
        friday_active_utc = datetime.datetime(2026, 6, 19, 16, 0, 0, tzinfo=datetime.timezone.utc)
        
        with patch('django.utils.timezone.now', return_value=friday_active_utc):
            from .views import get_flash_sale_status
            status = get_flash_sale_status()
            self.assertTrue(status['is_active'])
            
            # Since it is active, end_time should be Friday 20:00 Kampala time
            expected_end = timezone.make_aware(datetime.datetime(2026, 6, 19, 20, 0, 0))
            self.assertEqual(status['end_time'], expected_end)

    def test_get_flash_sale_status_inactive(self):
        from unittest.mock import patch
        import datetime
        from django.utils import timezone

        # Wednesday 10:00 Kampala time (which is Wednesday 7:00 UTC)
        wednesday_utc = datetime.datetime(2026, 6, 17, 7, 0, 0, tzinfo=datetime.timezone.utc)
        
        with patch('django.utils.timezone.now', return_value=wednesday_utc):
            from .views import get_flash_sale_status
            status = get_flash_sale_status()
            self.assertFalse(status['is_active'])
            
            # next_start should be Friday 18:00 Kampala time
            expected_start = timezone.make_aware(datetime.datetime(2026, 6, 19, 18, 0, 0))
            self.assertEqual(status['next_start'], expected_start)

    def test_product_get_current_price(self):
        from unittest.mock import patch
        import datetime
        from django.utils import timezone

        # Create a product with flash sale price
        flash_prod = Product.objects.create(
            seller=self.seller_user,
            category=self.category,
            title='Flash Sneakers',
            description='Exclusive deal',
            price=100000,
            flash_sale_price=50000,
            is_flash_sale=True,
            image=self.dummy_image
        )
        
        # 1. Friday 19:00 Kampala (16:00 UTC) -> Active
        friday_active_utc = datetime.datetime(2026, 6, 19, 16, 0, 0, tzinfo=datetime.timezone.utc)
        with patch('django.utils.timezone.now', return_value=friday_active_utc):
            self.assertEqual(flash_prod.get_current_price(), 50000)
            self.assertEqual(flash_prod.flash_sale_discount_percent, 50)
            # whatsapp message should reflect flash price
            decoded_link = urllib.parse.unquote(flash_prod.whatsapp_link)
            self.assertIn("50000 UGX", decoded_link)
            
        # 2. Wednesday 10:00 Kampala (07:00 UTC) -> Inactive
        wednesday_utc = datetime.datetime(2026, 6, 17, 7, 0, 0, tzinfo=datetime.timezone.utc)
        with patch('django.utils.timezone.now', return_value=wednesday_utc):
            self.assertEqual(flash_prod.get_current_price(), 100000)
            decoded_link = urllib.parse.unquote(flash_prod.whatsapp_link)
            self.assertIn("100000 UGX", decoded_link)

    def test_home_feed_flash_sale_context(self):
        from unittest.mock import patch
        import datetime
        
        # Create a flash sale product
        flash_prod = Product.objects.create(
            seller=self.seller_user,
            category=self.category,
            title='Flash Subwoofer',
            description='Exclusive deal',
            price=150000,
            flash_sale_price=75000,
            is_flash_sale=True,
            image=self.dummy_image
        )
        
        wednesday_utc = datetime.datetime(2026, 6, 17, 7, 0, 0, tzinfo=datetime.timezone.utc)
        with patch('django.utils.timezone.now', return_value=wednesday_utc):
            response = self.client.get(reverse('home_feed'))
            self.assertEqual(response.status_code, 200)
            self.assertIn('flash_status', response.context)
            self.assertIn('flash_products', response.context)
            
            # The flash product should be in flash_products
            self.assertIn(flash_prod, response.context['flash_products'])
            
            # The flash product should NOT be in featured_products or recent_products
            self.assertNotIn(flash_prod, response.context['featured_products'])
            self.assertNotIn(flash_prod, response.context['recent_products'])

    def test_admin_dashboard_permissions(self):
        # 1. Unauthenticated -> redirects to login
        response = self.client.get(reverse('admin_dashboard_home'))
        self.assertEqual(response.status_code, 302)

        # 2. Authenticated non-staff -> 403 Forbidden
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('admin_dashboard_home'))
        self.assertEqual(response.status_code, 403)
        self.client.logout()

        # 3. Authenticated staff -> 200 OK
        staff_user = User.objects.create_user(username='staffuser', password='testpassword', is_staff=True)
        self.client.login(username='staffuser', password='testpassword')
        response = self.client.get(reverse('admin_dashboard_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'System Overview')
        
    def test_admin_products_actions(self):
        staff_user = User.objects.create_user(username='staffuser2', password='testpassword', is_staff=True)
        self.client.login(username='staffuser2', password='testpassword')
        
        # Test toggle featured
        self.assertTrue(self.product.is_featured)
        response = self.client.post(reverse('admin_toggle_product', args=[self.product.id, 'featured']))
        self.assertRedirects(response, reverse('admin_products_list'))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_featured)
        
        # Test change status
        response = self.client.post(reverse('admin_update_product_status', args=[self.product.id]), data={'status': 'sold'})
        self.assertRedirects(response, reverse('admin_products_list'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'sold')
        
        # Test delete product
        response = self.client.post(reverse('admin_delete_product', args=[self.product.id]))
        self.assertRedirects(response, reverse('admin_products_list'))
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_admin_requests_actions(self):
        staff_user = User.objects.create_user(username='staffuser3', password='testpassword', is_staff=True)
        self.client.login(username='staffuser3', password='testpassword')
        
        item_req = ItemRequest.objects.create(
            requester=self.buyer_user,
            title='Needed a textbook',
            description='Django 6 guide',
            budget=20000,
            category=self.category
        )
        
        # Test update request status
        response = self.client.post(reverse('admin_update_request_status', args=[item_req.id]), data={'status': 'fulfilled'})
        self.assertRedirects(response, reverse('admin_requests_list'))
        item_req.refresh_from_db()
        self.assertEqual(item_req.status, 'fulfilled')
        
        # Test delete request
        response = self.client.post(reverse('admin_delete_request', args=[item_req.id]))
        self.assertRedirects(response, reverse('admin_requests_list'))
        self.assertFalse(ItemRequest.objects.filter(id=item_req.id).exists())

    def test_admin_users_actions(self):
        staff_user = User.objects.create_user(username='staffuser4', password='testpassword', is_staff=True)
        self.client.login(username='staffuser4', password='testpassword')
        
        # Test toggle staff status of another user
        self.assertFalse(self.buyer_user.is_staff)
        response = self.client.post(reverse('admin_toggle_user_staff', args=[self.buyer_user.id]))
        self.assertRedirects(response, reverse('admin_users_list'))
        self.buyer_user.refresh_from_db()
        self.assertTrue(self.buyer_user.is_staff)
        
        # Test prevent self-toggle
        response = self.client.post(reverse('admin_toggle_user_staff', args=[staff_user.id]))
        staff_user.refresh_from_db()
        self.assertTrue(staff_user.is_staff) # remains staff
        
        # Test delete another user
        response = self.client.post(reverse('admin_delete_user', args=[self.buyer_user.id]))
        self.assertRedirects(response, reverse('admin_users_list'))
        self.assertFalse(User.objects.filter(id=self.buyer_user.id).exists())
        
        # Test prevent self-deletion
        response = self.client.post(reverse('admin_delete_user', args=[staff_user.id]))
        self.assertTrue(User.objects.filter(id=staff_user.id).exists())

    def test_admin_categories_actions(self):
        staff_user = User.objects.create_user(username='staffuser5', password='testpassword', is_staff=True)
        self.client.login(username='staffuser5', password='testpassword')
        
        # Test create category
        response = self.client.post(reverse('admin_categories_list'), data={'name': 'Kitchenware'})
        self.assertRedirects(response, reverse('admin_categories_list'))
        self.assertTrue(Category.objects.filter(name='Kitchenware').exists())
        
        # Test delete category
        kitchen_cat = Category.objects.get(name='Kitchenware')
        response = self.client.post(reverse('admin_delete_category', args=[kitchen_cat.id]))
        self.assertRedirects(response, reverse('admin_categories_list'))
        self.assertFalse(Category.objects.filter(name='Kitchenware').exists())

    def test_login_redirect_rules(self):
        # 1. Normal client user login -> redirects to home feed
        response = self.client.post(reverse('login'), data={'username': 'testbuyer', 'password': 'testpassword'})
        self.assertRedirects(response, reverse('home_feed'))
        self.client.logout()

        # 2. Staff user login -> redirects to admin dashboard
        staff_user = User.objects.create_user(username='staffuser_login', password='testpassword', is_staff=True)
        response = self.client.post(reverse('login'), data={'username': 'staffuser_login', 'password': 'testpassword'})
        self.assertRedirects(response, reverse('admin_dashboard_home'))

        # 3. Already logged in staff goes to login -> redirects to admin dashboard
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('admin_dashboard_home'))
        self.client.logout()

        # 4. Already logged in client goes to login -> redirects to home feed
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home_feed'))

    def test_update_product_status(self):
        # 1. Unauthenticated -> redirects to login
        self.client.logout()
        response = self.client.post(reverse('update_product_status', args=[self.product.id]), data={'status': 'sold'})
        self.assertEqual(response.status_code, 302)
        
        # 2. Authenticated non-owner -> blocked and redirects with warning
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.post(reverse('update_product_status', args=[self.product.id]), data={'status': 'sold'})
        self.assertRedirects(response, reverse('product_detail', args=[self.product.id]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'available') # unchanged
        self.client.logout()
        
        # 3. Authenticated owner -> success and updates status
        self.client.login(username='testseller', password='testpassword')
        response = self.client.post(reverse('update_product_status', args=[self.product.id]), data={'status': 'sold'})
        self.assertRedirects(response, reverse('product_detail', args=[self.product.id]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'sold') # changed to sold!
        
        # 4. Verifying sold item is hidden from main feeds
        response_feed = self.client.get(reverse('home_feed'))
        self.assertNotContains(response_feed, self.product.title) # no longer in list!

    def test_update_product_status_with_next_redirect(self):
        # Authenticated owner updates status with next redirect parameter
        self.client.login(username='testseller', password='testpassword')
        
        # Reset status to available first
        self.product.status = 'available'
        self.product.save()
        
        target_next = '/chats/'
        response = self.client.post(
            reverse('update_product_status', args=[self.product.id]),
            data={'status': 'sold', 'next': target_next}
        )
        self.assertRedirects(response, target_next)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'sold')

    def test_home_feed_context_counters(self):
        # Count values should be in feed context
        response = self.client.get(reverse('home_feed'))
        self.assertIn('open_requests_count', response.context)
        self.assertIn('active_flash_count', response.context)
        self.assertIn('active_bundles_count', response.context)
        
        # Check correctness of counts (we created 1 product which is available, no bundles/requests yet)
        self.assertEqual(response.context['active_flash_count'], 0)
        self.assertEqual(response.context['active_bundles_count'], 0)
        
        # Add a request
        ItemRequest.objects.create(
            requester=self.buyer_user,
            title='Needed textbook',
            description='Test description',
            budget=15000,
            category=self.category,
            status='open'
        )
        # Add a flash sale product
        Product.objects.create(
            seller=self.seller_user,
            title='Flash sneaker',
            description='desc',
            price=20000,
            is_flash_sale=True,
            flash_sale_price=15000,
            status='available',
            category=self.category,
            image=self.dummy_image
        )
        # Add a bundle product
        Product.objects.create(
            seller=self.seller_user,
            title='Room bundle',
            description='desc',
            price=50000,
            is_bundle=True,
            status='available',
            category=self.category,
            image=self.dummy_image
        )
        
        response = self.client.get(reverse('home_feed'))
        self.assertEqual(response.context['open_requests_count'], 1)
        self.assertEqual(response.context['active_flash_count'], 1)
        self.assertEqual(response.context['active_bundles_count'], 1)

    def test_banner_images_management(self):
        # 1. Unauthenticated -> redirects to login
        response = self.client.get(reverse('admin_banners_list'))
        self.assertEqual(response.status_code, 302)
        
        # 2. Authenticated non-staff -> 403 Forbidden
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('admin_banners_list'))
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        
        # 3. Authenticated staff -> 200 OK
        staff_user = User.objects.create_user(username='staffbanner', password='testpassword', is_staff=True)
        self.client.login(username='staffbanner', password='testpassword')
        response = self.client.get(reverse('admin_banners_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hero Banner Settings')
        
        # 4. Upload banner
        self.assertEqual(BannerImage.objects.count(), 0)
        response = self.client.post(
            reverse('admin_banners_list'),
            data={
                'card_type': 'big_card',
                'image': self.dummy_image,
                'order': '1'
            }
        )
        self.assertRedirects(response, reverse('admin_banners_list'))
        self.assertEqual(BannerImage.objects.count(), 1)
        banner = BannerImage.objects.first()
        self.assertEqual(banner.card_type, 'big_card')
        self.assertEqual(banner.order, 1)
        
        # 5. Delete banner
        response = self.client.post(reverse('admin_delete_banner', args=[banner.id]))
        self.assertRedirects(response, reverse('admin_banners_list'))
        self.assertEqual(BannerImage.objects.count(), 0)

    def test_admin_create_product(self):
        # 1. Unauthenticated -> redirects to login
        response = self.client.get(reverse('admin_create_product'))
        self.assertEqual(response.status_code, 302)
        
        # 2. Authenticated non-staff -> 403 Forbidden
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('admin_create_product'))
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        
        # 3. Authenticated staff -> 200 OK
        staff_user = User.objects.create_user(username='staffprodadmin', password='testpassword', is_staff=True)
        self.client.login(username='staffprodadmin', password='testpassword')
        response = self.client.get(reverse('admin_create_product'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add New Product')
        
        # 4. Post valid data to create a product
        # Ensure we have a category and a seller user
        cat = Category.objects.create(name='Gadgets')
        seller = User.objects.create_user(username='sellerspecial', password='testpassword')
        
        # Clear out existing products to start fresh
        Product.objects.all().delete()
        
        response = self.client.post(
            reverse('admin_create_product'),
            data={
                'title': 'Admin Created Speaker',
                'description': 'Amazing condition',
                'price': '85000',
                'category': cat.id,
                'seller': seller.id,
                'status': 'available',
                'image': self.dummy_image,
                'is_featured': 'on',
                'is_flash_sale': 'on',
                'flash_sale_price': '65000'
            }
        )
        self.assertRedirects(response, reverse('admin_products_list'))
        self.assertEqual(Product.objects.count(), 1)
        
        prod = Product.objects.first()
        self.assertEqual(prod.title, 'Admin Created Speaker')
        self.assertEqual(prod.description, 'Amazing condition')
        self.assertEqual(prod.price, 85000)
        self.assertEqual(prod.category, cat)
        self.assertEqual(prod.seller, seller)
        self.assertEqual(prod.status, 'available')
        self.assertTrue(prod.is_featured)
        self.assertTrue(prod.is_flash_sale)
        self.assertEqual(prod.flash_sale_price, 65000)
        self.assertTrue(bool(prod.image))

    def test_api_notifications_unauthenticated(self):
        response = self.client.get(reverse('api_notifications'))
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_api_notifications_authenticated_empty(self):
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('api_notifications'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['notifications']), 0)
        self.assertEqual(data['global_unread_count'], 0)

    def test_api_notifications_authenticated_with_unread_and_read(self):
        # Create a thread
        thread = ChatThread.objects.create(product=self.product, buyer=self.buyer_user, seller=self.seller_user)
        
        # Message sent by seller to buyer (unread for buyer)
        msg1 = Message.objects.create(thread=thread, sender=self.seller_user, text="Hi! Are you interested?", is_read=False)
        
        # Buyer logs in
        self.client.login(username='testbuyer', password='testpassword')
        response = self.client.get(reverse('api_notifications'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should have 1 notification
        self.assertEqual(len(data['notifications']), 1)
        notif = data['notifications'][0]
        self.assertEqual(notif['thread_id'], thread.id)
        self.assertEqual(notif['unread_count'], 1)
        self.assertEqual(notif['last_message_text'], "Hi! Are you interested?")
        self.assertEqual(notif['other_user_name'], "SellerName")
        self.assertEqual(data['global_unread_count'], 1)
        
        # If buyer sends a reply (unread for seller, but NOT for buyer)
        msg2 = Message.objects.create(thread=thread, sender=self.buyer_user, text="Yes, is it negotiable?", is_read=False)
        response_after_reply = self.client.get(reverse('api_notifications'))
        data_after_reply = response_after_reply.json()
        # For buyer, their own message is excluded from unread count, so unread count should be 0 (since they read the seller's msg or the seller's msg is still there but buyer's own msg doesn't count)
        # Wait, the unread messages from seller is still 1. Let's check the count of messages not sent by buyer.
        # Seller's msg: sender = seller, is_read = False. Count = 1.
        # Buyer's msg: sender = buyer, is_read = False. Excluded from buyer's unread check.
        # So it should still be 1 unread message from the seller.
        self.assertEqual(data_after_reply['notifications'][0]['unread_count'], 1)
        self.assertEqual(data_after_reply['global_unread_count'], 1)
        
        # Log in as seller. Seller should have 1 unread message from buyer (msg2)
        self.client.logout()
        self.client.login(username='testseller', password='testpassword')
        response_seller = self.client.get(reverse('api_notifications'))
        data_seller = response_seller.json()
        self.assertEqual(data_seller['notifications'][0]['unread_count'], 1)
        self.assertEqual(data_seller['notifications'][0]['last_message_text'], "Yes, is it negotiable?")
        self.assertEqual(data_seller['notifications'][0]['other_user_name'], "BuyerName")
        self.assertEqual(data_seller['global_unread_count'], 1)












