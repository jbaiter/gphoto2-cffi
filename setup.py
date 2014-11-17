import os
import sys
from distutils.command.build import build
from setuptools import setup
from setuptools.command.install import install


def get_ext_modules():
    import gphoto2.backend
    return [gphoto2.backend.ffi.verifier.get_extension()]


class CFFIBuild(build):
    def finalize_options(self):
        self.distribution.ext_modules = get_ext_modules()
        build.finalize_options(self)


class CFFIInstall(install):
    def finalize_options(self):
        self.distribution.ext_modules = get_ext_modules()
        install.finalize_options(self)


if os.path.exists('README.rst'):
    if sys.version_info > (3,):
        description_long = open('README.rst', encoding="utf-8").read()
    else:
        description_long = open('README.rst').read()
else:
    description_long = """
Python bindings for libgphoto2 with an idiomatic interface and PyPy support,
using cffi. In contrast to other bindings for Python, gphoto2-cffi hides most
of the lower-level abstractions and allows you to work with an elegent API that
exposes most of the library's features in an idiomatic interface.
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
    package_data={
        'gphoto2': ['*.cdef']
    },
    install_requires=[
        'cffi >= 0.8',
        'enum34 >= 1.0.3'
    ],
    setup_requires=['cffi >= 0.8'],
    cmdclass={
        "build": CFFIBuild,
        "install": CFFIInstall,
    },
    zip_safe=False,
)
