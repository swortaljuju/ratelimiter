from decouple import config
from django.utils.deprecation import MiddlewareMixin


class RateLimiterMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (config('DEBUG', cast=bool)):
            print('ratelimiter middleware')
        return None
