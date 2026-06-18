from django.db.models import Q
from .models import Message, Category

def unread_messages_context(request):
    if request.user.is_authenticated:
        unread_count = Message.objects.filter(
            Q(thread__buyer=request.user) | Q(thread__seller=request.user),
            is_read=False
        ).exclude(sender=request.user).count()
        return {'global_unread_count': unread_count}
    return {'global_unread_count': 0}

def categories_context(request):
    return {
        'global_categories': Category.objects.all().order_by('name')
    }

