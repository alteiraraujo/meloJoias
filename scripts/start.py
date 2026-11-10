"""Serve the application on loopback using Waitress."""
import argparse
import os
from pathlib import Path
import sys
import threading
import webbrowser

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def main():
    parser = argparse.ArgumentParser(description='Inicia o Melo Joias neste computador.')
    parser.add_argument('--no-browser', action='store_true', help='Não abre o navegador automaticamente.')
    args = parser.parse_args()
    import django
    django.setup()
    from django.db import connection
    from django.core.wsgi import get_wsgi_application
    from waitress import serve

    try:
        connection.ensure_connection()
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            print('O banco precisa ser preparado. Execute INSTALAR.bat antes de iniciar.', file=sys.stderr)
            return 1
    except Exception:
        print('Não foi possível abrir o banco local. Execute INSTALAR.bat para preparar o sistema.\n'
              'Se escolheu PostgreSQL, confira os dados de conexão no .env.', file=sys.stderr)
        return 1
    finally:
        connection.close()
    try:
        port = int(os.environ.get('MELO_PORT', '8791'))
        if not 1024 <= port <= 65535:
            raise ValueError
    except ValueError:
        print('MELO_PORT deve ser uma porta entre 1024 e 65535.', file=sys.stderr)
        return 1
    url = f'http://127.0.0.1:{port}'
    from django.conf import settings
    mode = 'Demonstração — dados fictícios' if settings.DEMO_MODE else 'Seus cadastros'
    print(f'Melo Joias — {mode}\n{url}\nMantenha esta janela aberta. Pressione Ctrl+C para encerrar.', flush=True)
    if not args.no_browser:
        opener = threading.Timer(1.5, webbrowser.open, args=(url,))
        opener.daemon = True
        opener.start()
    try:
        serve(get_wsgi_application(), host='127.0.0.1', port=port, threads=4)
    except OSError:
        print(f'Não foi possível abrir a porta {port}. O sistema pode já estar aberto.\n'
              'Confira o endereço acima ou altere MELO_PORT no .env.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
