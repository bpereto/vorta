import sys
import os
import peewee

from vorta.models import init_db, SettingsModel
from vorta.application import VortaApp
from vorta.config import SETTINGS_DIR
from vorta.updater import get_updater
import vorta.sentry
import vorta.log
from vorta.utils import parse_args


def main():
    args = parse_args()

    frozen_binary = getattr(sys, 'frozen', False)
    # Don't fork if user specifies it or when running from onedir app bundle on macOS.
    if (hasattr(args, 'foreground') and args.foreground) or (frozen_binary and sys.platform == 'darwin'):
        pass
    else:
        print('Forking to background (see system tray).')
        if os.fork():
            sys.exit()

    # Init database
    sqlite_db = peewee.SqliteDatabase(os.path.join(SETTINGS_DIR, 'settings.db'))
    init_db(sqlite_db)

    # Send crashes to Sentry.
    if SettingsModel.get(key='send_sentry_reports').value:
        vorta.sentry.init()

    app = VortaApp(sys.argv, single_app=True)
    app.updater = get_updater()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
