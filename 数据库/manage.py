"""Local MySQL handoff tools. Never print credentials or account contents.

Generated backups are sensitive, ignored by Git, and restricted to the owner.
Only restore into a NEW database; never overwrite an existing schema.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')
UPLOAD_DIRS = ('backend/app/tupian', 'backend/app/uploads', 'tupian')


def validate_name(name):
    if not name or not IDENTIFIER.fullmatch(name):
        raise ValueError('数据库名仅允许字母开头的字母、数字和下划线（最长 64 字符）')
    return name


def configured_url(env_file):
    # Explicit file wins: avoids accidentally targeting a shell's other project.
    value = dotenv_values(env_file).get('DATABASE_URL')
    if not value:
        raise ValueError('配置文件缺少 DATABASE_URL')
    url = make_url(value)
    if url.drivername != 'mysql+pymysql':
        raise ValueError('本工具只接受 mysql+pymysql，不能把 SQLite 文件当作 MySQL 备份')
    validate_name(url.database)
    return url


def engine_for(url):
    return create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 8})


def server_url(url):
    # URL.set(database=None) means "leave unchanged", NOT clear the database.
    return url._replace(database=None)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def restrict_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        who = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                             capture_output=True, check=True).stdout.decode(errors='replace')
        sid = re.search(r'S-1-\d+(?:-\d+)+', who)
        if not sid:
            raise RuntimeError('无法确定当前用户 SID；未创建敏感文件')
        subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                        f'*{sid.group()}:(OI)(CI)F'], capture_output=True, check=True)
    else:
        path.chmod(0o700)


@contextmanager
def client_options(url):
    with tempfile.TemporaryDirectory(prefix='homework-mysql-') as directory:
        folder = Path(directory)
        restrict_directory(folder)
        option_file = folder / 'client.cnf'
        def quote(value):
            return '"' + str(value or '').replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'
        settings = {'host': url.host or '127.0.0.1', 'port': url.port or 3306,
                    'user': url.username, 'password': url.password,
                    'default-character-set': 'utf8mb4', 'protocol': 'TCP'}
        option_file.write_text('[client]\n' + ''.join(f'{key}={quote(value)}\n' for key, value in settings.items()), encoding='utf-8')
        yield option_file


def mysql_command(program, options, arguments, stdin=None):
    executable = shutil.which(program)
    if not executable:
        raise RuntimeError(f'未找到 {program}，请将 MySQL 8 的 bin 目录加入 PATH')
    # --defaults-file must be the first option. stderr may contain row contents;
    # do not forward it into logs or assistant output.
    result = subprocess.run([executable, f'--defaults-file={options}', *arguments],
                            stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(f'{program} 执行失败（退出码 {result.returncode}），未将敏感错误输出到终端')


def inventory(connection):
    inspector = inspect(connection)
    quote = connection.dialect.identifier_preparer.quote
    tables = sorted(inspector.get_table_names())
    counts = {table: connection.scalar(text(f'SELECT COUNT(*) FROM {quote(table)}')) for table in tables}
    # Row values are streamed into a digest, never returned or logged.
    columns = {table: [column['name'] for column in inspector.get_columns(table)] for table in tables}
    versions = list(connection.execute(text('SELECT version_num FROM alembic_version')).scalars()) if 'alembic_version' in tables else []
    digests = {}
    orphans = {}
    for table in tables:
        digest = hashlib.sha256()
        order = inspector.get_pk_constraint(table).get('constrained_columns') or columns[table]
        statement = f'SELECT * FROM {quote(table)} ORDER BY ' + ','.join(quote(column) for column in order)
        for row in connection.execution_options(stream_results=True).execute(text(statement)):
            values = [value.hex() if isinstance(value, bytes) else str(value) if value is not None else None for value in row]
            blob = json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            digest.update(len(blob).to_bytes(8, 'big'))
            digest.update(blob)
        digests[table] = digest.hexdigest()
        for foreign_key in inspector.get_foreign_keys(table):
            target = foreign_key['referred_table']
            pairs = list(zip(foreign_key['constrained_columns'], foreign_key['referred_columns']))
            not_null = ' AND '.join(f'c.{quote(left)} IS NOT NULL' for left, _ in pairs)
            join = ' AND '.join(f'c.{quote(left)}=p.{quote(right)}' for left, right in pairs)
            sql = f'SELECT COUNT(*) FROM {quote(table)} c WHERE {not_null} AND NOT EXISTS (SELECT 1 FROM {quote(target)} p WHERE {join})'
            orphans[f'{table}.{foreign_key["name"]}'] = connection.scalar(text(sql))
    return {'table_counts': counts, 'columns': columns, 'migration_versions': versions,
            'table_digests': digests, 'foreign_key_orphans': orphans}


def check(url):
    engine = engine_for(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_view_names():
                raise ValueError('存在视图，需核实跨库依赖后专门迁移')
            result = inventory(connection)
            result.update(connected=True, host=url.host, port=url.port or 3306,
                          database=url.database, server_version=connection.scalar(text('SELECT VERSION()')))
            return result
    finally:
        engine.dispose()


def backup(url, stopped):
    if not stopped:
        raise ValueError('备份前请停止本项目 Web/worker 写入，再提供 --writes-stopped；不要停止 MySQL')
    custom_upload = os.environ.get('UPLOAD_FOLDER') or dotenv_values(ROOT / 'backend/.env').get('UPLOAD_FOLDER')
    if custom_upload and custom_upload != 'tupian':
        raise ValueError('检测到自定义附件路径，当前自动备份只支持默认路径；请先制定对应附件迁移方案')
    destination = HERE / 'backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6])
    restrict_directory(destination)
    engine = engine_for(url)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_view_names():
                raise ValueError('存在视图，需核实跨库依赖后专门迁移')
            for catalog in ('triggers', 'routines', 'events'):
                schema_field = {'triggers': 'trigger_schema', 'routines': 'routine_schema', 'events': 'event_schema'}[catalog]
                if connection.scalar(text(f'SELECT COUNT(*) FROM information_schema.{catalog} WHERE {schema_field}=DATABASE()')):
                    raise ValueError('存在触发器/存储过程/事件，需专门迁移方案；本工具不会静默遗漏')
            non_innodb = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE' AND engine <> 'InnoDB'")).scalars().all()
            if non_innodb:
                raise ValueError('存在非 InnoDB 表，拒绝把单事务导出标为完整备份')
            before = inventory(connection)
        dump = destination / 'database.sql'
        with client_options(url) as options:
            mysql_command('mysqldump', options, ['--single-transaction', '--quick', '--hex-blob',
                '--no-tablespaces', '--set-gtid-purged=OFF', '--skip-add-drop-table',
                '--skip-add-locks', '--skip-triggers', '--column-statistics=0',
                f'--result-file={dump}', url.database])
        files = {}
        with zipfile.ZipFile(destination / 'attachments.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for relative in UPLOAD_DIRS:
                folder = ROOT / relative
                if folder.exists():
                    for path in sorted(folder.rglob('*')):
                        if path.is_symlink():
                            raise ValueError('附件目录包含符号链接，需人工检查后备份')
                        if path.is_file():
                            name = path.relative_to(ROOT).as_posix()
                            files[name] = sha256(path)
                            archive.write(path, name)
        if any(sha256(ROOT / name) != digest for name, digest in files.items()):
            raise RuntimeError('备份期间附件变化，请停写后重新备份')
        with engine.connect() as connection:
            after = inventory(connection)
        if before != after:
            raise RuntimeError('备份期间表结构或行数变化；本次没有生成完成清单，请停写后重新备份')
        manifest = {'format': 1, 'source_database': url.database, 'created_utc': datetime.now(timezone.utc).isoformat(),
                    **before, 'attachments': files,
                    'files': {name: sha256(destination / name) for name in ('database.sql', 'attachments.zip')},
                    'writes_stopped_confirmed': True,
                    'excluded': ['MySQL system users/grants', '.env and API secrets', 'Redis', 'Qdrant', 'model weights']}
        (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'backup': str(destination), 'tables': len(before['table_counts']), 'accounts': before['table_counts'].get('users', 0), 'attachment_files': len(files)}
    finally:
        engine.dispose()


def verified_manifest(folder):
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 1 or set(manifest.get('files', {})) != {'database.sql', 'attachments.zip'}:
        raise ValueError('不支持或不完整的备份清单')
    for name, expected in manifest['files'].items():
        if sha256(folder / name) != expected:
            raise ValueError(f'备份校验失败：{name}')
    return manifest


def restore(url, folder, target, confirmed):
    validate_name(target)
    if target == url.database or target in {'mysql', 'sys', 'information_schema', 'performance_schema'}:
        raise ValueError('不能覆盖当前库或系统库')
    if confirmed != target:
        raise ValueError('请用 --confirm-target 再次指定新库名')
    manifest = verified_manifest(folder)
    target_url = url.set(database=target)
    engine = engine_for(server_url(url))
    try:
        with engine.begin() as connection:
            exists = connection.scalar(text('SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=:name'), {'name': target})
            if exists:
                raise ValueError('目标库已存在，拒绝导入；请使用全新的库名')
            connection.execute(text(f'CREATE DATABASE `{target}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'))
        with client_options(target_url) as options, (folder / 'database.sql').open('rb') as stream:
            mysql_command('mysql', options, ['--binary-mode', target], stdin=stream)
        result = check(target_url)
        if result['table_counts'] != manifest['table_counts'] or result['columns'] != manifest['columns']:
            raise RuntimeError('恢复后的结构或行数不同；保留目标库供排查，不切换应用')
        if manifest.get('table_digests') and result['table_digests'] != manifest['table_digests']:
            raise RuntimeError('恢复后的逐表内容摘要不同，保留目标库供排查')
        # Stage only, never overwrite this machine's attachments.
        staged = HERE / 'local' / ('restored-' + target)
        if staged.exists():
            raise ValueError('附件暂存目录已存在，拒绝覆盖')
        restrict_directory(staged)
        with zipfile.ZipFile(folder / 'attachments.zip') as archive:
            if set(archive.namelist()) != set(manifest['attachments']):
                raise ValueError('附件列表不匹配')
            for member in archive.infolist():
                path = (staged / member.filename).resolve()
                if not path.is_relative_to(staged.resolve()) or not any(member.filename.startswith(prefix + '/') for prefix in UPLOAD_DIRS):
                    raise ValueError('附件路径不在允许范围内')
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output)
                if sha256(path) != manifest['attachments'][member.filename]:
                    raise ValueError('附件内容校验失败')
        return {'restored_database': target, 'tables_verified': len(manifest['table_counts']),
                'attachment_files_verified': len(manifest['attachments']), 'staged_attachments': str(staged),
                'application_configuration_changed': False}
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / 'backend' / '.env')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('check')
    export = sub.add_parser('backup')
    export.add_argument('--writes-stopped', action='store_true')
    load = sub.add_parser('restore')
    load.add_argument('--backup', type=Path, required=True)
    load.add_argument('--target', required=True)
    load.add_argument('--confirm-target', required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--backup', type=Path, required=True)
    verify.add_argument('--target', required=True)
    args = parser.parse_args()
    try:
        url = configured_url(args.env_file)
        if args.command == 'check':
            result = check(url)
        elif args.command == 'backup':
            result = backup(url, args.writes_stopped)
        elif args.command == 'restore':
            result = restore(url, args.backup.resolve(), args.target, args.confirm_target)
        else:
            manifest = verified_manifest(args.backup.resolve())
            current = check(url.set(database=validate_name(args.target)))
            if not manifest.get('table_digests'):
                raise ValueError('旧清单没有内容摘要，请生成新版备份后校验')
            mismatches = [table for table, digest in manifest['table_digests'].items()
                          if current['table_digests'].get(table) != digest]
            result = {'database': args.target, 'matching': not mismatches, 'different_tables': mismatches,
                      'foreign_key_orphans': current['foreign_key_orphans']}
            if mismatches:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
    except Exception as exc:
        # SQL/driver exceptions can contain connection strings, literals, hashes.
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__, 'error': '操作失败，敏感异常内容已隐藏；未自动删除任何数据库或备份'}, ensure_ascii=False))
    return 1


if __name__ == '__main__':
    sys.exit(main())
