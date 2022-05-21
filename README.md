# icloudfs
iCloud file system implementation using pyfilesystem2

I always wanted an easy access to my icloud files from Linux. This filesystem
is still under development and should not be used in a production environment.
At this stage I can safely read files but not writing files. Use This
software at your own risk.

## Quickstart

```bash
pip install fusefs
pip install fs-icloud
```

## Storing iCloud credentials in system keychain

```bash
icloud --username=john@apple.com
```

## Mounting icloudfs

```bash
fusefs icloud://john%40apple.com:@/ /tmp/icloud
```

## TODO

- [x] List files and directories
- [x] Read files
- [ ] Write files

## Credits

- [icloudpy](https://github.com/mandarons/icloudpy): I decided to start this project when I found this Python wrapper to access iCloud.
- [PyFilesystem2](https://docs.pyfilesystem.org/en/latest/)
