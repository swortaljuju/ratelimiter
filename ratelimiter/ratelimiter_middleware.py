from decouple import config
from django.utils.deprecation import MiddlewareMixin
from constants import RATE_THRESHOLD
from django.http import HttpResponse
from http import HTTPStatus
import random
import redis

DUMMY_RATELIMITER_THRESHOLD = 7

# Redis client is thread safe because each connection is obtained only
# when executing command.
redis_client = redis.Redis(
    host=config('REDIS_HOST'),
    port=config(
        'REDIS_PORT',
        cast=int))
TOKEN_BUCKET_LUA = '''
  local tokensPerBucket = 10; --[ Assign a small constant number of tokens always--]
  local timeBucket = 10 / ARGV[1];
  redis.call("SET", KEYS[1], tokensPerBucket, "EX", timeBucket, "NX");
  local decrResult = redis.call("DECR", KEYS[1]);
  if (decrResult >= 0)
  then
    return 1;
  else
    local pttlResult = redis.call("PTTL", KEYS[1]);
    if (pttlResult == -1)
    then
       redis.call("SET", KEYS[1], (tokensPerBucket - 1), "EX", timeBucket);
       return 1;
    else
       return 0;
    end
  end
'''

token_bucket_script = redis_client.register_script(TOKEN_BUCKET_LUA)

LEAKY_BUCKET_LUA = '''
  local tokensPerBucket = 10; --[ Assign a small constant number of tokens always--]
  local timeBucket = 10 / ARGV[1];
  redis.call("SET", KEYS[1], 0, "EX", timeBucket, "NX");
  local incrResult = redis.call("INCR", KEYS[1]);
  if (incrResult <= tokensPerBucket)
  then
    if (incrResult == 1)
    then
       local pttlResult = redis.call("PTTL", KEYS[1]);
       if (pttlResult == -1)
       then
          redis.call("EXPIRE", KEYS[1], timeBucket);
       end
    end
    return 1;
  else
    return 0;
  end
'''

leaky_bucket_script = redis_client.register_script(LEAKY_BUCKET_LUA)


class RateLimiterMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (config('DEBUG', cast=bool)):
            print('ratelimiter middleware. threshold=%s' % RATE_THRESHOLD)
        # A ratelimiter to test manual_test_scripts.
        if '/dummy/' in request.path:
            return self.dummyLimit()
        elif '/token/' in request.path:
            return self.tokenLimit()
        elif '/leaky_token/' in request.path:
            return self.leakyTokenLimit()
        elif '/fixed_window/' in request.path:
            return self.fixedWindowLimit()
        elif '/sliding_window_log/' in request.path:
            return self.slidingWindowLogLimit()
        elif '/sliding_window_prorate/' in request.path:
            return self.slidingWindowProrateLimit()
        return None

    def dummyLimit(self):
        if (random.randrange(10) >= DUMMY_RATELIMITER_THRESHOLD):
            return self.success()
        else:
            return self.fail()

    def tokenLimit(self):
        lua_result = token_bucket_script(
            keys=["token_bucket"], args=[RATE_THRESHOLD])
        return self.parseLuaResult(lua_result)

    def leakyTokenLimit(self):
        lua_result = leaky_bucket_script(
            keys=["leaky_bucket"], args=[RATE_THRESHOLD])
        return self.parseLuaResult(lua_result)

    def fixedWindowLimit(self):
        return None

    def slidingWindowLogLimit(self):
        return None

    def slidingWindowProrateLimit(self):
        return None

    def fail(self):
        return HttpResponse(status=HTTPStatus.TOO_MANY_REQUESTS)

    def success(self):
        return None

    def parseLuaResult(self, lua_result):
        return (self.success() if lua_result == 1 else self.fail())
