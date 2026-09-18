import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from desktop_assistant import core, service


def test_instance_lock_exclusive_and_released(tmp_path):
    lock = core.InstanceLock(tmp_path / 'assistant.lock')
    try:
        with pytest.raises(core.AssistantError):
            core.InstanceLock(tmp_path / 'assistant.lock')
    finally:
        lock.close()
    core.InstanceLock(tmp_path / 'assistant.lock').close()


def test_port_conflict_does_not_start_or_kill_other_process():
    with socket.socket() as busy:
        busy.bind(('127.0.0.1', 0))
        busy.listen()
        with patch.object(core.subprocess, 'Popen') as popen:
            with pytest.raises(core.AssistantError):
                core.require_free_port(busy.getsockname()[1])
            popen.assert_not_called()


def test_stop_uses_private_pipe_not_terminate():
    control = core.Controller()
    child = Mock()
    child.poll.return_value = None
    control.process = child
    control.stop()
    child.stdin.write.assert_called_once_with(b'stop\n')
    child.terminate.assert_not_called()
    child.kill.assert_not_called()
    assert control.process is None


def test_stop_timeout_retains_process_and_never_kills():
    control = core.Controller()
    child = Mock()
    child.poll.return_value = None
    child.wait.side_effect = subprocess.TimeoutExpired('owned', 40)
    control.process = child
    with pytest.raises(core.AssistantError):
        control.stop()
    assert control.process is child
    child.terminate.assert_not_called()
    child.kill.assert_not_called()


def test_duplicate_start_no_new_child():
    control = core.Controller()
    control.process = Mock()
    control.process.poll.return_value = None
    with patch.object(core.subprocess, 'Popen') as popen:
        control.start()
        popen.assert_not_called()


def test_ready_rejects_other_instance_even_if_http_ready():
    from io import BytesIO
    control = core.Controller()
    control.instance = 'ours'
    control.process = Mock()
    control.process.poll.return_value = None
    opener = Mock()
    opener.open.return_value = BytesIO(b'{"status":"ready","instance":"another"}')
    with patch.object(core.urllib.request, 'build_opener', return_value=opener):
        assert control.ready() is False


def test_failed_preflight_is_explicit_and_hides_raw_output():
    completed = Mock(returncode=1, stdout=json.dumps({'ok': False, 'error': '缺少运行依赖'}).encode())
    with patch.object(core.subprocess, 'run', return_value=completed):
        with pytest.raises(core.AssistantError, match='缺少运行依赖'):
            core.check_runtime('python', None)
    completed.stdout = b'private malformed database URL'
    with patch.object(core.subprocess, 'run', return_value=completed):
        with pytest.raises(core.AssistantError, match='环境检查未完成'):
            core.check_runtime('python', None)


def test_source_update_invalidates_build(tmp_path):
    front = tmp_path / 'frontend/src'
    front.mkdir(parents=True)
    source = front / '中文页面.vue'
    source.write_text('first', encoding='utf-8')
    before = core.source_digest(tmp_path)
    source.write_text('second', encoding='utf-8')
    assert core.source_digest(tmp_path) != before


def test_unchanged_build_needs_no_node(tmp_path):
    (tmp_path / 'frontend/dist').mkdir(parents=True)
    (tmp_path / 'frontend/dist/index.html').write_text('built')
    local = tmp_path / 'local'
    local.mkdir()
    (local / 'frontend.sha256').write_text(core.source_digest(tmp_path))
    with patch.object(core.shutil, 'which', return_value=None), patch.object(core.subprocess, 'run') as run:
        core.prepare_frontend(None, Mock(), root=tmp_path, local=local)
        run.assert_not_called()


def test_missing_build_dependencies_refuses_start(tmp_path):
    with patch.object(core.shutil, 'which', return_value=None):
        with pytest.raises(core.AssistantError, match='前端尚未准备好'):
            core.prepare_frontend(None, Mock(), root=tmp_path, local=tmp_path)


@pytest.fixture
def desktop_client(tmp_path):
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/test.js').write_text('console.log(1)')
    (tmp_path / 'index.html').write_text('<h1>desktop</h1>')
    app = Flask('desktop-test', static_folder=None)
    service.install_web_routes(app, tmp_path, 'owned-instance')
    return app.test_client()


def test_spa_deep_link_and_static_cache(desktop_client):
    page = desktop_client.get('/teacher/home')
    assert page.status_code == 200
    assert page.headers['Cache-Control'] == 'no-store'
    assert desktop_client.get('/assets/test.js').status_code == 200
    assert desktop_client.get('/assets/missing.js').status_code == 404


@pytest.mark.parametrize('path', ['/api/unknown', '/.env', '/backend/config.py', '/assets/../index.html', '/assets/%5C..%5Csecret'])
def test_unknown_api_and_private_paths_never_return_spa(desktop_client, path):
    response = desktop_client.get(path)
    assert response.status_code == 404
    assert b'<h1>desktop</h1>' not in response.data


def test_database_down_is_not_ready(desktop_client):
    with patch.object(service, 'database_ready', side_effect=RuntimeError('private SQL credentials')):
        response = desktop_client.get('/api/status/ready')
    assert response.status_code == 503
    assert b'credentials' not in response.data
    assert desktop_client.get('/api/status/health').json['mode'] == 'desktop'


def test_ready_identifies_exact_owned_instance(desktop_client):
    with patch.object(service, 'database_ready', return_value=True):
        response = desktop_client.get('/api/status/ready')
    assert response.json == {'status': 'ready', 'instance': 'owned-instance'}


def test_drain_completes_active_request_before_shutdown():
    entered, release = threading.Event(), threading.Event()
    def application(env, start):
        entered.set()
        release.wait(2)
        start('200 OK', [])
        return [b'done']
    draining = service.DrainRequests(application)
    response = draining({}, Mock())
    thread = threading.Thread(target=lambda: list(response))
    thread.start()
    assert entered.wait(1)
    assert draining.drain(timeout=.01) is False
    assert draining.stopping is False  # Long write not killed, service resumes.
    release.set()
    thread.join(2)
    assert draining.drain(timeout=1) is True
    status = Mock()
    assert list(draining({}, status)) == [b'{"error":"Service is stopping"}']
    assert status.call_args.args[0].startswith('503')


def test_application_error_releases_active_counter():
    def broken(env, start):
        raise RuntimeError('failed')
    draining = service.DrainRequests(broken)
    with pytest.raises(RuntimeError):
        list(draining({}, Mock()))
    assert draining.active == 0


def test_unstarted_response_does_not_block_stop():
    application = Mock(return_value=[b'ok'])
    draining = service.DrainRequests(application)
    response = draining({}, Mock())
    response.close()
    application.assert_not_called()
    assert draining.drain(timeout=.01)


def test_ui_can_be_created_and_closed_without_launching_services():
    import tkinter as tk
    from desktop_assistant.app import DesktopApp
    window = tk.Tk()
    window.withdraw()
    try:
        app = DesktopApp(window, auto_start=False, auto_open=False)
        assert app.status.get() == '尚未启动'
        assert app.controller.process is None
        app.append('仅测试窗口，不启动服务')
        window.update_idletasks()
        assert '仅测试窗口' in app.messages.get('1.0', 'end')
    finally:
        window.destroy()
