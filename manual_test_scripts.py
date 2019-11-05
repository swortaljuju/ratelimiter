import sys
from constants import RATE_THRESHOLD
import time
import http.client
from decouple import config
from termcolor import colored
from http import HTTPStatus
import random
import itertools

# max # of requests per second.
MAX_RATE = 15

# A class to collect single test's result


class Tracker(object):
    def __init__(self, test_name):
        self._test_name = test_name
        super().__init__()

    def start(self, is_paused=False):
        self._success_count = 0
        self._sent_count = 0
        self._start_time = time.time()
        self._total_time = 0
        self._is_paused = is_paused

    def log_success_request(self):
        self._success_count += 1

    def log_sent_request(self):
        self._sent_count += 1

    def pause(self):
        assert(not self._is_paused)
        self._total_time += time.time() - self._start_time
        self._is_paused = True

    def resume(self):
        assert(self._is_paused)
        self._start_time = time.time()
        self._is_paused = False

    def end(self):
        if (not self._is_paused):
            self._total_time += time.time() - self._start_time
        self._success_rate = self._success_count / self._total_time
        self._sent_rate = self._sent_count / self._total_time

    def __str__(self):
        return ('test: %s; actual rate: %s; sending rate: %.4f;' %
                (colored(self._test_name, 'blue'), colored('%.4f' % self._success_rate, 'yellow'),
                 self._sent_rate))


class TrackerForVerify(Tracker):
    def __str__(self):
        return super().__str__() + (colored('Failed', 'red') if self._success_rate >
                                    RATE_THRESHOLD else colored('Passed', 'green'))


def send_request(min_duration, tracker, conn, rate_limiter_url):
    start_time = time.time()
    conn.request("GET", rate_limiter_url)
    r1 = conn.getresponse()
    tracker.log_sent_request()
    if (r1.status != HTTPStatus.TOO_MANY_REQUESTS):
        tracker.log_success_request()
    r1.read()
    duration = time.time() - start_time
    # Sleep if min duration hasn't been reached
    time.sleep(max(0, min_duration - duration))


def run_test(test_method, rate, test_trackers, number_request_per_test,
             number_iteration_per_test, conn, rate_limiter_url):
    for i in range(number_iteration_per_test):
        test_trackers.append(
            test_method(
                rate,
                number_request_per_test,
                conn,
                rate_limiter_url))


def test_uniformed_distribution(
        rate, number_request_per_test, conn, rate_limiter_url):
    min_request_duration = 1 / rate
    tracker = TrackerForVerify(
        ('Uniformed Distribution Test with Rate %s' % rate))
    tracker.start()
    for x in range(number_request_per_test):
        send_request(min_request_duration, tracker, conn, rate_limiter_url)
    tracker.end()
    return tracker


def send_request_at_rate(tracker, conn, rate_limiter_url, rate, duration):
    interval = 1 / rate
    current_time = time.time()
    end_time = current_time + duration
    while (end_time > current_time):
        send_request(interval, tracker, conn, rate_limiter_url)
        current_time = time.time()


def verify(rate_limiter):
    print('%s manual test. rate threshold=%s' % (rate_limiter, RATE_THRESHOLD))
    assert(RATE_THRESHOLD <= MAX_RATE, 'rate exceeds limit')
    conn = http.client.HTTPConnection(
        config('HTTP_HOST'), config('HTTP_HOST_PORT'))
    rate_limiter_url = "/ratelimiter_test/%s/index" % rate_limiter
    test_trackers = []
    number_request_per_test = 100
    number_iteration_per_test = 5

    run_test(test_uniformed_distribution, RATE_THRESHOLD / 2,
             test_trackers, number_request_per_test, number_iteration_per_test, conn, rate_limiter_url)
    run_test(test_uniformed_distribution, RATE_THRESHOLD, test_trackers,
             number_request_per_test, number_iteration_per_test, conn, rate_limiter_url)
    run_test(test_uniformed_distribution, RATE_THRESHOLD * 2, test_trackers,
             number_request_per_test, number_iteration_per_test, conn, rate_limiter_url)

    for tracker in test_trackers:
        print(tracker)

# Test how well each ratelimiter performs under special tests.


def compare():
    assert(RATE_THRESHOLD <= MAX_RATE, 'rate exceeds limit')
    conn = http.client.HTTPConnection(
        config('HTTP_HOST'), config('HTTP_HOST_PORT'))
    rate_limiters = [
        'token',
        'leaky_token',
        'fixed_window',
        'sliding_window_log',
        'sliding_window_prorate']
    flush_intervals = [
        random.uniform(
            0, 2) for _ in itertools.repeat(
            None, 100)]
    for rate_limiter in rate_limiters:
        rate_limiter_url = "/ratelimiter_test/%s/index" % rate_limiter
        background_tracker = Tracker(
            "%s flusing test background requests metric:" %
            rate_limiter)
        flush_tracker = Tracker(
            "%s flusing test flush requests metric:" %
            rate_limiter)
        background_tracker.start(is_paused=True)
        flush_tracker.start(is_paused=True)
        for interval in flush_intervals:
            background_tracker.resume()
            send_request_at_rate(
                background_tracker,
                conn,
                rate_limiter_url,
                RATE_THRESHOLD / 2,
                interval)
            background_tracker.pause()
            flush_tracker.resume()
            send_request_at_rate(
                flush_tracker,
                conn,
                rate_limiter_url,
                RATE_THRESHOLD * 2,
                1)
            flush_tracker.pause()
        background_tracker.end()
        flush_tracker.end()
        print(background_tracker)
        print(flush_tracker)
        # sleep 10 seconds after testing each ratelimter
        time.sleep(10)


if __name__ == '__main__':
    if (sys.argv[1] == "verify"):
        verify(sys.argv[2])
    elif (sys.argv[1] == "compare"):
        compare()
