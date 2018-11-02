from dateutil import parser
from PyQt5 import uic, QtCore

from ..models import RepoModel, SnapshotModel, BackupProfileMixin
from .repo_add import AddRepoWindow, ExistingRepoWindow
from ..utils import pretty_bytes, get_private_keys, get_asset, keyring
from .ssh_add import SSHAddWindow

uifile = get_asset('UI/repotab.ui')
RepoUI, RepoBase = uic.loadUiType(uifile, from_imports=True, import_from='vorta.views')


class RepoTab(RepoBase, RepoUI, BackupProfileMixin):
    repo_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(parent)

        self.repoSelector.model().item(0).setEnabled(False)
        self.repoSelector.addItem('Initialize New Repository', 'init')
        self.repoSelector.addItem('Add Existing Repository', 'existing')
        for repo in RepoModel.select():
            self.repoSelector.addItem(repo.url, repo.id)

        if self.profile.repo:
            self.repoSelector.setCurrentIndex(self.repoSelector.findData(self.profile.repo.id))
        self.repoSelector.currentIndexChanged.connect(self.repo_select_action)

        self.repoCompression.addItem('LZ4 (default)', 'lz4')
        self.repoCompression.addItem('Zstandard (medium)', 'zstd')
        self.repoCompression.addItem('LZMA (high)', 'lzma,6')
        self.repoCompression.setCurrentIndex(self.repoCompression.findData(self.profile.compression))
        self.repoCompression.currentIndexChanged.connect(self.compression_select_action)

        self.init_ssh()

        if self.profile.repo:
            self.init_repo_stats()

    def init_repo_stats(self):
        repo = self.profile.repo
        self.sizeCompressed.setText(pretty_bytes(repo.unique_csize))
        self.sizeDeduplicated.setText(pretty_bytes(repo.unique_size))
        self.sizeOriginal.setText(pretty_bytes(repo.total_size))
        self.repoEncryption.setText(str(repo.encryption))
        self.repo_changed.emit(repo.id)

    def init_ssh(self):
        keys = get_private_keys()
        for key in keys:
            self.sshComboBox.addItem(f'{key["filename"]} ({key["format"]}:{key["fingerprint"]})', key['filename'])
        self.sshComboBox.currentIndexChanged.connect(self.ssh_select_action)

    def ssh_select_action(self, index):
        if index == 1:
            ssh_add_window = SSHAddWindow()
            ssh_add_window.setParent(self, QtCore.Qt.Sheet)
            ssh_add_window.show()
            if ssh_add_window.exec_():
                self.init_ssh()
        else:
            profile = self.profile
            profile.ssh_key = self.sshComboBox.itemData(index)
            profile.save()


    def compression_select_action(self, index):
        profile = self.profile
        profile.compression = self.repoCompression.currentData()
        profile.save()

    def repo_select_action(self, index):
        if index <= 2:
            if index == 1:
                window = AddRepoWindow()
            else:
                window = ExistingRepoWindow()
            window.setParent(self, QtCore.Qt.Sheet)
            window.show()
            if window.exec_():
                self.process_new_repo(window.result)
        else:
            profile = self.profile
            profile.repo = self.repoSelector.currentData()
            profile.save()
            self.init_repo_stats()

    def process_new_repo(self, result):
        if result['returncode'] == 0:
            new_repo, _ = RepoModel.get_or_create(
                url=result['params']['repo_url'],
                defaults={
                    'encryption': result['params'].get('encryption', 'none')
                }
            )
            if 'cache' in result['data']:
                stats = result['data']['cache']['stats']
                new_repo.total_size = stats['total_size']
                new_repo.unique_csize = stats['unique_csize']
                new_repo.unique_size = stats['unique_size']
                new_repo.total_unique_chunks = stats['total_unique_chunks']
            if 'encryption' in result['data']:
                new_repo.encryption = result['data']['encryption']['mode']
            if new_repo.encryption is not None and new_repo.encryption != 'none':
                keyring.set_password("vorta-repo", new_repo.url, result['params']['password'])


            new_repo.save()
            profile = self.profile
            profile.repo = new_repo.id
            profile.save()

            if 'archives' in result['data'].keys():
                for snapshot in result['data']['archives']:
                    new_snapshot, _ = SnapshotModel.get_or_create(
                        snapshot_id=snapshot['id'],
                        defaults={
                            'repo': new_repo.id,
                            'name': snapshot['name'],
                            'time': parser.parse(snapshot['time'])
                        }
                    )
                    new_snapshot.save()
            self.repoSelector.addItem(new_repo.url, new_repo.id)
            self.repoSelector.setCurrentIndex(self.repoSelector.count()-1)
            self.repo_changed.emit(self.profile.repo.id)
