from fs.opener import Opener


__all__ = ["ICloudOpener"]


class ICloudOpener(Opener):
    protocols = ["icloud"]

    @staticmethod
    def open_fs(fs_url, parse_result, writeable, create, cwd):
        from .icloudfs import ICloudFS
        directory = parse_result.resource or "/"
        fs = ICloudFS(email=parse_result.username)

        if directory:
            return fs.opendir(directory)
        else:
            return fs
