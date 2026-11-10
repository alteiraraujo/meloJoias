"""Package portable sources only; never bundle credentials or local records."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import uuid
import zipfile

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_FILES = {
    'README.md', '.env.example', '.gitignore', 'manage.py',
    'requirements.txt', 'requirements-postgresql.txt',
    'INSTALAR.bat', 'INICIAR.bat', 'DEMONSTRACAO.bat',
}
SOURCE_DIRS = {'config', 'core', 'docs', 'scripts', 'static', 'templates'}
EXCLUDED_DIRS = {'.venv', '.git', '__pycache__', 'data', 'backups', 'staticfiles', 'dist', '.pytest_cache'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.log', '.sqlite3', '.sqlite', '.db', '.dump', '.zip', '.tmp'}


def source_files():
    for name in sorted(ROOT_FILES):
        path = BASE_DIR / name
        if path.is_file() and not path.is_symlink():
            yield path
    for name in sorted(SOURCE_DIRS):
        directory = BASE_DIR / name
        if not directory.is_dir() or directory.is_symlink():
            continue
        for current, folders, files in os.walk(directory, followlinks=False):
            folders[:] = sorted(folder for folder in folders if folder not in EXCLUDED_DIRS
                                and not (Path(current) / folder).is_symlink())
            for filename in sorted(files):
                path = Path(current) / filename
                if path.is_symlink() or path.suffix.lower() in EXCLUDED_SUFFIXES:
                    continue
                if filename == '.env' or filename.startswith('.env.'):
                    continue
                yield path


def create_package():
    output_dir = BASE_DIR / 'dist'
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = output_dir / f'melo-joias-prototipo_{stamp}_{uuid.uuid4().hex[:6]}.zip'
    temporary = output.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for source in source_files():
                relative = source.relative_to(BASE_DIR).as_posix()
                archive.write(source, arcname=f'melo-joias/{relative}')
        temporary.replace(output)
        return output
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gera um ZIP das fontes, sem bancos ou credenciais.')
    parser.add_argument('--list', action='store_true', help='Mostra os arquivos sem criar ZIP.')
    args = parser.parse_args()
    if args.list:
        for path in source_files():
            print(path.relative_to(BASE_DIR).as_posix())
    else:
        print(f'Pacote criado: {create_package()}')
