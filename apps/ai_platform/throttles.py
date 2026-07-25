from rest_framework.throttling import UserRateThrottle


class AIRequestDailyThrottle(UserRateThrottle):
    """Per-user safety throttle for AI job creation.

    Subscription services still enforce monthly/character limits atomically. This
    throttle adds a coarse daily abuse guard backed by Django's configured cache.
    """

    scope = 'ai_requests'
