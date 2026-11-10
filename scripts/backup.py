"""Create consistent SQLite snapshots or optional PostgreSQL custom backups."""
from datetime import datetime
from contextlib import closing
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid


class BackupError(RuntimeError):
    """An actionable error that can be shown by the local interface."""


def _pg_dump_binary(major):
    override = os.environ.get('MELO_PG_BIN')
    candidates = []
    executable = 'pg_dump.exe' if os.name == 'nt' else 'pg_dump'
    if override:
        candidates.append(Path(override) / executable)
    if os.name == 'nt':
        candidates.append(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) /
                          'PostgreSQL' / str(major) / 'bin' / executable)
    on_path = shutil.which('pg_dump')
    if on_path:
        candidates.append(Path(on_path))
    for candidate in dict.fromkeys(candidates):
        if not candidate.is_file():
            continue
        try:
            result = subprocess.run([str(candidate), '--version'], capture_output=True,
                                    text=True, timeout=10, check=True)
            match = re.search(r'\(PostgreSQL\)\s+(\d+)', result.stdout)
            if match and int(match.group(1)) == major:
                return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    raise BackupError(
        f'Não foi encontrado pg_dump da versão {major}. Configure MELO_PG_BIN no .env '
        'com a pasta bin da mesma versão do PostgreSQL.')


def _create_postgresql_backup():
    from django.conf import settings
    from django.db import connection

    try:
        connection.ensure_connection()
        major = connection.pg_version // 10000
    except Exception as exc:
        raise BackupError('Não foi possível conectar ao PostgreSQL. Confira o serviço e o arquivo .env.') from exc
    binary = _pg_dump_binary(major)
    db = settings.DATABASES['default']
    backup_dir = Path(settings.BASE_DIR) / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup_path = backup_dir / f'melo_joias_{stamp}_{uuid.uuid4().hex[:6]}.dump'
    command = [str(binary), '--no-password', '--format=custom', '--no-owner', '--no-privileges',
               '--host', str(db['HOST']), '--port', str(db['PORT']),
               '--username', str(db['USER']), '--dbname', str(db['NAME']),
               '--file', str(backup_path)]
    environment = os.environ.copy()
    environment['PGPASSWORD'] = str(db['PASSWORD'])
    environment['PGCONNECT_TIMEOUT'] = '10'
    complete = False
    try:
        result = subprocess.run(command, capture_output=True, env=environment,
                                timeout=300, check=False)
        if result.returncode or not backup_path.is_file() or backup_path.stat().st_size == 0:
            raise BackupError('O PostgreSQL não concluiu o backup. Confira conexão, permissões do usuário e espaço em disco.')
        complete = True
        return backup_path
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError('Não foi possível gerar o backup. Confira o pg_dump, espaço em disco e conexão ao banco.') from exc
    finally:
        environment.pop('PGPASSWORD', None)
        if not complete:
            backup_path.unlink(missing_ok=True)


def create_backup():
    """Return a complete .sqlite3 snapshot or PostgreSQL .dump under backups/."""
    from django.conf import settings
    from django.db import connection
    if connection.vendor == 'postgresql':
        return _create_postgresql_backup()
    if connection.vendor != 'sqlite':
        raise BackupError('Este tipo de banco não possui backup configurado.')
    source = Path(settings.DATABASES['default']['NAME'])
    if not source.is_file():
        raise BackupError('O banco local ainda não existe. Execute INSTALAR.bat primeiro.')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    label = 'demo' if settings.DEMO_MODE else 'melo_joias'
    destination = Path(settings.BASE_DIR) / 'backups' / f'{label}_{stamp}_{uuid.uuid4().hex[:6]}.sqlite3'
    completed = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True, timeout=20)) as source_db:
            with closing(sqlite3.connect(destination, timeout=20)) as target_db:
                source_db.backup(target_db, pages=128)
                if target_db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise BackupError('A verificação do backup falhou. O arquivo incompleto foi descartado.')
        completed = True
        return destination
    except (OSError, sqlite3.Error) as exc:
        raise BackupError('Não foi possível criar o backup local. Confira permissões e espaço em disco.') from exc
    finally:
        if not completed:
            destination.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    try:
        print(f'Backup criado: {create_backup()}')
    except BackupError as exc:
        print(f'Backup não realizado: {exc}', file=sys.stderr)
        raise SystemExit(1)
