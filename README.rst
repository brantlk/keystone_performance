Simple keystone performance tests
=================================

Tools for testing keystone performance.

Run `python keystone_performance.test1`

Common arguments, with default::

  --test: validate_one_token
  --url: http://localhost:35357
  --username: demo
  --password
  --user-domain-name: Default
  --project-name: demo
  --project-domain-name: Default
  --concurrency: 1

Installing
----------

To install::

  pip install git+https://github.com/brantlk/keystone_performance.git

Tests
-----

validate_one_token
~~~~~~~~~~~~~~

This test gets one token, then validates it multiple times.
If token caching is enabled and configured on the server, this test will show
if keystone is properly caching/retriving the token as this should be very
fast.

Arguments, with default::

  --validation-count: 100


issue_token
~~~~~~~~~~~

This test calls the issue token request (POST /v3/auth/tokens) with the same
user.

Arguments, with default::

  --issue-count: 100
