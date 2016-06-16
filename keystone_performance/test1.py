
import argparse
import datetime
import functools
import multiprocessing
import sys
import time

import numpy
import requests


class ConcurrentTest(object):
    def __init__(
            self, base_url, username, password, user_domain_name, project_name,
            project_domain_name, concurrency):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.user_domain_name = user_domain_name
        self.project_name = project_name
        self.project_domain_name = project_domain_name
        self.concurrency = concurrency

    def _get_concurrent_launch_fn(self):
        return None

    def run_test(self):
        # Validate the token
        total_start_time = time.time()
        pool = multiprocessing.Pool(self.concurrency)
        f = functools.partial(self._get_concurrent_launch_fn(), self)
        res = pool.map(f, xrange(self.concurrency))
        total_end_time = time.time()
        times = []
        for r in res:
            times.extend(r)

        # Calculate P50/P90
        min_val = min(times)
        max_val = max(times)
        p50 = numpy.percentile(times, 50)
        p90 = numpy.percentile(times, 90)
        total_time = sum(times)
        total_wall_time = total_end_time - total_start_time
        print('P50/P90: %s/%s min/max: %s/%s total: %s wall: %s' % (
            p50, p90, min_val, max_val, total_time, total_wall_time))


def validate_token(validate_token_test, i):
    return validate_token_test._validate_token()


class ValidateTokenTest(ConcurrentTest):
    def __init__(
            self, base_url, username, password, user_domain_name, project_name,
            project_domain_name, validation_count, concurrency):
        super(ValidateTokenTest, self).__init__(
            base_url, username, password, user_domain_name, project_name,
            project_domain_name, concurrency)
        self.validation_count = validation_count

    def _get_concurrent_launch_fn(self):
        return validate_token

    def run_test(self):
        # Get a token as the requested user.
        req_body = {
            'auth': {
                'identity': {
                    'methods': ['password'],
                    'password': {
                        'user': {
                            'name': self.username,
                            'domain': {'name': self.user_domain_name},
                            'password': self.password
                        }
                    }
                },
                'scope': {
                    'project': {
                        'name': self.project_name,
                        'domain': {'name': self.project_domain_name}
                    }
                }
            }
        }

        response = requests.post(
            '%s/v3/auth/tokens' % self.base_url,
            headers={'Content-Type': 'application/json'},
            json=req_body)
        response.raise_for_status()
        self.user_token = response.headers['X-Subject-Token']

        super(ValidateTokenTest, self).run_test()

    def _validate_token(self):
        validation_times = []
        for i in xrange(self.validation_count):
            start_time = time.time()
            response = requests.get(
                '%s/v3/auth/tokens' % self.base_url,
                headers={
                    'Content-Type': 'application/json',
                    'X-Auth-Token': self.user_token,
                    'X-Subject-Token': self.user_token
                })
            response.raise_for_status()
            end_time = time.time()
            total_time = end_time - start_time
            validation_times.append(total_time)
        return validation_times


def issue_token(issue_token_test, i):
    return issue_token_test._issue_token()


class IssueTokenTest(ConcurrentTest):
    def __init__(
            self, base_url, username, password, user_domain_name, project_name,
            project_domain_name, issue_count, concurrency):
        super(IssueTokenTest, self).__init__(
            base_url, username, password, user_domain_name, project_name,
            project_domain_name, concurrency
        )
        self.issue_count = issue_count

    def _get_concurrent_launch_fn(self):
        return issue_token

    def _issue_token(self):
        issue_times = []
        for i in xrange(self.issue_count):
            start_time = time.time()

            # Get a token as the requested user.
            req_body = {
                'auth': {
                    'identity': {
                        'methods': ['password'],
                        'password': {
                            'user': {
                                'name': self.username,
                                'domain': {'name': self.user_domain_name},
                                'password': self.password
                            }
                        }
                    },
                    'scope': {
                        'project': {
                            'name': self.project_name,
                            'domain': {'name': self.project_domain_name}
                        }
                    }
                }
            }

            response = requests.post(
                '%s/v3/auth/tokens' % self.base_url,
                headers={'Content-Type': 'application/json'},
                json=req_body)
            response.raise_for_status()

            end_time = time.time()
            total_time = end_time - start_time
            issue_times.append(total_time)
        return issue_times


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', default='validate_one_token')
    parser.add_argument('--url', default='http://localhost:35357')
    parser.add_argument('--username', default='demo')
    parser.add_argument('--password')
    parser.add_argument('--user-domain-name', default='Default')
    parser.add_argument('--project-name', default='demo')
    parser.add_argument('--project-domain-name', default='Default')
    parser.add_argument('--validation-count', default=100, type=int)
    parser.add_argument('--issue-count', default=100, type=int)
    parser.add_argument('--concurrency', default=1, type=int)
    args = parser.parse_args()

    if args.test == 'validate_one_token':
        test = ValidateTokenTest(
            args.url,
            args.username,
            args.password,
            args.user_domain_name,
            args.project_name,
            args.project_domain_name,
            args.validation_count,
            args.concurrency,
        )
    elif args.test == 'issue_token':
        test = IssueTokenTest(
            args.url,
            args.username,
            args.password,
            args.user_domain_name,
            args.project_name,
            args.project_domain_name,
            args.issue_count,
            args.concurrency,
        )
    else:
        sys.exit('Unexpected test %r' % args.test)

    print('Test starting: %s' % datetime.datetime.now().isoformat())
    test.run_test()
    print('Test completed: %s' % datetime.datetime.now().isoformat())


if __name__ == '__main__':
    main()
