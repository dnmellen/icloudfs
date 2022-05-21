from io import BytesIO
import os
import sys
import logging
import threading
from contextlib import closing
from fs import ResourceType, errors
from fs.base import FS
from fs.subfs import SubFS
from fs.mode import Mode
from fs.info import Info
from icloudpy import ICloudPyService
from icloudpy.services.drive import DriveNode
import requests

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class ICloudAPI:

    def __init__(self, email, password=None):
        self.api = ICloudPyService(email, password)
        self.api.drive.params["clientId"] = self.api.client_id

    def authenticate(self):
        if self.api.requires_2fa:
            print("Two-factor authentication required.")
            code = input("Enter the code you received of one of your approved devices: ")
            result = self.api.validate_2fa_code(code)
            print("Code validation result: %s" % result)

            if not result:
                print("Failed to verify security code")
                sys.exit(1)

            if not self.api.is_trusted_session:
                print("Session is not trusted. Requesting trust...")
                result = self.api.trust_session()
                print("Session trust result %s" % result)

                if not result:
                    print("Failed to request trust. You will likely be prompted for the code again in the coming weeks")
        elif self.api.requires_2sa:
            import click
            print("Two-step authentication required. Your trusted devices are:")

            devices = self.api.trusted_devices
            for i, device in enumerate(devices):
                print("  %s: %s" % (i, device.get('deviceName',
                    "SMS to %s" % device.get('phoneNumber'))))

            device = click.prompt('Which device would you like to use?', default=0)
            device = devices[device]
            if not self.api.send_verification_code(device):
                print("Failed to send verification code")
                sys.exit(1)

            code = click.prompt('Please enter validation code')
            if not self.api.validate_verification_code(device, code):
                print("Failed to verify verification code")
                sys.exit(1)
    
    def get_node(self, path: str) -> DriveNode:
        if path == '/':
            return self.api.drive.root
        else:
            node = self.api.drive.root
            try:
                for item in [p for p in path.split('/') if p]:
                    node = node[item]
            except KeyError as e:
                raise errors.ResourceNotFound(path=path, exc=e)
            return node

class ICloudFile(BytesIO):
    """
    BytesIO is stored in memory. Maybe we should change this to a temp file for large files?
    """
    def __init__(self, icloud: ICloudAPI, path, mode):

        self.icloud = icloud
        self.path = path
        self.mode = mode
        self._lock = threading.RLock()
        self.name = os.path.basename(self.path)

        initialData = None
        self.rev = None
        try:
            response = self.icloud.get_node(self.path).open()
            with closing(response):

                if self.mode.appending or (
                    self.mode.reading and not self.mode.truncate
                ):
                    initialData = response.content
        except errors.ResourceNotFound:
            if self.mode.reading:
                raise
        except requests.exceptions.HTTPError as err:
            log.warning(f"Could not open file {self.path}: {err}")

        super().__init__(initialData)
        if self.mode.appending and initialData is not None:
            # seek to the end
            self.seek(len(initialData))

    def __length_hint__(self):
        return self.getbuffer().nbytes

    def truncate(self, size=None):
        super().truncate(size)
        data_size = self.__length_hint__()
        if size and data_size < size:
            self.write(b"\0" * (size - data_size))
            self.seek(data_size)
        return size or data_size

    def close(self):

        if not self.mode.writing:
            super().close()
            return

        self.seek(0)
        self.icloud.get_node(self.path).upload(self)
        self.path = None
        self.mode = None
        self.icloud = None
        super().close()

    def write(self, data):
        if self.mode.writing == False:
            raise IOError("File is not in write mode")

        return super().write(data)

    def read(self, size=None):

        if self.mode.reading == False:
            raise IOError("File is not in read mode")

        return super().read(size)

    def readable(self):
        return self.mode.reading

    def writable(self):
        return self.mode.writing


class ICloudFS(FS):
    _meta = {
        "case_insensitive": False,
        "invalid_path_chars": "\0",
        "network": True,
        "read_only": False,
        "thread_safe": True,
        "unicode_paths": True,
        "virtual": False,
    }

    def __init__(self, email, password=None):
        super().__init__()
        self.icloud = ICloudAPI(email, password)

    def fix_path(self, path):

        if isinstance(path, bytes):
            try:
                path = path.decode("utf-8")
            except AttributeError:
                pass
        if not path.startswith("/"):
            path = "/" + path
        if path == "." or path == "./":
            path = "/"
        path = self.validatepath(path)

        return path

    def _info_from_node(self, node: DriveNode):

        rawInfo = {
            "basic": {
                "name": node.name,
                "is_dir": node.type == "folder",
            }
        }
        if node.type == "file":
            rawInfo.update(
                {"details": {"size": node.size, "type": ResourceType.file}}
            )
        else:
            rawInfo.update({"details": {"type": ResourceType.directory}})

        return Info(rawInfo)

    def getinfo(self, path, namespaces=None):
        _path = self.fix_path(path)
        if _path == "/":
            info_dict = {
                "basic": {"name": "", "is_dir": True},
                "details": {"type": ResourceType.directory},
            }
            return Info(info_dict)

        node = self.icloud.get_node(_path)
        return self._info_from_node(node)

    def exists(self, path):
        path = self.fix_path(path)
        try:
            self.icloud.get_node(path)
            return True
        except errors.ResourceNotFound as e:
            return False

    def listdir(self, path):
        _path = self.fix_path(path)

        if not self.exists(_path):
            raise errors.ResourceNotFound(path)

        meta = self.getinfo(_path)
        if meta.is_file:
            raise errors.DirectoryExpected(path)

        return self.icloud.get_node(_path).dir()

    def makedir(self, path, permissions=None, recreate=False):
        path = self.fix_path(path)
        if self.exists(path) and not recreate:
            raise errors.DirectoryExists(path)
        if path == "/":
            return SubFS(self, path)

        if self.exists(path):
            meta = self.getinfo(path)
            if meta.is_dir:
                if recreate == False:
                    raise errors.DirectoryExists(path)
                else:
                    return SubFS(self, path)
            if meta.is_file:
                raise errors.DirectoryExpected(path)

        parent_path, folder_name = os.path.split(path)
        if not self.exists(parent_path):

            raise errors.ResourceNotFound(parent_path)

        self.icloud.api.drive.create_folders(parent_path, folder_name)
        return SubFS(self, path)
    
    def openbin(self, path, mode="r", buffering=-1, **options):
        path = self.fix_path(path)
        _mode = Mode(mode)
        mode = _mode
        _mode.validate_bin()
        _path = self.validatepath(path)

        log.debug("openbin: %s, %s", path, mode)
        with self._lock:
            try:
                info = self.getinfo(_path)
            except errors.ResourceNotFound:
                if not _mode.create:
                    raise

                # Target doesn't exist and we're in create mode. Ensure the
                # parent is an existing directory before we try to create a file
                # in it.
                parent_path = self.get_parent(_path)

                # Can't use self.isdir() because it doesn't crash if the
                # directory doesn't exist, and we don't want to stat a file twice
                # if we can avoid it.
                info = self.getinfo(parent_path)
                if not info.is_dir:
                    raise errors.DirectoryExpected(parent_path)
                return ICloudFile(self.icloud, path, mode)

            # Target exists.
            if info.is_dir:
                raise errors.FileExpected(path)
            if _mode.exclusive:
                raise errors.FileExists(path)
            return ICloudFile(self.icloud, path, mode)

    def remove(self, path):
        _path = self.fix_path(path)

        info = self.getinfo(path)
        if info.is_dir:
            raise errors.FileExpected(path=path)
        self.icloud.get_node(_path).delete()

    def removedir(self, path):
        return self.remove(path)

    def setinfo(self, path, info):
        if not self.exists(path):
            raise errors.ResourceNotFound(path)