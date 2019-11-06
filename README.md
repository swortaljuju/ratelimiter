[general introduction]

# Rate Limiter Implementation
[general design, why redis, why not django redis, lua vs transaction, ]

## 1. Token Bucket Rate Limiter
Every n seconds add m tokens

## 2. Leaky Bucket Rate Limiter
Every n seconds remove n requests

## 3. Fixed Window Rate Limiter
Fixed window. For each static time window, issue m tokens

## 4. Sliding Window Log Rate Limiter
Sliding window log. Log all requests’ timestamps. When a new request comes in, sum previous requests based on timestamp and see if the new request should be abandoned

## 5. Sliding Window Prorated Rate Limiter
Sliding window prorated. Only store count of requests in previous sliding window. Assume requests come in at a uniform speed. When a new request comes in, based on previous window’s count and current window’s count, calculate the estimated count from new request’s timestamp to a window’s time before the new window’s timestamp.

## Comparison
[difference, will show metric in latter section]

# Test
[general]

## Verification Test
[...]

## Comparison Test
[...]

# Project Structure
[django, secrets, pip require, middleware]