from setuptools import find_packages
from setuptools import setup

setup(
    name='msg_folder',
    version='0.0.0',
    packages=find_packages(
        include=('msg_folder', 'msg_folder.*')),
)
