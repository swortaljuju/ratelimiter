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


class Tracker(object):
    ''' A class to track # failed requests, # successful requests and
    actual rate of a test.

    Attributes
    ----------
    _test_name : str
        name of a test
    _sent_count : int
        # of requests sent
    _start_time : int
        test starting time in seconds
    _total_time : int
        total test time up till current in seconds
    _is_paused : bool
        A flag indicates if the test is paused
    _success_rate: float
        # successful requests per seconds
    _sent_rate: float
        # sent requests per seconds
    '''

    def __init__(self, test_name):
        '''
        Parameters
        ----------
        test_name : str
            name of a test
        '''
        self._test_name = test_name
        super().__init__()

    def start(self, is_paused=False):
        '''Start tracking the test.

        Parameters
        ----------
        is_paused : bool
            True if start with paused state
        '''
        self._success_count = 0
        self._sent_count = 0
        self._start_time = time.time()
        self._total_time = 0
        self._is_paused = is_paused

    def log_success_request(self):
        '''Count successful request'''
        assert(not self._is_paused)
        self._success_count += 1

    def log_sent_request(self):
        '''Count sent request'''
        assert(not self._is_paused)
        self._sent_count += 1

    def pause(self):
        '''Pause tracker and add elapsed time to total time'''
        assert(not self._is_paused)
        self._total_time += time.time() - self._start_time
        self._is_paused = True

    def resume(self):
        '''Resume tracker and set start time to current time'''
        assert(self._is_paused)
        self._start_time = time.time()
        self._is_paused = False

    def end(self):
        '''End tracker and calculate rates'''
        if (not self._is_paused):
            self._total_time += time.time() - self._start_time
        self._success_rate = self._success_count / self._total_time
        self._sent_rate = self._sent_count / self._total_time

    def __str__(self):
        '''Print test result'''
        return ('test: %s; actual rate: %s; sending rate: %.4f;' %
                (colored(self._test_name, 'blue'), colored('%.4f' % self._success_rate, 'yellow'),
                 self._sent_rate))


class TrackerForVerify(Tracker):
    '''A tracker for verification test'''

    def __str__(self):
        '''Print test result'''
        return super().__str__() + (colored('Failed', 'red') if self._success_rate >
                                    RATE_THRESHOLD else colored('Passed', 'green'))


def send_request(min_duration, tracker, conn, rate_limiter_url):
    '''Send a http request to server and check the response.

    Parameters
    ----------
    min_duration : float
        The minimum duration in seconds this function should take. This is
        used to control request sending rate.
    tracker : Tracker
        The test tracker to track success and failed requests
    conn : http.client.HTTPConnection
        HTTPConnect to send request
    rate_limiter_url : str
        Target ratelimiter's url
    '''
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
    '''Run a single test for some times and collect the test tracker.

    Parameters
    ----------
    test_method : lambda
        The method to execute test case.
    rate : float
        Request sending rate
    test_trackers : List
        A list to collect test trackers
    number_request_per_test : int
        # of requests to be sent in each test
    number_iteration_per_test : int
        # of times each test should be run
    conn : http.client.HTTPConnection
        HTTPConnect to send request
    rate_limiter_url : str
        Target ratelimiter's url
    '''
    for i in range(number_iteration_per_test):
        test_trackers.append(
            test_method(
                rate,
                number_request_per_test,
                conn,
                rate_limiter_url))


def test_uniformed_distribution(
        rate, number_request_per_test, conn, rate_limiter_url):
    '''A test which sends request in a constant pace.

    Parameters
    ----------
    rate : float
        Request sending rate
    number_request_per_test : int
        # of requests to be sent in each test
    conn : http.client.HTTPConnection
        HTTPConnect to send request
    rate_limiter_url : str
        Target ratelimiter's url

    Returns
    -------
    Trakcer
        The test result tracker
    '''
    min_request_duration = 1 / rate
    tracker = TrackerForVerify(
        ('Uniformed Distribution Test with Rate %s' % rate))
    tracker.start()
    for x in range(number_request_per_test):
        send_request(min_request_duration, tracker, conn, rate_limiter_url)
    tracker.end()
    return tracker


def send_request_at_rate(tracker, conn, rate_limiter_url, rate, duration):
    '''Send requests at a particular rate.

    Parameters
    ----------
    tracker : Tracker
        The test tracker
    conn : http.client.HTTPConnection
        HTTPConnect to send request
    rate_limiter_url : str
        Target ratelimiter's url
    rate : float
        Request sending rate
    duration : float
        The total amount of time the method spend sending request
    '''
    interval = 1 / rate
    current_time = time.time()
    end_time = current_time + duration
    while (end_time > current_time):
        send_request(interval, tracker, conn, rate_limiter_url)
        current_time = time.time()


def verify(rate_limiter):
    '''Verify a particular ratelimiter

    Parameters
    ----------
    rate_limiter : str
        The name of the ratelimiter to be verified
    '''
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


def compare():
    '''Test how well each ratelimiter performs comparing each other.

    This test compares all ratelimiters on the rate limiting capability
    when requests are flushing. It sends 100 flushes of requests in total.
    Each flush lasts 1 second. In each flush, request is sent at 2 * RATE_THRESHOLD.
    2 consecutive flushes' gap is randomly generated between 0 to 2s. During the gap,
    it sends requests at RATE_THRESHOLD / 2 rate. To compare ratelimiters, it uses same
    sequence of flush gaps for all ratelimiter. Between each 2 ratelimiters' tests, it
    sleeps 10 seconds so that previous ratelimiter's redis cache could expire and won't
    affect next ratelimiter.
    '''
    assert(RATE_THRESHOLD <= MAX_RATE, 'rate exceeds limit')
    conn = http.client.HTTPConnection(
        config('HTTP_HOST'), config('HTTP_HOST_PORT'))
    rate_limiters = [
        'token',
        'leaky_token',
        'fixed_window',
        'sliding_window_log',
        'sliding_window_prorate']
    # Generate a random sequence of 100 flush gaps.
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
            # Send requests during flush gap at RATE_THRESHOLD / 2 rate.
            send_request_at_rate(
                background_tracker,
                conn,
                rate_limiter_url,
                RATE_THRESHOLD / 2,
                interval)
            background_tracker.pause()
            flush_tracker.resume()
            # Send a flush of requests.
            send_request_at_rate(
                flush_tracker,
                conn,
                rate_limiter_url,
                RATE_THRESHOLD * 2,
                1)
            flush_tracker.pause()
        background_tracker.end()
        flush_tracker.end()
        # Print test result.
        print(background_tracker)
        print(flush_tracker)
        # sleep 10 seconds after testing each ratelimter
        time.sleep(10)


if __name__ == '__main__':
    if (sys.argv[1] == "verify"):
        verify(sys.argv[2])
    elif (sys.argv[1] == "compare"):
        compare()
