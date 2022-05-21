# icloudfs
iCloud file system implementation using pyfilesystem2


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
