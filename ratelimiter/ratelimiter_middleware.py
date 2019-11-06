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

# Redis client is thread safe because each connection is obtained only
# when executing command.
redis_client = redis.Redis(
    host=config('REDIS_HOST'),
    port=config(
        'REDIS_PORT',
        cast=int))
        
# LUA script for token bucket ratelimiter.
TOKEN_BUCKET_LUA = '''
  local key = "token_bucket";
  local tokensPerBucket = %d;
  local timeBucket = 1;
  redis.call("SET", key, tokensPerBucket, "EX", timeBucket, "NX");
  local decrResult = redis.call("DECR", key);
  if (decrResult >= 0)
  then
    return 1;
  else
    local pttlResult = redis.call("PTTL", key);
    if (pttlResult == -1)
    then
       redis.call("SET", key, (tokensPerBucket - 1), "EX", timeBucket);
       return 1;
    else
       return 0;
    end
  end
''' % RATE_THRESHOLD

token_bucket_script = redis_client.register_script(TOKEN_BUCKET_LUA)

# LUA script for leaky bucket ratelimiter.
LEAKY_BUCKET_LUA = '''
  local key = "leaky_bucket";
  local tokensPerBucket = %d;
  local timeBucket = 1;
  redis.call("SET", key, 0, "EX", timeBucket, "NX");
  local incrResult = redis.call("INCR", key);
  if (incrResult <= tokensPerBucket)
  then
    if (incrResult == 1)
    then
       local pttlResult = redis.call("PTTL", key);
       if (pttlResult == -1)
       then
          redis.call("EXPIRE", key, timeBucket);
       end
    end
    return 1;
  else
    return 0;
  end
''' % RATE_THRESHOLD

leaky_bucket_script = redis_client.register_script(LEAKY_BUCKET_LUA)

# Use constant number of tokens per bucket/window to avoid flushing in
# short period.
TOKEN_PER_BUCKET = 10

TIME_SEC_PER_BUCKET = TOKEN_PER_BUCKET / RATE_THRESHOLD

# LUA script for sliding window log ratelimiter.
SLIDING_WINDOW_LOG_LUA = '''
  local key = "sliding_window_log";
  redis.call("ZREMRANGEBYSCORE", key, -1/0, ARGV[1] - %f);
  local windowSize = redis.call("ZCARD", key);
  if (windowSize == %d)
  then
    return 0;
  end
  local value = redis.call("INCR", key .. "_counter");
  redis.call("ZADD", key, ARGV[1], value);
  return 1;
''' % (TIME_SEC_PER_BUCKET, TOKEN_PER_BUCKET)

sliding_window_log_script = redis_client.register_script(
    SLIDING_WINDOW_LOG_LUA)

# LUA script for sliding window prorate ratelimiter.
SLIDING_WINDOW_PRORATE_LUA = '''
  local key = "sliding_window_prorate_"
  local currentKey = key .. KEYS[1];
  local previousKey = key .. (KEYS[1] - 1);
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
            return self.__dummy_limit()
        elif '/token/' in request.path:
            return self.__token_limit()
        elif '/leaky_token/' in request.path:
            return self.__leaky_token_limit()
        elif '/fixed_window/' in request.path:
            return self.__fixed_window_limit()
        elif '/sliding_window_log/' in request.path:
            return self.__sliding_window_log_limit()
        elif '/sliding_window_prorate/' in request.path:
            return self.__sliding_window_prorate_limit()
        return None

    def __dummy_limit(self):
        if (random.randrange(10) >= DUMMY_RATELIMITER_THRESHOLD):
            return self.__success()
        else:
            return self.__fail()

    def __token_limit(self):
        lua_result = token_bucket_script()
        return self.__parse_lua_result(lua_result)

    def __leaky_token_limit(self):
        lua_result = leaky_bucket_script()
        return self.__parse_lua_result(lua_result)

    def __fixed_window_limit(self):
        key = "%d_fixed_window" % self.__get_current_window()
        pipe = redis_client.pipeline()
        res = pipe.set(key, TOKEN_PER_BUCKET, ex=max(
            1, int(2 * TIME_SEC_PER_BUCKET)), nx=True).decr(key).execute()
        return self.__success() if res[1] >= 0 else self.__fail()

    def __sliding_window_log_limit(self):
        lua_result = sliding_window_log_script(args=[time.time()])
        return self.__parse_lua_result(lua_result)

    def __sliding_window_prorate_limit(self):
        current_time = time.time()
        current_window = self.__get_fixed_window(current_time)
        previous_window_portion = current_window + \
            1 - current_time / TIME_SEC_PER_BUCKET
        lua_result = sliding_window_prorate_script(
            keys=[current_window], args=[previous_window_portion])
        return self.__parse_lua_result(lua_result)

    def __fail(self):
        return HttpResponse(status=HTTPStatus.TOO_MANY_REQUESTS)

    def __success(self):
        return None

    def __parse_lua_result(self, lua_result):
        return (self.__success() if lua_result == 1 else self.__fail())

    def __get_current_window(self):
        return self.__get_fixed_window(time.time())

    def __get_fixed_window(self, time_sec):
        return int(math.floor(time_sec / TIME_SEC_PER_BUCKET))
