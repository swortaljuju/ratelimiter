import sys
from constants import RATE_THRESHOLD


def testAtRate(rate):
    print('testAtRate rate=%s' % rate)


def main():
    print('manual test. rate threshold=%s' % RATE_THRESHOLD)
    testAtRate(RATE_THRESHOLD / 2)
    testAtRate(RATE_THRESHOLD)
    testAtRate(RATE_THRESHOLD * 2)


if __name__ == '__main__':
    main()
