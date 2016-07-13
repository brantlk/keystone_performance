Keystone performance tests
==========================

Tools for testing keystone performance.

This repository contains a couple of scripts for testing keystone performance.

Installing
----------

To install::

  pip install git+https://github.com/brantlk/keystone_performance.git

load_test
~~~~~~~~~

Run ``python keystone_performance.load_test``

This test generates load at a certain concurrency for some amount of time, then
generates load at another concurrency and so forth. When all the concurrencies
are run it prints out a summary.

Arguments, with default (if any)::

  --type: full
  --url: http://localhost:35357
  --username: demo
  --password
  --user-domain-name: Default
  --user-domain-id
  --project-name: demo
  --project-id
  --project-domain-name: Default
  --project-domain-id
  --out-file

For developers, you'll want to set ``--type=quick`` this runs a few low
concurrency tests for a short time just to show that the program works.

If --out_file is provided then a file is generated with 1 line per
concurrency::

  <start time>,<end time>,<concurrency>,<latency p90>


test1
-----

Run ``python keystone_performance.test1``

Common arguments, with default::

  --test: validate_one_token
  --url: http://localhost:35357
  --username: demo
  --password
  --user-domain-name: Default
  --project-name: demo
  --project-domain-name: Default
  --concurrency: 1

Tests
~~~~~

validate_one_token
^^^^^^^^^^^^^^^^^^

This test gets one token, then validates it multiple times.
If token caching is enabled and configured on the server, this test will show
if keystone is properly caching/retriving the token as this should be very
fast.

Arguments, with default::

  --validation-count: 100


issue_token
^^^^^^^^^^^

This test calls the issue token request (``POST /v3/auth/tokens``) with the same
user.

Arguments, with default::

  --issue-count: 100
