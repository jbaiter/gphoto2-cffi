import os
import sys
from distutils.command.build import build
from setuptools import setup
from setuptools.command.install import install
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
        def is_pure(self):
                    return False


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

REQUIRES = ['cffi >= 0.8']

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
    version="0.2",
    description=("libgphoto2 bindings with an interface that strives to be "
                 "idiomatic"),
    description_long=description_long,
    author="Johannes Baiter",
    url="http://github.com/jbaiter/gphoto2-cffi.git",
    author_email="johannes.baiter@gmail.com",
    license='LGPLv3',
    packages=['gphoto2'],
    include_package_data=True,
    distclass=BinaryDistribution,
    setup_requires=['cffi'],
    install_requires=REQUIRES,
    cmdclass={
        "build": CFFIBuild,
        "install": CFFIInstall,
    },
    zip_safe=False,
)
