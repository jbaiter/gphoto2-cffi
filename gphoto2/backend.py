import binascii
import logging
import os
import sys
import threading

from cffi import FFI
from cffi.verifier import Verifier
from enum import IntEnum

from . import errors

with open(os.path.join(os.path.dirname(__file__), 'gphoto2.cdef')) as fp:
    CDEF = fp.read()

SOURCE = """
#include "gphoto2/gphoto2-context.h"
#include "gphoto2/gphoto2-camera.h"
#include <time.h>
"""


def _create_modulename(cdef_sources, source, sys_version):
    """ This is the same as CFFI's create modulename except we don't include
        the CFFI version.
    """
    key = '\x00'.join([sys_version[:3], source, cdef_sources])
    key = key.encode()
    k1 = hex(binascii.crc32(key[0::2]) & 0xffffffff)
    k1 = k1.lstrip('0x').rstrip('L')
    k2 = hex(binascii.crc32(key[1::2]) & 0xffffffff)
    k2 = k2.lstrip('0').rstrip('L')
    return '_gphoto2_cffi_{0}{1}'.format(k1, k2)


def _compile_module(*args, **kwargs):
    raise RuntimeError(
        "Attempted implicit compile of a cffi module. All cffi modules should "
        "be pre-compiled at installation time.")

ffi = FFI()
ffi.cdef(CDEF)
ffi.verifier = Verifier(
    ffi, SOURCE,
    modulename=_create_modulename(CDEF, SOURCE, sys.version),
    libraries=['gphoto2'])

# Patch the Verifier() instance to prevent CFFI from compiling the module
ffi.verifier.compile_module = _compile_module
ffi.verifier._compile_module = _compile_module


class _globals(object):
    def __init__(self, lib):
        self._lib = lib

    @property
    def FILE_TYPES(self):
        """ Mapping from libgphoto2 file type constants to human-readable
            strings.
        """
        return {
            'normal': self._lib.GP_FILE_TYPE_NORMAL,
            'exif': self._lib.GP_FILE_TYPE_EXIF,
            'metadata': self._lib.GP_FILE_TYPE_METADATA,
            'preview': self._lib.GP_FILE_TYPE_PREVIEW,
            'raw': self._lib.GP_FILE_TYPE_RAW,
            'audio': self._lib.GP_FILE_TYPE_AUDIO
        }

    @property
    def CONSTRUCTORS(self):
        """ Mapping from libgphoto2 types to their appropriate constructor
            functions.
        """
        return {
            "Camera":       self._lib.gp_camera_new,
            "GPPortInfo":   self._lib.gp_port_info_new,
            "CameraList":   self._lib.gp_list_new,
            "CameraAbilitiesList": self._lib.gp_abilities_list_new,
            "GPPortInfoList": self._lib.gp_port_info_list_new,
        }

    @property
    def WIDGET_TYPES(self):
        """ Mapping from libgphoto2 widget type constants to human-readable
            strings
        """
        return {
            self._lib.GP_WIDGET_MENU:     "selection",
            self._lib.GP_WIDGET_RADIO:    "selection",
            self._lib.GP_WIDGET_TEXT:     "text",
            self._lib.GP_WIDGET_RANGE:    "range",
            self._lib.GP_WIDGET_DATE:     "date",
            self._lib.GP_WIDGET_TOGGLE:   "toggle",
            self._lib.GP_WIDGET_WINDOW:   "window",
            self._lib.GP_WIDGET_SECTION:  "section",
        }

    @property
    def LOG_LEVELS(self):
        """ Mapping from libgphoto2 logging levels to Python logging levels.
        """
        return {
            self._lib.GP_LOG_ERROR:   logging.ERROR,
            self._lib.GP_LOG_VERBOSE: logging.INFO,
            self._lib.GP_LOG_DEBUG:   logging.DEBUG
        }

    @property
    def FILE_OPS(self):
        return IntEnum(b'FileOperations', {
            'remove': lib.GP_FILE_OPERATION_DELETE,
            'extract_preview': lib.GP_FILE_OPERATION_PREVIEW,
            'extract_raw': lib.GP_FILE_OPERATION_RAW,
            'extract_audio': lib.GP_FILE_OPERATION_AUDIO,
            'extract_exif': lib.GP_FILE_OPERATION_EXIF})

    @property
    def CAM_OPS(self):
        return IntEnum(b'CameraOperations', {
            'capture_image': lib.GP_OPERATION_CAPTURE_IMAGE,
            'capture_video': lib.GP_OPERATION_CAPTURE_VIDEO,
            'capture_audio': lib.GP_OPERATION_CAPTURE_AUDIO,
            'capture_preview': lib.GP_OPERATION_CAPTURE_PREVIEW,
            'update_config': lib.GP_OPERATION_CONFIG,
            'trigger_capture': lib.GP_OPERATION_TRIGGER_CAPTURE})

    @property
    def DIR_OPS(self):
        return IntEnum(b'DirectoryOperations', {
            'remove': lib.GP_FOLDER_OPERATION_REMOVE_DIR,
            'create': lib.GP_FOLDER_OPERATION_MAKE_DIR,
            'delete_all': lib.GP_FOLDER_OPERATION_DELETE_ALL,
            'upload': lib.GP_FOLDER_OPERATION_PUT_FILE})


class LibraryWrapper(object):
    NO_ERROR_CHECK = (
        "gp_log_add_func",
        "gp_context_new",
        "gp_list_count",
        "gp_result_as_string",
    )
    #: Root logger that all other libgphoto2 loggers are children of
    _logger = logging.getLogger("libgphoto2")

    def __init__(self, ffi):
        """ Wrapper around our FFI object that performs error checking
            and lazy-loads the C library.

        Wraps functions inside an anonymous function that checks the inner
        function's return code for libgphoto2 errors and throws a
        :py:class:`gphoto2.errors.GPhoto2Error` if needed.

        :param to_wrap:     FFI library to wrap
        """
        def _logging_callback(level, domain, message, data):
            """ Callback that outputs libgphoto2's logging message via
                Python's standard logging facilities.

            :param level:   libgphoto2 logging level
            :param domain:  component the message originates from
            :param message: logging message
            :param data:    Other data in the logging record (unused)
            """
            domain = ffi.string(domain).decode()
            message = ffi.string(message).decode()
            logger = LibraryWrapper._logger.getChild(domain)

            if level not in globals.LOG_LEVELS:
                return
            logger.log(globals.LOG_LEVELS[level], message)

        self._ffi = ffi
        self._lib = None
        self._lock = threading.Lock()
        self._logging_cb = self._ffi.callback(
            "void(GPLogLevel, const char*, const char*, void*)",
            _logging_callback)

    @staticmethod
    def _check_error(rval):
        """ Check a return value for a libgphoto2 error. """
        if rval < 0:
            raise errors.error_from_code(rval)
        else:
            return rval

    def _load_library(self):
        """ Lazy-load the library. """
        with self._lock:
            if self._lib is None:
                self._lib = self._ffi.verifier.load_library()
                # Register our logging callback
                self._lib.gp_log_add_func(
                    self._lib.GP_LOG_DEBUG, self._logging_cb, self._ffi.NULL)

    def __getattr__(self, name):
        if self._lib is None:
            self._load_library()
        val = getattr(self._lib, name)
        if not isinstance(val, int) and name not in self.NO_ERROR_CHECK:
            return lambda *a, **kw: self._check_error(val(*a, **kw))
        else:
            return val


#: The wrapped library
lib = LibraryWrapper(ffi)

#: Namespace for lazy-loaded global variables
globals = _globals(lib)
