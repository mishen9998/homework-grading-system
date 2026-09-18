import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('handoff_manage', ROOT / '数据库/manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)
startup_spec = importlib.util.spec_from_file_location('local_startup', ROOT / 'start_all.py')
startup = importlib.util.module_from_spec(startup_spec)
startup_spec.loader.exec_module(startup)


class DatabaseToolTests(unittest.TestCase):
    def test_startup_failure_has_nonzero_exit_and_cleans_only_owned_processes(self):
        from unittest.mock import Mock
        backend, frontend = Mock(), Mock()
        with patch.object(startup, 'backend_process', backend), patch.object(startup, 'frontend_process', frontend):
            with self.assertRaises(SystemExit) as stopped:
                startup.cleanup(exit_code=1)
        self.assertEqual(stopped.exception.code, 1)
        backend.terminate.assert_called_once()
        frontend.terminate.assert_called_once()

    def test_server_connection_has_no_database(self):
        url = make_url('mysql+pymysql://example:example@127.0.0.1/does_not_exist')
        self.assertIsNone(manage.server_url(url).database)
        self.assertEqual(url.database, 'does_not_exist')

    def test_backup_requires_stopped_writes_before_any_io(self):
        with patch.object(manage, 'engine_for') as connect:
            with self.assertRaises(ValueError):
                manage.backup(make_url('mysql+pymysql://localhost/homework'), False)
            connect.assert_not_called()

    def test_no_restore_over_source_or_system_database(self):
        url = make_url('mysql+pymysql://localhost/homework')
        for target in ('homework', 'mysql', 'sys'):
            with self.assertRaises(ValueError):
                manage.restore(url, Path('not-opened'), target, target)

    def test_restore_requires_explicit_matching_target(self):
        with self.assertRaises(ValueError):
            manage.restore(make_url('mysql+pymysql://localhost/homework'), Path('not-opened'), 'homework_copy', 'different')

    def test_checksum_detects_changed_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ('database.sql', 'attachments.zip'):
                (folder / name).write_bytes(b'synthetic')
            manifest = {'format': 1, 'files': {name: manage.sha256(folder / name) for name in ('database.sql', 'attachments.zip')}}
            (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            manage.verified_manifest(folder)
            (folder / 'database.sql').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                manage.verified_manifest(folder)

    def test_failed_readiness_is_not_treated_as_started(self):
        from urllib.error import HTTPError
        with patch('urllib.request.urlopen', side_effect=HTTPError('local', 503, 'not ready', {}, None)), patch.object(startup.time, 'sleep'):
            self.assertFalse(startup.wait_for_backend(timeout=0.001))

    def test_occupied_port_does_not_kill_process(self):
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            with patch.object(startup.subprocess, 'run') as run:
                with self.assertRaises(RuntimeError):
                    startup.require_free_port(listener.getsockname()[1])
                run.assert_not_called()
