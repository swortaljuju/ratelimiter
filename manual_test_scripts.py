import sys
from constants import RATE_THRESHOLD
import time
import http.client
from decouple import config
from termcolor import colored
from http import HTTPStatus

# max # of requests per second.
MAX_RATE = 15

# Global connection object.
conn = None

# Rate limiter's url
rateLimiterUrl = None

# Number fo requests to be sent per test
NUMBER_REQUEST_PER_TEST = 100

# Number to times each test should be ran
NUMBER_ITERATION_PER_TEST = 5

# A class to collect single test's result
class Tracker(object):
    def __init__(self, testName):
        self.__testName__ = testName
        super().__init__()

    def start(self):
        self.__successCount__ = 0
        self.__sentCount__ = 0
        self.__startTime__ = time.time()

    def logSuccessRequest(self):
        self.__successCount__ += 1

    def logSentRequest(self):
        self.__sentCount__ += 1

    def end(self):
        endTime = time.time()
        totalTime = endTime - self.__startTime__
        self.__successRate__ = self.__successCount__ / totalTime
        self.__sentRate__ = self.__sentCount__ / totalTime

    def __str__(self):
        return ('test: %s; actual rate: %s; %s; sending rate: %.4f;' %
                (colored(self.__testName__, 'blue'), colored('%.4f' % self.__successRate__, 'yellow'),
                 (colored('Failed', 'red') if self.__successRate__ >
                  RATE_THRESHOLD else colored('Passed', 'green')),
                 self.__sentRate__))


def sendRequest(minDuration, tracker):
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


def runTest(testMethod, rate, testTrackers):
    for i in range(NUMBER_ITERATION_PER_TEST):
        testTrackers.append(testMethod(rate))


def testUniformedDistribution(rate):
    '''
        A test whose request's time gap is a constant
        rate: float
            # requests per seconds
    '''
    minRequestDuration = 1 / rate
    tracker = Tracker(('Uniformed Distribution Test with Rate %s' % rate))
    tracker.start()
    for x in range(NUMBER_REQUEST_PER_TEST):
        sendRequest(minRequestDuration, tracker)
    tracker.end()
    return tracker


def main(rateLimiter):
    global rateLimiterUrl, conn
    print('%s manual test. rate threshold=%s' % (rateLimiter, RATE_THRESHOLD))
    assert(RATE_THRESHOLD <= MAX_RATE, 'rate exceeds limit')
    conn = http.client.HTTPConnection(
        config('HTTP_HOST'), config('HTTP_HOST_PORT'))
    rateLimiterUrl = "/ratelimiter_test/%s" % rateLimiter
    testTrackers = []

    runTest(testUniformedDistribution, RATE_THRESHOLD / 2, testTrackers)
    runTest(testUniformedDistribution, RATE_THRESHOLD, testTrackers)
    runTest(testUniformedDistribution, RATE_THRESHOLD * 2, testTrackers)
    
    for tracker in testTrackers:
        print(tracker)


if __name__ == '__main__':
    main(sys.argv[1])
