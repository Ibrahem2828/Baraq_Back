import calendar

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.sources.models import StudentSource, StudentSourceCollection

from .constants import (
    CHARACTER_FEATURE_KEYS,
    CHARACTER_LIMIT_KEYS,
    CHARACTER_USAGE_FIELDS,
    DEFAULT_PLANS,
    FREE_PLAN_CODE,
)
from .exceptions import SubscriptionFeatureNotAllowed, SubscriptionLimitExceeded
from .models import SubscriptionEvent, SubscriptionPlan, SubscriptionUsage, UserSubscription


def ensure_default_plans():
    plans = {}
    for code, payload in DEFAULT_PLANS.items():
        plan, _ = SubscriptionPlan.objects.update_or_create(
            code=code,
            defaults={
                'name': payload['name'],
                'description': payload['description'],
                'price': payload['price'],
                'currency': payload['currency'],
                'billing_interval': payload['billing_interval'],
                'features': payload['features'],
                'limits': payload['limits'],
                'is_active': True,
                'is_public': payload['is_public'],
                'sort_order': payload['sort_order'],
            },
        )
        plans[code] = plan
    return plans


def get_free_plan():
    plan = SubscriptionPlan.objects.filter(code=FREE_PLAN_CODE).first()
    if plan is None:
        plan = ensure_default_plans()[FREE_PLAN_CODE]
    return plan


def current_month_period(today=None):
    today = today or timezone.localdate()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return today.replace(day=1), today.replace(day=last_day)


def get_or_create_user_subscription(user):
    subscription = UserSubscription.objects.select_related('plan').filter(user=user).first()
    if subscription:
        return subscription
    return UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            'plan': get_free_plan(),
            'status': UserSubscription.Status.ACTIVE,
            'provider': UserSubscription.Provider.LOCAL,
        },
    )[0]


def get_user_subscription(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return get_or_create_user_subscription(user)


def get_user_plan(user):
    subscription = get_user_subscription(user)
    return subscription.plan if subscription else get_free_plan()


def get_user_limits(user):
    return dict(get_user_plan(user).limits or {})


def get_user_features(user):
    return dict(get_user_plan(user).features or {})


def get_or_create_current_usage(user):
    subscription = get_user_subscription(user)
    period_start, period_end = current_month_period()
    usage, _ = SubscriptionUsage.objects.get_or_create(
        user=user,
        period_start=period_start,
        period_end=period_end,
        defaults={'subscription': subscription},
    )
    if subscription and usage.subscription_id != subscription.id:
        usage.subscription = subscription
        usage.save(update_fields=['subscription', 'updated_at'])
    return usage


def get_current_usage(user):
    return get_or_create_current_usage(user)


def recalculate_storage_used(user):
    usage = get_or_create_current_usage(user)
    total = StudentSource.objects.filter(user=user).aggregate(total=Sum('file_size'))['total'] or 0
    if usage.storage_used_bytes != total:
        usage.storage_used_bytes = total
        usage.save(update_fields=['storage_used_bytes', 'updated_at'])
    return usage


def limit_value(limits, key):
    value = limits.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bytes_to_mb(size_bytes):
    return size_bytes / (1024 * 1024)


def get_remaining_limits(user):
    limits = get_user_limits(user)
    usage = recalculate_storage_used(user)
    actual_collections = StudentSourceCollection.objects.filter(user=user).count()
    actual_sources = StudentSource.objects.filter(user=user).count()
    remaining = {}
    pairs = {
        'max_collections': actual_collections,
        'max_sources': actual_sources,
        'max_storage_mb': bytes_to_mb(usage.storage_used_bytes),
        'max_ai_requests_per_month': usage.ai_requests_used,
        'max_khota_requests_per_month': usage.khota_requests,
        'max_fahes_requests_per_month': usage.fahes_requests,
        'max_rasheed_requests_per_month': usage.rasheed_requests,
        'max_kholasa_requests_per_month': usage.kholasa_requests,
        'max_sada_requests_per_month': usage.sada_requests,
    }
    for key, used in pairs.items():
        limit = limit_value(limits, key)
        remaining[key] = None if limit is None else max(limit - int(used), 0)
    return remaining


def _raise_limit(message, code, limit=None, usage=None):
    raise SubscriptionLimitExceeded(message, code=code, limit=limit, usage=usage)


def can_create_collection(user):
    features = get_user_features(user)
    if features.get('can_create_unlimited_collections'):
        return True
    limit = limit_value(get_user_limits(user), 'max_collections')
    if limit is None:
        return True
    usage = StudentSourceCollection.objects.filter(user=user).count()
    if usage >= limit:
        _raise_limit(
            'لقد وصلت إلى الحد الأقصى للمجلدات في خطتك الحالية.',
            'collection_limit_reached',
            limit,
            usage,
        )
    return True


def can_upload_source(user, file_size_bytes):
    limits = get_user_limits(user)
    source_limit = limit_value(limits, 'max_sources')
    source_count = StudentSource.objects.filter(user=user).count()
    if source_limit is not None and source_count >= source_limit:
        _raise_limit(
            'لقد وصلت إلى الحد الأقصى للمصادر في خطتك الحالية.',
            'source_limit_reached',
            source_limit,
            source_count,
        )

    file_limit = limit_value(limits, 'max_file_size_mb')
    if file_limit is not None and bytes_to_mb(file_size_bytes) > file_limit:
        _raise_limit(
            'حجم الملف أكبر من الحد المسموح في خطتك.',
            'file_size_limit_exceeded',
            file_limit,
            round(bytes_to_mb(file_size_bytes), 2),
        )

    storage_limit = limit_value(limits, 'max_storage_mb')
    if storage_limit is not None:
        current_storage = StudentSource.objects.filter(user=user).aggregate(total=Sum('file_size'))['total'] or 0
        new_storage_mb = bytes_to_mb(current_storage + file_size_bytes)
        if new_storage_mb > storage_limit:
            _raise_limit(
                'لقد وصلت إلى حد التخزين المتاح في خطتك الحالية.',
                'storage_limit_exceeded',
                storage_limit,
                round(new_storage_mb, 2),
            )
    return True


def can_use_character(user, character):
    features = get_user_features(user)
    feature_key = CHARACTER_FEATURE_KEYS.get(character)
    if feature_key and not features.get(feature_key, False):
        raise SubscriptionFeatureNotAllowed(
            'هذه الشخصية غير متاحة في خطتك الحالية.',
            code='character_not_allowed',
            character=character,
        )

    limits = get_user_limits(user)
    usage = get_or_create_current_usage(user)
    limit_key = CHARACTER_LIMIT_KEYS.get(character)
    usage_field = CHARACTER_USAGE_FIELDS.get(character)
    if limit_key and usage_field:
        limit = limit_value(limits, limit_key)
        used = getattr(usage, usage_field)
        if limit is not None and used >= limit:
            _raise_limit(
                f'لقد استهلكت حد استخدام {character} لهذا الشهر.',
                'character_limit_reached',
                limit,
                used,
            )
    return True


def consume_collection_created(user):
    usage = get_or_create_current_usage(user)
    usage.collections_created += 1
    usage.save(update_fields=['collections_created', 'updated_at'])
    return usage


def consume_source_uploaded(user, file_size_bytes):
    usage = get_or_create_current_usage(user)
    usage.sources_uploaded += 1
    usage.storage_used_bytes = StudentSource.objects.filter(user=user).aggregate(total=Sum('file_size'))['total'] or 0
    usage.save(update_fields=['sources_uploaded', 'storage_used_bytes', 'updated_at'])
    return usage


def consume_character_request(user, character):
    usage = get_or_create_current_usage(user)
    field = CHARACTER_USAGE_FIELDS.get(character)
    if field:
        setattr(usage, field, getattr(usage, field) + 1)
        usage.ai_requests_used += 1
        usage.save(update_fields=[field, 'ai_requests_used', 'updated_at'])
    return usage


@transaction.atomic
def change_user_plan(user, plan, actor=None, status=None, current_period_end=None, metadata=None):
    subscription = get_or_create_user_subscription(user)
    old_plan = subscription.plan
    subscription.plan = plan
    if status:
        subscription.status = status
    else:
        subscription.status = UserSubscription.Status.ACTIVE
    subscription.current_period_start = timezone.now()
    subscription.current_period_end = current_period_end
    subscription.canceled_at = None
    subscription.metadata = {**(subscription.metadata or {}), **(metadata or {})}
    subscription.save()
    SubscriptionEvent.objects.create(
        user=user,
        subscription=subscription,
        event_type=SubscriptionEvent.EventType.PLAN_CHANGED,
        metadata={
            'old_plan': old_plan.code,
            'new_plan': plan.code,
            'actor_id': getattr(actor, 'id', None),
            **(metadata or {}),
        },
    )
    return subscription


@transaction.atomic
def cancel_user_subscription(user, actor=None):
    subscription = get_or_create_user_subscription(user)
    subscription.status = UserSubscription.Status.CANCELED
    subscription.canceled_at = timezone.now()
    subscription.auto_renew = False
    subscription.save(update_fields=['status', 'canceled_at', 'auto_renew', 'updated_at'])
    SubscriptionEvent.objects.create(
        user=user,
        subscription=subscription,
        event_type=SubscriptionEvent.EventType.CANCELED,
        metadata={'actor_id': getattr(actor, 'id', None)},
    )
    return subscription


def subscription_summary_for_user(user):
    subscription = get_or_create_user_subscription(user)
    usage = recalculate_storage_used(user)
    return {
        'plan': subscription.plan,
        'subscription': subscription,
        'usage': usage,
        'limits': get_user_limits(user),
        'features': get_user_features(user),
        'remaining': get_remaining_limits(user),
    }
