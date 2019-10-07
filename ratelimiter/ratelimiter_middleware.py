from decouple import config
from django.utils.deprecation import MiddlewareMixin
from constants import RATE_THRESHOLD


class RateLimiterMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (config('DEBUG', cast=bool)):
            print('ratelimiter middleware. threshold=%s' % RATE_THRESHOLD)
        return None
