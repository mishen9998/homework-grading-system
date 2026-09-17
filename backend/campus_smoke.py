"""Positive role reads only. Tokens, passwords and response bodies never leave memory."""
import argparse
import json
import os
from pathlib import Path

from campus_http import CampusClient
from campus_runtime import assert_runtime_identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/runtime/http-smoke.json')
    args = parser.parse_args()
    identity = assert_runtime_identity()
    rows, roles = [], {}
    # The client runs inside the backend container on a second loopback-only port.
    # The host still verifies its published HTTP port separately.
    client = CampusClient('http://127.0.0.1:18100', identity['run_id'], sink=rows.append)
    for role in ('student', 'teacher'):
        actual = client.login('campus_01', role + '_00001', os.environ['CAMPUS_FIXTURE_PASSWORD'])
        if actual != role:
            raise RuntimeError('positive role mismatch')
        response = client.request('GET', '/api/courses/my-courses')
        if response.status_code != 200 or not response.json().get('courses'):
            raise RuntimeError('positive role course read failed')
        roles[role] = 1
    result = {'run_id': identity['run_id'], 'http_participants': 2, 'roles': roles,
              'requests': rows, 'capacity_test': False, 'fixture_accounts_are_not_participants': True}
    Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'http_participants': 2, 'requests': len(rows), 'status': 'passed'}))


if __name__ == '__main__':
    main()
