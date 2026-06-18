from django.contrib import admin
from .models import Profile, Category, Product, ChatThread, Message, BundleItem, ItemRequest

class BundleItemInline(admin.TabularInline):
    model = BundleItem
    extra = 3

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'hostel_or_area')
    list_filter = ('hostel_or_area',)
    search_fields = ('user__username', 'user__first_name', 'phone_number')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'seller', 'is_featured', 'is_bundle', 'status')
    list_editable = ('is_featured', 'status')
    list_filter = ('is_featured', 'is_bundle', 'status', 'category', 'seller__profile__hostel_or_area')
    search_fields = ('title', 'description', 'seller__username', 'seller__first_name')
    inlines = [BundleItemInline]
    date_hierarchy = 'created_at'

@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'buyer', 'seller')
    list_filter = ('product__category',)
    search_fields = ('product__title', 'buyer__username', 'seller__username')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'sender', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('text', 'sender__username')

@admin.register(ItemRequest)
class ItemRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'budget', 'requester', 'status', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'description', 'requester__username', 'requester__first_name')
