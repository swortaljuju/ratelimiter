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
    def __init__(self, testName):
        self.__testName__ = testName
        super().__init__()

    def start(self, is_paused=False):
        self.__successCount__ = 0
        self.__sentCount__ = 0
        self.__startTime__ = time.time()
        self.__totalTime__ = 0
        self.__isPaused__ = is_paused

    def logSuccessRequest(self):
        self.__successCount__ += 1

    def logSentRequest(self):
        self.__sentCount__ += 1

    def pause(self):
        assert(not self.__isPaused__)
        self.__totalTime__ += time.time() - self.__startTime__
        self.__isPaused__ = True

    def resume(self):
        assert(self.__isPaused__)
        self.__startTime__ = time.time()
        self.__isPaused__ = False

    def end(self):
        if (not self.__isPaused__):
            self.__totalTime__ += time.time() - self.__startTime__
        self.__successRate__ = self.__successCount__ / self.__totalTime__
        self.__sentRate__ = self.__sentCount__ / self.__totalTime__

    def __str__(self):
        return ('test: %s; actual rate: %s; sending rate: %.4f;' %
                (colored(self.__testName__, 'blue'), colored('%.4f' % self.__successRate__, 'yellow'),
                 self.__sentRate__))


class TrackerForVerify(Tracker):
    def __str__(self):
        return super().__str__() + (colored('Failed', 'red') if self.__successRate__ >
                                    RATE_THRESHOLD else colored('Passed', 'green'))


def sendRequest(minDuration, tracker, conn, rateLimiterUrl):
    '''
        minDuration: float
            Minimum duration to execute this function
    '''
    startTime = time.time()
    conn.request("GET", rateLimiterUrl)
    r1 = conn.getresponse()
    tracker.logSentRequest()
    if (r1.status != HTTPStatus.TOO_MANY_REQUESTS):
        tracker.logSuccessRequest()
    r1.read()
    duration = time.time() - startTime
    # Sleep if min duration hasn't been reached
    time.sleep(max(0, minDuration - duration))


def runTest(testMethod, rate, testTrackers, number_request_per_test,
            number_iteration_per_test, conn, rateLimiterUrl):
    for i in range(number_iteration_per_test):
        testTrackers.append(
            testMethod(
                rate,
                number_request_per_test,
                conn,
                rateLimiterUrl))


def testUniformedDistribution(
        rate, number_request_per_test, conn, rateLimiterUrl):
    '''
        A test whose request's time gap is a constant
        rate: float
            # requests per seconds
    '''
    minRequestDuration = 1 / rate
    tracker = TrackerForVerify(
        ('Uniformed Distribution Test with Rate %s' % rate))
    tracker.start()
    for x in range(number_request_per_test):
        sendRequest(minRequestDuration, tracker, conn, rateLimiterUrl)
    tracker.end()
    return tracker


def sendRequestAtRate(tracker, conn, rateLimiterUrl, rate, duration):
    interval = 1 / rate
    current_time = time.time()
    end_time = current_time + duration
    while (end_time > current_time):
        sendRequest(interval, tracker, conn, rateLimiterUrl)
        current_time = time.time()


def verify(rateLimiter):
    print('%s manual test. rate threshold=%s' % (rateLimiter, RATE_THRESHOLD))
    assert(RATE_THRESHOLD <= MAX_RATE, 'rate exceeds limit')
    conn = http.client.HTTPConnection(
        config('HTTP_HOST'), config('HTTP_HOST_PORT'))
    rateLimiterUrl = "/ratelimiter_test/%s/index" % rateLimiter
    testTrackers = []
    number_request_per_test = 100
    number_iteration_per_test = 5

    runTest(testUniformedDistribution, RATE_THRESHOLD / 2,
            testTrackers, number_request_per_test, number_iteration_per_test, conn, rateLimiterUrl)
    runTest(testUniformedDistribution, RATE_THRESHOLD, testTrackers,
            number_request_per_test, number_iteration_per_test, conn, rateLimiterUrl)
    runTest(testUniformedDistribution, RATE_THRESHOLD * 2, testTrackers,
            number_request_per_test, number_iteration_per_test, conn, rateLimiterUrl)

    for tracker in testTrackers:
        print(tracker)

# Test how well each ratelimiter performs under special tests.


def compare():
    assert(RATE_THRESHOLD <= MAX_RATE, 'rate exceeds limit')
    conn = http.client.HTTPConnection(
        config('HTTP_HOST'), config('HTTP_HOST_PORT'))
    ratelimiters = [
        'token',
        'leaky_token',
        'fixed_window',
        'sliding_window_log',
        'sliding_window_prorate']
    flush_intervals = [
        random.uniform(
            0, 2) for _ in itertools.repeat(
            None, 100)]
    for rateLimiter in ratelimiters:
        rateLimiterUrl = "/ratelimiter_test/%s/index" % rateLimiter
        background_tracker = Tracker(
            "%s flusing test background requests metric:" %
            rateLimiter)
        flush_tracker = Tracker(
            "%s flusing test flush requests metric:" %
            rateLimiter)
        background_tracker.start(is_paused=True)
        flush_tracker.start(is_paused=True)
        for interval in flush_intervals:
            background_tracker.resume()
            sendRequestAtRate(
                background_tracker,
                conn,
                rateLimiterUrl,
                RATE_THRESHOLD / 2,
                interval)
            background_tracker.pause()
            flush_tracker.resume()
            sendRequestAtRate(
                flush_tracker,
                conn,
                rateLimiterUrl,
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
