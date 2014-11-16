import logging
import os

from cffi import FFI

from . import errors

ffi = FFI()
with open(os.path.join(os.path.dirname(__file__), 'gphoto2.cdef')) as fp:
    ffi.cdef(fp.read())

_lib = ffi.verify("""
#include "gphoto2/gphoto2-context.h"
#include "gphoto2/gphoto2-camera.h"
#include <time.h>
""", libraries=["gphoto2"])

#: Mapping from libgphoto2 logging levels to Python logging levels
LOG_LEVELS = {
    _lib.GP_LOG_ERROR:   logging.ERROR,
    _lib.GP_LOG_VERBOSE: logging.INFO,
    _lib.GP_LOG_DEBUG:   logging.DEBUG
}

#: Root logger that all other libgphoto2 loggers are children of
_root_logger = logging.getLogger("libgphoto2")


@ffi.callback("void(GPLogLevel, const char*, const char*, void*)")
def logging_callback(level, domain, message, data):
    """ Callback that outputs libgphoto2's logging message via Python's
        standard logging facilities.

    :param level:   libgphoto2 logging level
    :param domain:  component the message originates from
    :param message: logging message
    :param data:    Other data in the logging record (unused)
    """
    domain = ffi.string(domain)
    message = ffi.string(message)
    logger = _root_logger.getChild(domain)

    if level not in LOG_LEVELS:
        return
    logger.log(LOG_LEVELS[level], message)

# Register our logging callback
_lib.gp_log_add_func(_lib.GP_LOG_DEBUG, logging_callback, ffi.NULL)


def check_error(rval):
    """ Check a return value for a libgphoto2 error. """
    if rval < 0:
        raise errors.error_from_code(rval)
    else:
        return rval


class LibraryWrapper(object):
    NO_ERROR_CHECK = (
        "gp_log_add_func",
        "gp_context_new",
        "gp_list_count",
        "gp_result_as_string",
    )

    def __init__(self, to_wrap):
        """ Wrapper around our libgphoto2 FFI object.

        Wraps functions inside an anonymous function that checks the inner
        function's return code for libgphoto2 errors and throws a
        :py:class:`gphoto2.errors.GPhoto2Error` if needed.

        :param to_wrap:     FFI library to wrap
        """
        self._wrapped = to_wrap

    def __getattribute__(self, name):
        # Use the parent class' implementation to avoid infinite recursion
        val = getattr(object.__getattribute__(self, '_wrapped'), name)
        blacklist = object.__getattribute__(self, 'NO_ERROR_CHECK')
        if not isinstance(val, int) and name not in blacklist:
            return lambda *a, **kw: check_error(val(*a, **kw))
        else:
            return val

#: The wrapped library
lib = LibraryWrapper(_lib)

#: Mapping from libgphoto2 file type constants to human-readable strings
FILE_TYPES = {
    'normal': _lib.GP_FILE_TYPE_NORMAL,
    'exif': _lib.GP_FILE_TYPE_EXIF,
    'metadata': _lib.GP_FILE_TYPE_METADATA,
    'preview': _lib.GP_FILE_TYPE_PREVIEW,
    'raw': _lib.GP_FILE_TYPE_RAW,
    'audio': _lib.GP_FILE_TYPE_AUDIO
}

#: Mapping from libgphoto2 types to their appropriate constructor functions
CONSTRUCTORS = {
    "Camera":       lib.gp_camera_new,
    "GPPortInfo":   lib.gp_port_info_new,
    "CameraList":   lib.gp_list_new,
    "CameraAbilitiesList": lib.gp_abilities_list_new,
    "GPPortInfoList": lib.gp_port_info_list_new,
}

#: Mapping from libgphoto2 widget type constants to human-readable strings
WIDGET_TYPES = {
    lib.GP_WIDGET_MENU:     "selection",
    lib.GP_WIDGET_RADIO:    "selection",
    lib.GP_WIDGET_TEXT:     "text",
    lib.GP_WIDGET_RANGE:    "range",
    lib.GP_WIDGET_DATE:     "date",
    lib.GP_WIDGET_TOGGLE:   "toggle",
    lib.GP_WIDGET_WINDOW:   "window",
    lib.GP_WIDGET_SECTION:  "section",
}


def get_string(cfunc, *args):
    """ Call a C function and return its return value as a Python string.

    :param cfunc:   C function to call
    :param args:    Arguments to call function with
    :rtype:         str
    """
    cstr = get_ctype("const char**", cfunc, *args)
    return ffi.string(cstr) if cstr else None


def get_ctype(rtype, cfunc, *args):
    """ Call a C function that takes a pointer as its last argument and
        return the C object that it contains after the function has finished.

    :param rtype:   C data type is filled by the function
    :param cfunc:   C function to call
    :param args:    Arguments to call function with
    :return:        A pointer to the specified data type
    """
    val_p = ffi.new(rtype)
    args = args + (val_p,)
    cfunc(*args)
    return val_p[0]


def new_gp_object(typename):
    """ Create an indirect pointer to a GPhoto2 type, call its matching
        constructor function and return the pointer to it.

    :param typename:    Name of the type to create.
    :return:            A pointer to the specified data type.
    """
    obj_p = ffi.new("{0}**".format(typename))
    CONSTRUCTORS[typename](obj_p)
    return obj_p[0]
