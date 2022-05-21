import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='fs-icloud',  # Name in PyPi
    author="Diego Navarro Mellen",
    author_email="dnmellen@gmail.com",
    description="An icloud filesystem for pyfilesystem2!",
    long_description=read('README.md'),
    url="https://github.com/dnmellen/icloudfs",
    install_requires=[
        "fs>=2.0.5",
        "icloudpy",
    ],
    entry_points = {
        'fs.opener': [
            'icloud = icloudfs.opener:ICloudOpener',
        ]
    },
    license="MIT",
    packages=['icloudfs'],
    version="1.0.2",
)
