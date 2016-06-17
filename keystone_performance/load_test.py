
# This one puts a consistent load on the keystone server and prints stats as
# long as it's running.


import numpy

import argparse
import multiprocessing
import requests
import time


def issue_token(args):
    if args.user_domain_id:
        user_domain_info = {'id': args.user_domain_id}
    else:
        user_domain_info = {'name': args.user_domain_name}
    if args.project_id:
        project_info = {'id': args.project_id}
    else:
        project_info = {'name': args.project_name}
    if args.project_domain_id:
        project_info['domain'] = {'id': args.project_domain_id}
    else:
        project_info['domain'] = {'name': args.project_domain_name}
    req_body = {
        'auth': {
            'identity': {
                'methods': ['password'],
                'password': {
                    'user': {
                        'name': args.username,
                        'domain': user_domain_info,
                        'password': args.password
                    }
                }
            },
            'scope': {
                'project': project_info
            }
        }
    }

    response = requests.post(
        '%s/v3/auth/tokens' % args.url,
        headers={'Content-Type': 'application/json'},
        json=req_body)
    response.raise_for_status()


def issue_tokens_proc(q, args):
    while True:
        start_time = time.time()
        issue_token(args)
        end_time = time.time()
        total_time = end_time - start_time
        q.put(total_time)


def issue_tokens(args):
    q = multiprocessing.Queue()

    for i in range(args.concurrency):
        p = multiprocessing.Process(target=issue_tokens_proc, args=(q, args))
        p.start()

    times = []
    last_report_time = time.time()

    while True:
        issue_time = q.get()

        if len(times) >= 1000:
            del times[0]

        times.append(issue_time)

        if time.time() - last_report_time > 10:
            last_report_time = time.time()

            # Calculate P50/P90
            min_val = min(times)
            max_val = max(times)
            p50 = numpy.percentile(times, 50)
            p90 = numpy.percentile(times, 90)
            print('P50/P90: %s/%s min/max: %s/%s' %
                  (p50, p90, min_val, max_val))


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

    issue_tokens(args)


if __name__ == '__main__':
    main()
