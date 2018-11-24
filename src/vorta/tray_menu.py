from PyQt5.QtWidgets import QMenu, QSystemTrayIcon
from PyQt5.QtGui import QIcon

from .utils import get_asset
from .borg.borg_thread import BorgThread
from .models import BackupProfileModel


class TrayMenu(QSystemTrayIcon):
    def __init__(self, parent=None):
        icon = QIcon(get_asset('icons/hdd-o.png'))
        QSystemTrayIcon.__init__(self, icon, parent)
        self.app = parent
        menu = QMenu()

        self.status = menu.addAction(self.app.scheduler.next_job)
        self.status.setEnabled(False)

        self.profile_menu = menu.addMenu('Backup Now')

        self.cancel_action = menu.addAction("Cancel Backup")
        self.cancel_action.triggered.connect(self.app.backup_cancelled_event.emit)

        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.app.open_main_window_action)

        menu.addSeparator()

        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.app.quit)

        self.on_user_click()
        self.activated.connect(self.on_user_click)

        self.setContextMenu(menu)
        self.setVisible(True)
        self.show()

    def on_user_click(self, reason=0):
        """Adjust labels to reflect current status."""
        # BUG on ubuntu 18.04 (standard edition with gnome):
        # a single LMB click on the tray icon does not fire the "activated" signal (documented reason 3).
        # working: double LMB click (reason reported 3, should be 2), MMB click (reason 4)
        if BorgThread.is_running():
            self.status.setText('Backup in Progress')
            self.profile_menu.setEnabled(False)
            self.cancel_action.setVisible(True)
        else:
            self.status.setText(f'Next Task: {self.app.scheduler.next_job}')
            self.profile_menu.setEnabled(True)
            self.cancel_action.setVisible(False)

        self.profile_menu.clear()
        for profile in BackupProfileModel.select():
            new_item = self.profile_menu.addAction(profile.name)
            new_item.setData(profile.id)
            new_item.triggered.connect(lambda profile_id=profile.id: self.app.create_backup_action(profile_id))
