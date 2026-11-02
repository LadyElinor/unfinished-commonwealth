"""O1 operational prerequisite inspection and explicit offline recovery tools."""
import argparse
import sqlite3
import sys
from ..engine import canonical
from . import VERSION
from .config import BLOCKERS, inspect, load
from .backup import backup_database, restore_database


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('readiness')
    sub.add_parser('preflight').add_argument('config')
    sub.add_parser('selfcheck')
    for name in ('backup', 'restore'):
        item = sub.add_parser(name)
        item.add_argument('source')
        item.add_argument('new_destination')
    args = parser.parse_args(argv)
    try:
        if args.command == 'readiness':
            result = {'version': VERSION, 'production_ready': False, 'blockers': list(BLOCKERS), 'external_authority': 'NONE'}
            code = 2
        elif args.command == 'preflight':
            result = inspect(load(args.config))
            code = 0 if result['operational_admission'] else 2
        elif args.command == 'selfcheck':
            from .selfcheck import run
            result, code = run(), 0
        else:
            operation = backup_database if args.command == 'backup' else restore_database
            result, code = operation(args.source,args.new_destination), 0
        print(canonical(result))
        return code
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print(canonical({'error':'Operational tool refused; inspect local configuration and recovery runbook.'}),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
