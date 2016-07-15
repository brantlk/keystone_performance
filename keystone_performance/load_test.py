
import argparse
import datetime
import itertools
import json
import time

import numpy
from twisted.internet import defer
from twisted.internet import reactor
from twisted.web import client
from twisted.web import http_headers
from twisted.web import iweb
from zope import interface


def _not_null(x):
    return x is not None


def format_timestamp(ts):
    return ts.strftime('%Y-%m-%d %H:%M:%S.%f')


def timestamp():
    return format_timestamp(datetime.datetime.utcnow())


class StringProducer(object):
    interface.implements(iweb.IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class TestTracker(object):
    def __init__(self, args):
        self._args = args

        self._agent = client.Agent(reactor)

        if args.type == 'quick':
            self._run_time = 15  # seconds
            self._concurrencies = [1, 2, 4, 8]
        else:  # Full run
            self._run_time = 60  # seconds
            self._concurrencies = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, ]

        self._concurrency_idx = 0

        self.stats = []

    def start(self):
        self._concurrency = self._concurrencies[self._concurrency_idx]
        print("Kicking off testing at concurrency {0}".format(
            self._concurrency))
        self._request_gatherer = (
            RequestGatherer(self._concurrency,
                            on_test_started=self._test_started))
        self._requests = []

        for i in range(self._concurrency):
            r = Request(self._agent, self._request_gatherer, self._args,
                        on_complete=self._notify_request_complete)
            r.start()
            self._requests.append(r)

        self._request_gatherer.start()

    def _test_started(self):
        reactor.callLater(self._run_time, self._done)
        self._start_time = datetime.datetime.utcnow()

    def _done(self):
        end_time = datetime.datetime.utcnow()
        conc_stats = self._request_gatherer.notify_complete()
        conc_stats['concurrency'] = self._concurrency
        conc_stats['start_time'] = format_timestamp(self._start_time)
        conc_stats['end_time'] = format_timestamp(end_time)
        self.stats.append(conc_stats)

        print(
            "concurrency: {concurrency} start_time: {start_time} "
            "end_time: {end_time} latency: {p90}".format(**conc_stats))

        # Notify all the Requests that the test is complete.
        self._requests_complete = 0
        for r in self._requests:
            r.notify_done()
        print(
            "Concurrency {0} test complete. "
            "Waiting on outstanding requests to complete...".format(
                self._concurrency))

    def _notify_request_complete(self):
        self._requests_complete += 1
        if self._requests_complete != self._concurrency:
            # Still waiting for all requests to complete.
            return

        # All requests complete! Go on to the next concurrency.
        self._concurrency_idx += 1
        if self._concurrency_idx >= len(self._concurrencies):
            # There is no next concurrency. We're done.
            reactor.stop()
            return

        self.start()


class RequestGatherer(object):
    def __init__(self, concurrency, on_test_started):
        self._concurrency = concurrency
        self._on_test_started = on_test_started

        self._state = 0  # waiting on initial results
        self._initial_requests_received = 0
        self._print_delayed_call = None
        self._startup_reset_delayed_call = None
        self._start_time = None
        self._reset()

    def _reset(self):
        self._response_times = []

    def start(self):
        self._print_delayed_call = reactor.callLater(3, self._print)

    def notify_initial_response(self):
        if self._state != 0:
            print("Got initial response after done??")
            return

        self._initial_requests_received += 1
        if self._initial_requests_received >= self._concurrency:
            print("%s All initial requests completed" % (timestamp(), ))
            self._state = 1
            self._reset()

            self._startup_reset_delayed_call = (
                reactor.callLater(5, self._notify_startup_reset))

    def _notify_startup_reset(self):
        print("%s Warmup complete (discarding results)." % (timestamp(), ))
        self._reset()
        self._startup_reset_delayed_call = None
        self._start_time = datetime.datetime.utcnow()
        self._on_test_started()

    def _add_response(self, time_or_none):
        if len(self._response_times) >= 100000:
            del self._response_times[0]
        self._response_times.append(time_or_none)

    def notify_response(self, new_time):
        self._add_response(new_time)

    def notify_failure_response(self):
        self._add_response(None)

    def _calc_stats(self):
        if not self._response_times:
            return None

        ret = {}

        measurements = list(
            itertools.ifilter(_not_null, self._response_times))
        ret['measure_count'] = len(measurements)
        ret['failure_count'] = len(list(
            itertools.ifilterfalse(_not_null, self._response_times)))
        ret['failure_rate'] = (
            float(ret['failure_count']) / len(self._response_times) * 100)

        if not measurements:
            return ret

        ret['min_val'] = min(measurements)
        ret['max_val'] = max(measurements)
        ret['p50'] = numpy.percentile(measurements, 50)
        ret['p90'] = numpy.percentile(measurements, 90)
        ret['std'] = numpy.std(measurements)
        return ret

    def notify_complete(self):
        self._state = 2  # Test is complete.

        self._print_delayed_call.cancel()
        if self._startup_reset_delayed_call:
            self._startup_reset_delayed_call.cancel()

        stats = self._calc_stats()
        return stats

    def _print(self):
        stats = self._calc_stats()
        now = timestamp()
        if stats is None:
            print("{0} No responses yet.".format(now))
        else:
            stats['now'] = now
            if 'p90' in stats:
                print('{now} P50/P90: {p50}/{p90} '
                      'min/max: {min_val}/{max_val}  std: {std} '
                      'falures: {failure_count} {failure_rate}% '
                      'measurements: {measure_count}'.format(**stats))
            else:
                print('{now} falures: {failure_count}'.format(**stats))

        self._print_delayed_call = reactor.callLater(3, self._print)


class Request(object):
    def __init__(self, agent, request_gatherer, args, on_complete=None):
        self._agent = agent
        self._request_gatherer = request_gatherer
        self._args = args
        self._on_complete = on_complete

        self._request_no = 0
        self._done = False

        if self._args.user_domain_id:
            user_domain_info = {'id': self._args.user_domain_id}
        else:
            user_domain_info = {'name': self._args.user_domain_name}
        if self._args.project_id:
            project_info = {'id': self._args.project_id}
        else:
            project_info = {'name': self._args.project_name}
        if self._args.project_domain_id:
            project_info['domain'] = {'id': self._args.project_domain_id}
        else:
            project_info['domain'] = {'name': self._args.project_domain_name}
        auth_req_body = {
            'auth': {
                'identity': {
                    'methods': ['password'],
                    'password': {
                        'user': {
                            'name': self._args.username,
                            'domain': user_domain_info,
                            'password': self._args.password
                        }
                    }
                },
                'scope': {
                    'project': project_info
                }
            }
        }
        self._auth_req_body = json.dumps(auth_req_body)

    def start(self):
        self._got_response = False
        self._failed = False
        self._start_time = time.time()

        d = self._agent.request(
            'POST',
            '%s/v3/auth/tokens' % self._args.url,
            http_headers.Headers({'Content-Type': ['application/json']}),
            StringProducer(self._auth_req_body))
        d.addCallback(self.response_cb)
        d.addBoth(self.shutdown_cb)

    def response_cb(self, response):
        self._got_response = True
        if response.code != 201:
            print("Request failed with code %s" % response.code)
            self._failed = True

    def shutdown_cb(self, ignored):
        if self._done:
            # Was waiting for the outstanding request to complete. Now it's
            # done.
            self._on_complete()
            return

        self._request_no += 1
        if self._request_no == 1:
            self._request_gatherer.notify_initial_response()

        if not self._got_response or self._failed:
            self._request_gatherer.notify_failure_response()
        else:
            end_time = time.time()
            self._request_gatherer.notify_response(end_time - self._start_time)
        self.start()

    def notify_done(self):
        # This test is done. Set a flag so don't send more requests.
        self._done = True


def print_summary(results):
    print("\nSummary:")
    for s in results:
        print(
            "concurrency: {concurrency} start_time: {start_time} "
            "end_time: {end_time} measurements: {measure_count} "
            "failures: {failure_count} failure_rate: {failure_rate} "
            "minimum: {min_val} maximum: {max_val} p50: {p50} p90: {p90} "
            "std_deviation: {std}".format(**s))


def write_out_file(out_file_name, results):
    with open(out_file_name, 'w') as f:
        for s in results:
            f.write(
                "{start_time},{end_time},{concurrency},{p90}\n".format(
                    **s))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://localhost:35357')
    parser.add_argument('--username', default='demo')
    parser.add_argument('--password')
    parser.add_argument('--user-domain-name', default='Default')
    parser.add_argument('--user-domain-id')
    parser.add_argument('--project-name', default='demo')
    parser.add_argument('--project-id')
    parser.add_argument('--project-domain-name', default='Default')
    parser.add_argument('--project-domain-id')
    parser.add_argument('--type', default='full', choices=['full', 'quick'])
    parser.add_argument('--out-file')
    args = parser.parse_args()

    test_tracker = TestTracker(args)
    test_tracker.start()

    reactor.run()

    print_summary(test_tracker.stats)
    if args.out_file:
        write_out_file(args.out_file, test_tracker.stats)


main()
