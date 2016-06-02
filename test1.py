
# Gets a token for a user, then validates that token some # of times.
# Prints out the perf stats for it.

# Arguments:
#   --url: http://localhost:35357
#   --username: demo
#   --password
#   --user-domain-name: Default
#   --project-name: demo
#   --project-domain-name: Default
#   --validation-count: 100

import argparse
import time

import numpy
import requests


def run_test(
        base_url, username, password, user_domain_name, project_name,
        project_domain_name, validation_count):
    # Get a token as demo user.
    req_body = {
        'auth': {
            'identity': {
                'methods': ['password'],
                'password': {
                    'user': {
                        'name': username,
                        'domain': {'name': user_domain_name},
                        'password': password
                    }
                }
            },
            'scope': {
                'project': {
                    'name': project_name,
                    'domain': {'name': project_domain_name}
                }
            }
        }
    }

    response = requests.post(
        '%s/v3/auth/tokens' % base_url,
        headers={'Content-Type': 'application/json'},
        json=req_body)
    response.raise_for_status()
    user_token = response.headers['X-Subject-Token']

    # Validate the token
    validation_times = []
    total_start_time = time.time()
    for i in xrange(validation_count):
        start_time = time.time()
        response = requests.get(
            '%s/v3/auth/tokens' % base_url,
            headers={
                'Content-Type': 'application/json',
                'X-Auth-Token': user_token,
                'X-Subject-Token': user_token
            })
        response.raise_for_status()
        end_time = time.time()
        total_time = end_time - start_time
        validation_times.append(total_time)
    total_end_time = time.time()

    # Calculate P50/P90
    min_val = min(validation_times)
    max_val = max(validation_times)
    p50 = numpy.percentile(validation_times, 50)
    p90 = numpy.percentile(validation_times, 90)
    total_time = sum(validation_times)
    total_wall_time = total_end_time - total_start_time
    print('P50/P90: %s/%s min/max: %s/%s total: %s wall: %s' % (
        p50, p90, min_val, max_val, total_time, total_wall_time))


def main():
    print('Working...')

    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://localhost:35357')
    parser.add_argument('--username', default='demo')
    parser.add_argument('--password')
    parser.add_argument('--user-domain-name', default='Default')
    parser.add_argument('--project-name', default='demo')
    parser.add_argument('--project-domain-name', default='Default')
    parser.add_argument('--validation-count', default=100, type=int)
    args = parser.parse_args()

    run_test(
        args.url,
        args.username,
        args.password,
        args.user_domain_name,
        args.project_name,
        args.project_domain_name,
        args.validation_count
    )


main()
