from decouple import config
from django.utils.deprecation import MiddlewareMixin
from constants import RATE_THRESHOLD
from django.http import HttpResponse
from http import HTTPStatus
import random

DUMMY_RATELIMITER_THRESHOLD = 7


class RateLimiterMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (config('DEBUG', cast=bool)):
            print('ratelimiter middleware. threshold=%s' % RATE_THRESHOLD)
        # A ratelimiter to test manual_test_scripts.
        if '/dummy' in request.path:
            return self.dummyLimit()
        elif '/token' in request.path:
            return self.tokenLimit()
        elif '/leaky_token' in request.path:
            return self.leakyTokenLimit()
        elif '/fixed_window' in request.path:
            return self.fixedWindowLimit()
        elif '/sliding_window_log' in request.path:
            return self.slidingWindowLogLimit()
        elif '/sliding_window_prorate' in request.path:
            return self.slidingWindowProrateLimit()    
        return None

    def dummyLimit(self):
        if (random.randrange(10) >= DUMMY_RATELIMITER_THRESHOLD):
            return None
        else:
            return HttpResponse(status=HTTPStatus.TOO_MANY_REQUESTS)

    def tokenLimit(self):
        return None        

    def leakyTokenLimit(self):
        return None

    def fixedWindowLimit(self):
        return None
    
    def slidingWindowLogLimit(self):
        return None
    
    def slidingWindowProrateLimit(self):
        return None    
