from decouple import config
from django.utils.deprecation import MiddlewareMixin
from constants import RATE_THRESHOLD
from django.http import HttpResponse
from http import HTTPStatus
import random
import redis
import time
import math

DUMMY_RATELIMITER_THRESHOLD = 7

# Use constant number of tokens per bucket/window to avoid flushing in
# short period.
TOKEN_PER_BUCKET = 10

# Redis client is thread safe because each connection is obtained only
# when executing command.
redis_client = redis.Redis(
    host=config('REDIS_HOST'),
    port=config(
        'REDIS_PORT',
        cast=int))
TOKEN_BUCKET_LUA = '''
  local tokensPerBucket = %d; --[ Assign a small constant number of tokens always--]
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
''' % TOKEN_PER_BUCKET

token_bucket_script = redis_client.register_script(TOKEN_BUCKET_LUA)

LEAKY_BUCKET_LUA = '''
  local tokensPerBucket = %d; --[ Assign a small constant number of tokens always--]
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
''' % TOKEN_PER_BUCKET

leaky_bucket_script = redis_client.register_script(LEAKY_BUCKET_LUA)

TIME_SEC_PER_BUCKET = TOKEN_PER_BUCKET / RATE_THRESHOLD

SLIDING_WINDOW_LOG_LUA = '''
  redis.call("ZREMRANGEBYSCORE", KEYS[1], -1/0, ARGV[1] - %f);
  local windowSize = redis.call("ZCARD", KEYS[1]);
  if (windowSize == %d)
  then
    return 0;
  end
  local value = redis.call("INCR", KEYS[1] .. "_counter");
  redis.call("ZADD", KEYS[1], ARGV[1], value);
  return 1;
''' % (TIME_SEC_PER_BUCKET, TOKEN_PER_BUCKET)

sliding_window_log_script = redis_client.register_script(
    SLIDING_WINDOW_LOG_LUA)

SLIDING_WINDOW_PRORATE_LUA = '''
  local currentKey = KEYS[1] .. KEYS[2];
  local previousKey = KEYS[1] .. (KEYS[2] - 1);
  redis.call("SET", currentKey, 0, "NX", "EX", math.max(1 , %d));
  local currentCnt = redis.call("GET", currentKey);
  local previousCnt = redis.call("GET", previousKey);
  if (previousCnt == false)
  then
    previousCnt = 0;
  end

  if (currentCnt + previousCnt * ARGV[1] < %d)
  then
    redis.call("INCR", currentKey);
    return 1;
  else
    return 0;
  end
    ''' % (int(4 * TIME_SEC_PER_BUCKET), TOKEN_PER_BUCKET)

sliding_window_prorate_script = redis_client.register_script(
    SLIDING_WINDOW_PRORATE_LUA)


class RateLimiterMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (config('DEBUG', cast=bool)):
            print('ratelimiter middleware. threshold=%s' % RATE_THRESHOLD)
        # A ratelimiter to test manual_test_scripts.
        if '/dummy/' in request.path:
            return self.__dummyLimit()
        elif '/token/' in request.path:
            return self.__tokenLimit()
        elif '/leaky_token/' in request.path:
            return self.__leakyTokenLimit()
        elif '/fixed_window/' in request.path:
            return self.__fixedWindowLimit()
        elif '/sliding_window_log/' in request.path:
            return self.__slidingWindowLogLimit()
        elif '/sliding_window_prorate/' in request.path:
            return self.__slidingWindowProrateLimit()
        return None

    def __dummyLimit(self):
        if (random.randrange(10) >= DUMMY_RATELIMITER_THRESHOLD):
            return self.__success()
        else:
            return self.__fail()

    def __tokenLimit(self):
        lua_result = token_bucket_script(
            keys=["token_bucket"], args=[RATE_THRESHOLD])
        return self.__parseLuaResult(lua_result)

    def __leakyTokenLimit(self):
        lua_result = leaky_bucket_script(
            keys=["leaky_bucket"], args=[RATE_THRESHOLD])
        return self.__parseLuaResult(lua_result)

    def __fixedWindowLimit(self):
        key = "%d_fixed_window" % self.__getCurrentWindow()
        pipe = redis_client.pipeline()
        res = pipe.set(key, TOKEN_PER_BUCKET, ex=max(
            1, int(2 * TIME_SEC_PER_BUCKET)), nx=True).decr(key).execute()
        return self.__success() if res[1] >= 0 else self.__fail()

    def __slidingWindowLogLimit(self):
        lua_result = sliding_window_log_script(
            keys=["sliding_window_log"], args=[time.time()])
        return self.__parseLuaResult(lua_result)

    def __slidingWindowProrateLimit(self):
        currentTime = time.time()
        currentWindow = self.__getFixedWindow(currentTime)
        previousWindowPortion = currentWindow + 1 - currentTime / TIME_SEC_PER_BUCKET
        lua_result = sliding_window_prorate_script(
            keys=["sliding_window_prorate_", currentWindow], args=[previousWindowPortion])
        return self.__parseLuaResult(lua_result)

    def __fail(self):
        return HttpResponse(status=HTTPStatus.TOO_MANY_REQUESTS)

    def __success(self):
        return None

    def __parseLuaResult(self, lua_result):
        return (self.__success() if lua_result == 1 else self.__fail())

    def __getCurrentWindow(self):
        return self.__getFixedWindow(time.time())

    def __getFixedWindow(self, time_sec):
        return int(math.floor(time_sec / TIME_SEC_PER_BUCKET))
