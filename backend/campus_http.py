"""Reusable real HTTP client; metrics deliberately exclude bodies and credentials."""
import hashlib
import ipaddress
import re
import time
import uuid
from urllib.parse import urlsplit

import requests


def validate_target(base_url, run_id):
    target = urlsplit(base_url)
    try:
        loopback = ipaddress.ip_address(target.hostname).is_loopback
    except (ValueError, TypeError):
        loopback = False
    if (not loopback or target.scheme != 'http' or target.username or target.password
            or target.path not in ('', '/') or target.query or target.fragment
            or target.port not in range(18100, 18120)
            or not re.fullmatch('[a-f0-9]{12}', run_id)):
        raise ValueError('a dedicated loopback campus target and run identity are required')


class CampusClient:
    def __init__(self, base_url, run_id, sink=None):
        validate_target(base_url, run_id)
        self.base_url = base_url.rstrip('/')
        self.run_id = run_id
        self.session = requests.Session()
        self.session.trust_env = False
        self.sink = sink
        self.participant = None
        response = self.session.get(self.base_url + '/api/status/health', timeout=5, allow_redirects=False)
        if response.status_code != 200 or response.json().get('run_id') != run_id:
            raise ValueError('HTTP service did not attest the dedicated run')

    def request(self, method, path, **kwargs):
        if not path.startswith('/api/') or '://' in path or '?' in path:
            raise ValueError('only relative campus API paths are accepted')
        trace = uuid.uuid4().hex
        headers = dict(kwargs.pop('headers', {}), **{'X-Campus-Trace': trace})
        started = time.perf_counter()
        status, server_ms, error = 0, None, None
        try:
            response = self.session.request(method, self.base_url + path, headers=headers,
                                            timeout=kwargs.pop('timeout', 20), allow_redirects=False, **kwargs)
            status = response.status_code
            if response.headers.get('X-Campus-Run') != self.run_id:
                raise ValueError('HTTP response run identity mismatch')
            match = re.search(r'app;dur=([0-9.]+)', response.headers.get('Server-Timing', ''))
            server_ms = float(match[1]) if match else None
            return response
        except requests.RequestException as exc:
            error = type(exc).__name__
            raise
        finally:
            if self.sink:
                self.sink({'trace': trace, 'participant': self.participant,
                           'method': method, 'route': re.sub(r'/[0-9]+', '/:id', path),
                           'status': status, 'client_ms': round((time.perf_counter() - started) * 1000, 3),
                           'server_ms': server_ms, 'error': error})

    def login(self, organization_code, username, password):
        self.participant = hashlib.sha256((self.run_id + ':' + organization_code + ':' + username).encode()).hexdigest()[:20]
        response = self.request('POST', '/api/auth/login', json={
            'organization_code': organization_code, 'username': username, 'password': password})
        if response.status_code != 200:
            raise RuntimeError('positive synthetic login failed')
        self.session.headers['Authorization'] = 'Bearer ' + response.json()['access_token']
        return response.json()['user']['role']
