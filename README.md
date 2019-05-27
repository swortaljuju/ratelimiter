# ratelimiter
Rate limiter knowledges
5 ways:
1. Every n seconds add m tokens
2. Queue all requests. When queue is full, abandon new request. Process the request at a constant rate
3. Sliding window. For each static time window, issue m tokens
4. Sliding window log. Log all requests’ timestamps. When a new request comes in, sum previous requests based on timestamp and see if the new request should be abandoned
5. Sliding window prorated. Only store count of requests in previous sliding window. Assume requests come in at a uniform speed. When a new request comes in, based on previous window’s count and current window’s count, calculate the estimated count from new request’s timestamp to a window’s time before the new window’s timestamp.

Implementation:
Redis db has good implementation

Contains:
Python impl w/o redis