import os
import sys
from setuptools import setup


REQUIRES = ['cffi >= 1.4']

if sys.version_info < (3, 4):
    REQUIRES.append('enum34 >= 1.0.3')


if os.path.exists('README.rst'):
    if sys.version_info > (3,):
        description_long = open('README.rst', encoding="utf-8").read()
    else:
        description_long = open('README.rst').read()
else:
    description_long = """
Python bindings for libgphoto2 with an interface that strives to be idiomatic.
In contrast to other bindings for Python, gphoto2-cffi hides most of the
lower-level abstractions and reduces the API surface while still offering
access to most of the library's features.
"""

setup(
    name='gphoto2-cffi',
    version="0.4.1",
    description=("libgphoto2 bindings with an interface that strives to be "
                 "idiomatic"),
    long_description=description_long,
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5'],
    author="Johannes Baiter",
    url="http://github.com/jbaiter/gphoto2-cffi.git",
    author_email="johannes.baiter@gmail.com",
    license='LGPLv3',
    packages=['gphoto2cffi'],
    include_package_data=True,
    setup_requires=['cffi >= 1.4'],
    cffi_modules=['gphoto2cffi/backend_build.py:ffi'],
    install_requires=REQUIRES,
    zip_safe=False,
)
