from __future__ import annotations

from .orchestration.service import execute_ai_request

try:
    from celery import shared_task
except ImportError:  # Local/test fallback before Celery is installed.
    def shared_task(*decorator_args, **decorator_kwargs):
        bind = bool(decorator_kwargs.get('bind'))

        def decorator(function):
            if bind:
                function.delay = lambda *args, **kwargs: function(None, *args, **kwargs)
            else:
                function.delay = function
            return function

        if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1:
            return decorator(decorator_args[0])
        return decorator


@shared_task(bind=True, autoretry_for=(), max_retries=0, name='ai_platform.process_request')
def process_ai_request(self, request_id: int):
    request = execute_ai_request(request_id)
    return {'request_id': request_id, 'status': request.status}
