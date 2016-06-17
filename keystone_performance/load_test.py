
# This one puts a consistent load on the keystone server and prints stats as
# long as it's running.


import numpy

import argparse
import requests
import time


def issue_token(args):
    req_body = {
        'auth': {
            'identity': {
                'methods': ['password'],
                'password': {
                    'user': {
                        'name': args.username,
                        'domain': {'name': args.user_domain_name},
                        'password': args.password
                    }
                }
            },
            'scope': {
                'project': {
                    'name': args.project_name,
                    'domain': {'name': args.project_domain_name}
                }
            }
        }
    }

    response = requests.post(
        '%s/v3/auth/tokens' % args.url,
        headers={'Content-Type': 'application/json'},
        json=req_body)
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://localhost:35357')
    parser.add_argument('--username', default='demo')
    parser.add_argument('--password')
    parser.add_argument('--user-domain-name', default='Default')
    parser.add_argument('--project-name', default='demo')
    parser.add_argument('--project-domain-name', default='Default')
    args = parser.parse_args()

    times = []
    for i in xrange(10):
        start_time = time.time()
        issue_token(args)
        end_time = time.time()
        total_time = end_time - start_time
        times.append(total_time)

    # Calculate P50/P90
    min_val = min(times)
    max_val = max(times)
    p50 = numpy.percentile(times, 50)
    p90 = numpy.percentile(times, 90)
    total_time = sum(times)
    print('P50/P90: %s/%s min/max: %s/%s' % (p50, p90, min_val, max_val))


if __name__ == '__main__':
    main()
