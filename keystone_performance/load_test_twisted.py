
import argparse
import json
import time

import numpy
from twisted.internet import defer
from twisted.internet import reactor
from twisted.web import client
from twisted.web import http_headers
from twisted.web import iweb
from zope import interface


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


class RequestGatherer(object):
    def __init__(self):
        self._response_times = []
        self._failures = 0

    def start(self):
        reactor.callLater(3, self._print)

    def notify_response(self, new_time):
        if len(self._response_times) >= 10000:
            del self._response_times[0]
        self._response_times.append(new_time)

    def notify_failure_response(self):
        self._failures += 1

    def _print(self):
        # Calculate P50/P90
        min_val = min(self._response_times)
        max_val = max(self._response_times)
        p50 = numpy.percentile(self._response_times, 50)
        p90 = numpy.percentile(self._response_times, 90)
        print('P50/P90: %s/%s min/max: %s/%s falures: %s' %
              (p50, p90, min_val, max_val, self._failures))
        reactor.callLater(2, self._print)


class Request(object):
    def __init__(self, agent, request_gatherer, args):
        self._agent = agent
        self._request_gatherer = request_gatherer
        self._args = args

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
            self._failed = True

    def shutdown_cb(self, ignored):
        if not self._got_response or self._failed:
            self._request_gatherer.notify_failure_response()
        else:
            end_time = time.time()
            self._request_gatherer.notify_response(end_time - self._start_time)
        self.start()


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
    parser.add_argument('--concurrency', type=int, default=1)
    args = parser.parse_args()

    agent = client.Agent(reactor)
    request_gatherer = RequestGatherer()

    for i in range(args.concurrency):
        r = Request(agent, request_gatherer, args)
        r.start()

    request_gatherer.start()

    reactor.run()


main()
