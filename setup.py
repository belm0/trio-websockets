#!/usr/bin/env python

import pathlib
import sys

import setuptools


root_dir = pathlib.Path(__file__).parent

description = "An implementation of the WebSocket Protocol (RFC 6455 & 7692)"

# When dropping Python < 3.5, change to:
# long_description = (root_dir / 'README.rst').read_text(encoding='utf-8')
with (root_dir / 'README.rst').open(encoding='utf-8') as f:
    long_description = f.read()

# When dropping Python < 3.5, change to:
# exec((root_dir / 'websockets' / 'version.py').read_text(encoding='utf-8'))
with (root_dir / 'trio_websockets' / 'version.py').open(encoding='utf-8') as f:
    exec(f.read())

py_version = sys.version_info[:2]

if py_version < (3, 5):
    raise Exception("websockets requires Python >= 3.5.")

packages = ['trio_websockets']

if py_version >= (3, 5):
    packages.append('trio_websockets/py35')

if py_version >= (3, 6):
    packages.append('trio_websockets/py36')


setuptools.setup(
    name='trio-websockets',
    version=version,
    description=description,
    long_description=long_description,
    url='https://github.com/miracle2k/trio-websockets',
    author='Michael Elsdorfer',
    author_email='michael@elsdorfer.com',
    license='BSD',
    install_requires=['wsproto'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    packages=packages,
    include_package_data=True,
    zip_safe=True,
    python_requires='>=3.4',
)
