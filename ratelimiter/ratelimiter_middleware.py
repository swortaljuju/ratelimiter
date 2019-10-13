from decouple import config
from django.utils.deprecation import MiddlewareMixin
from constants import RATE_THRESHOLD
from django.http import HttpResponse
import random

DUMMY_RATELIMITER_THRESHOLD = 7


class RateLimiterMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (config('DEBUG', cast=bool)):
            print('ratelimiter middleware. threshold=%s' % RATE_THRESHOLD)
        # A ratelimiter to test manual_test_scripts.
        if '/dummy' in request.path:
            if (random.randrange(10) >= DUMMY_RATELIMITER_THRESHOLD):
                print('dummy ratelimiter request succeed')
                return None
            else:
                print('dummy ratelimiter request failed')
                return HttpResponse(status=429)
        return None
