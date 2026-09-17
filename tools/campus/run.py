"""Dedicated local Docker controller. Host Python uses only the standard library.

Secrets are generated afresh and handed to container processes over stdin. No .env,
secret file, CLI credential, Docker Config.Env credential, or existing database is used.
"""
import argparse
import hashlib
import json
import platform
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / '.campus-runs'
LABEL = 'org.campusperf.run'
PURPOSE = 'synthetic-campus-only'
WORKSPACE_ID = hashlib.sha256(str(ROOT).encode('utf-8')).hexdigest()[:12]
APP_IMAGE = 'campusperf-runtime:' + WORKSPACE_ID
GATEWAY_IMAGE = 'campusperf-gateway:' + WORKSPACE_ID
IMAGES = {
    'mysql': 'mysql@sha256:ccb8f749bb5e59f9f8f03bf7282c7ef27a93a1814a24f0a8a926fb4e19b7fb97',
    'redis': 'redis@sha256:8f157725f8eee31e65a8d4765f1f986d76aedc1a0503345dfb63a2b1b5a441ee',
    'qdrant': 'qdrant/qdrant@sha256:6ac4807063bbecddca0250bfbcff52acf18c22263b904d12919349e6d0a408f1',
    'node': 'node@sha256:d2166de198f26e17e5a442f537754dd616ab069c47cc57b889310a717e0abbf9',
}
QUOTAS = {'mysql': ('1.5', '1536m'), 'redis': ('.25', '128m'),
          'qdrant': ('.5', '512m'), 'backend': ('1.25', '1024m'), 'worker': ('.4', '256m'),
          'gateway': ('.1', '64m')}


class RuntimeFailure(RuntimeError):
    pass


def docker(*args, input_text=None):
    result = subprocess.run(['docker', *map(str, args)], input=input_text, capture_output=True,
                            encoding='utf-8', errors='replace', check=False)
    if result.returncode:
        # Arbitrary docker output could include SQL parameters; do not echo it.
        raise RuntimeFailure('Docker operation failed: ' + str(args[0]))
    return result.stdout.strip()


def identifier(value):
    if not re.fullmatch('[a-f0-9]{12}', value or ''):
        raise RuntimeFailure('invalid dedicated run identity')
    return value


def read_manifest(run_id):
    identifier(run_id)
    data = json.loads((RUNS / run_id / 'identity.json').read_text())
    if data['run_id'] != run_id or data['project'] != 'campusperf-' + run_id:
        raise RuntimeFailure('run descriptor mismatch')
    if data['database'] != 'campus_perf_' + run_id or data['port'] not in range(18100, 18120):
        raise RuntimeFailure('run target mismatch')
    return data


def verify_resources(data):
    run_id, project = data['run_id'], data['project']
    identifier(run_id)
    network = json.loads(docker('network', 'inspect', project, '--format', '{{json .}}'))
    if not network['Internal'] or network['Labels'].get(LABEL) != run_id:
        raise RuntimeFailure('dedicated internal network ownership mismatch')
    if 'gateway' in data['services']:
        ingress = json.loads(docker('network', 'inspect', project + '-ingress', '--format', '{{json .}}'))
        if ingress['Internal'] or ingress['Labels'].get(LABEL) != run_id:
            raise RuntimeFailure('dedicated ingress network ownership mismatch')
    for suffix in ('mysql', 'redis', 'qdrant', 'runtime'):
        volume = json.loads(docker('volume', 'inspect', project + '-' + suffix, '--format', '{{json .}}'))
        if volume['Labels'].get(LABEL) != run_id or volume['Labels'].get('org.campusperf.purpose') != PURPOSE:
            raise RuntimeFailure('dedicated volume ownership mismatch')
    for service in data['services']:
        name = project + '-' + service
        # Select only non-secret fields. Never inspect Config.Env.
        found = json.loads(docker('inspect', name, '--format',
            '{"labels":{{json .Config.Labels}},"networks":{{json .NetworkSettings.Networks}},'
            '"mounts":{{json .Mounts}},"ports":{{json .HostConfig.PortBindings}},'
            '"memory":{{.HostConfig.Memory}},"cpu":{{.HostConfig.NanoCpus}},"image":{{json .Image}}}'))
        expected_networks = {project, project + '-ingress'} if service == 'gateway' else {project}
        if found['labels'].get(LABEL) != run_id or set(found['networks']) != expected_networks:
            raise RuntimeFailure('dedicated container ownership mismatch')
        if found['labels'].get('org.campusperf.purpose') != PURPOSE:
            raise RuntimeFailure('dedicated container purpose mismatch')
        for mount in found['mounts']:
            if mount['Type'] != 'volume' or mount['Name'] not in {project + '-' + x for x in ('mysql', 'redis', 'qdrant', 'runtime')}:
                raise RuntimeFailure('unowned mount rejected')
        expected = {'18100/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(data['port'])}]} if service == 'gateway' else {}
        if (found['ports'] or {}) != expected:
            raise RuntimeFailure('unexpected published target rejected')
        if not found['memory'] or not found['cpu']:
            raise RuntimeFailure('resource limits missing')
        expected_image = data.get('image_ids', {}).get(service)
        if not expected_image:
            expected_image = (data['backend_image_id'] if service in ('backend', 'worker') else
                              data['gateway_image_id'] if service == 'gateway' else
                              data['images'][service].split('@', 1)[1])
        if expected_image and found['image'] != expected_image:
            raise RuntimeFailure('dedicated image identity mismatch')
    return data


def labels(run_id):
    return ['--label', LABEL + '=' + run_id, '--label', 'org.campusperf.purpose=' + PURPOSE]


def create_service(data, service, image, command, mounts=(), stdin=None):
    project, run_id = data['project'], data['run_id']
    cpu, memory = QUOTAS[service]
    options = ['run', '-d', '-i', '--name', project + '-' + service, '--network', project,
               '--network-alias', service, '--cpus', cpu, '--memory', memory,
               '--memory-swap', memory, '--pids-limit', '128', *labels(run_id)]
    health_commands = {
        'mysql': 'mysqladmin ping --silent',
        'redis': 'redis-cli ping',
        'qdrant': "bash -c ': > /dev/tcp/127.0.0.1/6333'",
        'backend': 'python -c "import urllib.request; urllib.request.urlopen(\'http://127.0.0.1:18100/api/status/ready\', timeout=3)"',
        'worker': 'python campus_exec.py python campus_worker_health.py',
        'gateway': 'wget -q -O /dev/null http://127.0.0.1:18100/api/status/health',
    }
    options += ['--health-cmd', health_commands[service], '--health-interval', '10s',
                '--health-timeout', '5s', '--health-retries', '5', '--health-start-period', '90s']
    for volume, dest in mounts:
        options += ['--mount', f'type=volume,src={project}-{volume},dst={dest}']
    if service == 'gateway':
        options += ['--network', project + '-ingress']
        options += ['-p', f"127.0.0.1:{data['port']}:18100"]
    if service == 'mysql':
        options += ['--entrypoint', 'sh']
    docker(*options, image, *command)
    if stdin is not None:
        # Bootstrap is blocked reading stdin: inspect ownership BEFORE handing it
        # credentials or allowing its first database/Redis connection.
        verify_resources(dict(data, services=data['services'] + [service]))
        # attach has no secret arguments/environment. Input is sent only to new PID 1.
        attach = subprocess.Popen(['docker', 'attach', '--sig-proxy=false', project + '-' + service],
                                  stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        attach.stdin.write(stdin.encode())
        attach.stdin.close()
        data.setdefault('_attach_processes', []).append(attach)


def json_http(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=5) as response:
        return json.load(response)


def wait_ready(data, path='/api/status/ready', timeout=180):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        states = [docker('inspect', data['project'] + '-' + name, '--format', '{{.State.Status}}')
                  for name in ('backend', 'worker')]
        if any(state in ('exited', 'dead') for state in states):
            raise RuntimeFailure('dedicated application process exited during startup')
        try:
            health = json_http(f"http://127.0.0.1:{data['port']}" + path)
            if health['run_id'] == data['run_id'] and health['status'] in ('ready', 'healthy'):
                return health
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeFailure('dedicated HTTP service readiness timed out')


def run_exec(data, command):
    verify_resources(data)
    return docker('exec', data['project'] + '-backend', 'python', 'campus_exec.py', *command)


def save(data):
    destination = RUNS / data['run_id'] / 'identity.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({k: v for k, v in data.items() if not k.startswith('_')}, indent=2), encoding='utf-8')


def start(args):
    if args.port not in range(18100, 18120):
        raise RuntimeFailure('only reserved campus HTTP range is allowed')
    # Binding checks Windows excluded ranges as well as current listeners.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
    run_id = secrets.token_hex(6)
    project = 'campusperf-' + run_id
    data = {'run_id': run_id, 'project': project, 'port': args.port, 'database': 'campus_perf_' + run_id,
            'collection': 'campus_perf_' + run_id, 'redis_namespace': 'campus_perf:' + run_id,
            'synthetic': True, 'profile': args.profile, 'services': [],
            'images': IMAGES, 'quotas': QUOTAS, 'host_os': platform.platform(),
            'docker_resources': docker('info', '--format', '{{.NCPU}} CPU; {{.MemTotal}} bytes'),
            'baseline': '38ce3f0-unverified', 'historical_pipeline': 'blocked-manual',
            'historical_blocked_checks_retried': False}
    image = APP_IMAGE
    data['backend_image_id'] = docker('image', 'inspect', image, '--format', '{{.Id}}')
    data['gateway_image_id'] = docker('image', 'inspect', GATEWAY_IMAGE, '--format', '{{.Id}}')
    data['image_ids'] = {service: docker('image', 'inspect', value, '--format', '{{.Id}}')
                         for service, value in IMAGES.items() if service != 'node'}
    data['image_ids'].update(backend=data['backend_image_id'], worker=data['backend_image_id'],
                             gateway=data['gateway_image_id'])
    data['node_version'] = docker('run', '--rm', '--network', 'none', *labels(run_id), IMAGES['node'], 'node', '--version')
    save(data)
    docker('network', 'create', '--internal', *labels(run_id), project)
    docker('network', 'create', *labels(run_id), project + '-ingress')
    for suffix in ('mysql', 'redis', 'qdrant', 'runtime'):
        docker('volume', 'create', *labels(run_id), project + '-' + suffix)
    sql_secret, root_secret = secrets.token_urlsafe(36), secrets.token_urlsafe(36)
    envelope = {'CAMPUS_RUN_ID': run_id,
                'DATABASE_URL': f'mysql+pymysql://campus_runner:{sql_secret}@mysql:3306/campus_perf_{run_id}?charset=utf8mb4',
                'REDIS_URL': 'redis://redis:6379/0', 'QDRANT_URL': 'http://qdrant:6333',
                'QDRANT_COLLECTION': 'campus_perf_' + run_id,
                'QDRANT_CHUNK_COLLECTION': 'campus_perf_' + run_id + '_chunks',
                'SECRET_KEY': secrets.token_urlsafe(48), 'JWT_SECRET_KEY': secrets.token_urlsafe(48),
                'CAMPUS_FIXTURE_PASSWORD': secrets.token_urlsafe(30), 'UPLOAD_FOLDER': '/runtime/attachments'}
    mysql_command = ['-c', 'read -r MYSQL_ROOT_PASSWORD; read -r MYSQL_PASSWORD; read -r MYSQL_DATABASE; '
                     'MYSQL_USER=campus_runner; export MYSQL_ROOT_PASSWORD MYSQL_PASSWORD MYSQL_DATABASE MYSQL_USER; '
                     'exec docker-entrypoint.sh mysqld --max-connections=150 --innodb-buffer-pool-size=512M']
    create_service(data, 'mysql', IMAGES['mysql'], mysql_command, [('mysql', '/var/lib/mysql')],
                   root_secret + '\n' + sql_secret + '\n' + data['database'] + '\n')
    data['services'].append('mysql'); save(data)
    create_service(data, 'redis', IMAGES['redis'], ['redis-server', '--appendonly', 'yes', '--maxmemory', '96mb', '--maxmemory-policy', 'noeviction'], [('redis', '/data')])
    data['services'].append('redis'); save(data)
    create_service(data, 'qdrant', IMAGES['qdrant'], [], [('qdrant', '/qdrant/storage')])
    data['services'].append('qdrant'); save(data)
    # Place only the non-secret descriptor into the dedicated runtime volume.
    bootstrap = project + '-descriptor'
    docker('create', '--name', bootstrap, '--network', project, *labels(run_id),
           '--mount', f'type=volume,src={project}-runtime,dst=/runtime', '--entrypoint', 'true', image)
    docker('cp', str(RUNS / run_id / 'identity.json'), bootstrap + ':/runtime/identity.json')
    docker('rm', bootstrap)
    credentials = json.dumps(envelope) + '\n'
    create_service(data, 'backend', image,
                   ['gunicorn', '-w', '2', '--threads', '4', '-b', '0.0.0.0:18100', '--timeout', '120', 'campus_runtime:create_campus_app()'],
                   [('runtime', '/runtime')], credentials)
    data['services'].append('backend'); save(data)
    create_service(data, 'worker', image, ['python', 'campus_runtime.py'], [('runtime', '/runtime')], credentials)
    data['services'].append('worker'); save(data)
    create_service(data, 'gateway', GATEWAY_IMAGE, [])
    data['services'].append('gateway'); save(data)
    verify_resources(data)
    # MySQL cold initialization may take longer than the HTTP bootstrap.
    wait_ready(data, '/api/status/health')
    wait_ready(data)
    print(json.dumps({'run_id': run_id, 'status': 'healthy', 'profile': args.profile}), flush=True)
    print(run_exec(data, ['python', 'campus_fixture.py', 'seed', '--profile', args.profile, '--output', '/runtime/fixture.json']), flush=True)
    print(run_exec(data, ['python', 'campus_smoke.py']), flush=True)
    data['health'] = wait_ready(data)
    data['dependencies'] = run_exec(data, ['python', '-m', 'pip', 'freeze']).splitlines()
    data['python_version'] = run_exec(data, ['python', '--version'])
    save(data)
    export(data)
    print(json.dumps({'run_id': run_id, 'status': 'complete', 'evidence': str(RUNS / run_id)}))


def export(data):
    verify_resources(data)
    for name in ('fixture.json', 'http-smoke.json'):
        docker('cp', data['project'] + '-backend:/runtime/' + name, str(RUNS / data['run_id'] / name))
    for name in ('environment.json', 'replay-check.json', 'verify.json'):
        try:
            docker('exec', data['project'] + '-backend', 'test', '-f', '/runtime/' + name)
        except RuntimeFailure:
            continue
        docker('cp', data['project'] + '-backend:/runtime/' + name, str(RUNS / data['run_id'] / name))
    facts = {'run_id': data['run_id'], 'docker_health': {}, 'statistics_are_snapshot_not_capacity': True}
    for service in data['services']:
        facts['docker_health'][service] = docker('inspect', data['project'] + '-' + service,
                                                '--format', '{{.State.Health.Status}}')
    facts['published_ports'] = docker('port', data['project'] + '-gateway')
    facts['resource_snapshot'] = docker('stats', '--no-stream', '--format', '{{json .}}',
                                       *[data['project'] + '-' + s for s in data['services']]).splitlines()
    (RUNS / data['run_id'] / 'runtime-snapshot.json').write_text(json.dumps(facts, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    build = sub.add_parser('build')
    start_parser = sub.add_parser('start')
    start_parser.add_argument('--profile', choices=('small', 'full'), default='small')
    start_parser.add_argument('--port', type=int, default=18100)
    for action in ('status', 'export', 'stop', 'exec'):
        command = sub.add_parser(action)
        command.add_argument('--run', required=True)
        if action == 'exec':
            command.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == 'build':
        print(docker('build', '-f', str(ROOT / 'tools/campus/Dockerfile'), '-t', APP_IMAGE,
                     '--label', 'org.campusperf.purpose=' + PURPOSE, str(ROOT)))
        print(docker('build', '-f', str(ROOT / 'tools/campus/Gateway.Dockerfile'), '-t', GATEWAY_IMAGE,
                     '--label', 'org.campusperf.purpose=' + PURPOSE, str(ROOT)))
        print(json.dumps({'backend_image': APP_IMAGE, 'gateway_image': GATEWAY_IMAGE}))
    elif args.action == 'start':
        start(args)
    else:
        data = verify_resources(read_manifest(args.run))
        if args.action == 'status':
            print(json.dumps(wait_ready(data), indent=2))
        elif args.action == 'export':
            export(data)
        elif args.action == 'exec':
            command = args.command[1:] if args.command[:1] == ['--'] else args.command
            if not command:
                raise RuntimeFailure('maintenance command required')
            print(run_exec(data, command))
        elif args.action == 'stop':
            docker('stop', *[data['project'] + '-' + name for name in reversed(data['services'])])
            print('Dedicated containers stopped; volumes retained. Resume requires fresh process credentials or a new run.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Deliberately avoid arbitrary exception messages/SQL in console output.
        print(json.dumps({'status': 'failed', 'type': type(exc).__name__,
                          'message': str(exc) if isinstance(exc, RuntimeFailure) else 'isolated run failed; retained for review'}))
        raise SystemExit(1)
