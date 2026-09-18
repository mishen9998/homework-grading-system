"""Check fixture rerun determinism and explicit wrong-profile refusal on this run only."""
import argparse
import contextlib
import io
import json
from pathlib import Path

from campus_fixture import main as fixture_main
from campus_runtime import assert_runtime_identity


def invoke(*args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fixture_main(list(args))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True, choices=('small', 'full'))
    args = parser.parse_args()
    run = assert_runtime_identity()['run_id']
    before = json.loads(Path('/runtime/fixture.json').read_text())
    assert invoke('seed', '--profile', args.profile, '--output', '/runtime/replay.json') == 0
    replay = json.loads(Path('/runtime/replay.json').read_text())
    other = 'small' if args.profile == 'full' else 'full'
    assert invoke('seed', '--profile', other, '--output', '/runtime/conflict.json') == 2
    refused = json.loads(Path('/runtime/conflict.json').read_text())
    assert refused['error'] == 'fixture_profile_version_or_status_conflict'
    assert invoke('verify', '--profile', args.profile, '--output', '/runtime/after-conflict.json') == 0
    after = json.loads(Path('/runtime/after-conflict.json').read_text())
    assert before['tables'] == replay['tables'] == after['tables']
    assert before['attachments'] == replay['attachments'] == after['attachments']
    report = {'run_id': run, 'profile': args.profile, 'status': 'passed',
              'same_profile': replay['action'], 'different_profile': refused['error'],
              'table_and_attachment_hashes_unchanged': True, 'no_business_rows_deleted': True}
    Path('/runtime/replay-check.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
