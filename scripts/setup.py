"""Prepare the local database. Real data and examples live in separate files."""
import argparse
import os
from pathlib import Path
import shutil
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)


def check_dedicated_database():
    from django.apps import apps
    from django.db import connection
    expected = {model._meta.db_table for model in apps.get_models(include_auto_created=True)}
    expected.add('django_migrations')
    existing = set(connection.introspection.table_names())
    unexpected = existing - expected
    if unexpected:
        raise RuntimeError('O banco selecionado contém tabelas de outro sistema. '
                           'Configure um banco dedicado vazio para não misturar seus dados.')


def main():
    parser = argparse.ArgumentParser(description='Prepara o banco local do Melo Joias.')
    parser.add_argument('--no-input', action='store_true', help='Compatibilidade: a instalação não faz perguntas.')
    parser.add_argument('--demo', action='store_true', help='Prepara exemplos em um banco separado de demonstração.')
    args = parser.parse_args()
    try:
        if not (BASE_DIR / '.env').exists():
            shutil.copyfile(BASE_DIR / '.env.example', BASE_DIR / '.env')
        if args.demo:
            os.environ['MELO_DEMO_MODE'] = '1'
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()
        from django.conf import settings
        from django.core.management import call_command
        from django.db import connection
        db = settings.DATABASES['default']
        if args.demo and connection.vendor == 'postgresql' and db['NAME'] != 'melo_joias_demo':
            raise RuntimeError('Para exemplos no PostgreSQL configure o banco separado DB_NAME=melo_joias_demo.')
        try:
            connection.ensure_connection()
        except Exception as exc:
            raise RuntimeError('Não foi possível abrir o banco. Para SQLite confira permissões da pasta data; '
                               'para PostgreSQL crie um banco dedicado vazio e confira o .env.') from exc
        check_dedicated_database()
        call_command('migrate', interactive=False)
        call_command('collectstatic', interactive=False, verbosity=0)
        if args.demo:
            from django.apps import apps
            if any(model.objects.exists() for model in apps.get_app_config('core').get_models()):
                print('A demonstração já contém cadastros; seus exemplos foram preservados.')
            else:
                call_command('seed_demo')
        print('Tabelas e arquivos locais prontos. Execute INICIAR.bat.')
        return 0
    except (RuntimeError, EOFError, KeyboardInterrupt) as exc:
        print(f'Instalação não concluída: {exc}', file=sys.stderr)
        return 1
    except Exception:
        print('A instalação encontrou um erro ao preparar as tabelas. Confira permissões e espaço em disco. '
              'Para diagnóstico: .venv\\Scripts\\python.exe manage.py migrate',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
