import os
import sys
from setuptools import setup

import gphoto2.backend

if os.path.exists('README.rst'):
    if sys.version_info > (3,):
        description_long = open('README.rst', encoding="utf-8").read()
    else:
        description_long = open('README.rst').read()
else:
    description_long = """
Python bindings for `libgphoto2`_ with an idiomatic interface and `PyPy`_
support, using `cffi`_. In contrast to other bindings for Python, gphoto2-cffi
hides most of the lower-level abstractions and allows you to work with an
elegent API that exposes most of the library's features in an idiomatic
interface.
"""

setup(
    name='gphoto2-cffi',
    version="0.1",
    description=("Bindings for libgphoto2 with an idiomatic API"),
    description_long=description_long,
    author="Johannes Baiter",
    url="http://github.com/jbaiter/gphoto2-cffi.git",
    author_email="johannes.baiter@gmail.com",
    license='LGPLv3',
    packages=['gphoto2'],
    zip_safe=False,
    ext_modules=[gphoto2.backend.ffi.verifier.get_extension()],
    install_requires=['cffi >= 0.8'],
    setup_requires=['cffi >= 0.8']
)
