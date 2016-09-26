import logging

from enum import IntEnum

from . import errors
from ._backend import ffi, lib as _lib


#: Root logger that all other libgphoto2 loggers are children of
LOGGER = logging.getLogger("libgphoto2")


#: Mapping from libgphoto2 file type constants to human-readable strings.
FILE_TYPES = {
    'normal': _lib.GP_FILE_TYPE_NORMAL,
    'exif': _lib.GP_FILE_TYPE_EXIF,
    'metadata': _lib.GP_FILE_TYPE_METADATA,
    'preview': _lib.GP_FILE_TYPE_PREVIEW,
    'raw': _lib.GP_FILE_TYPE_RAW,
    'audio': _lib.GP_FILE_TYPE_AUDIO}


#: Mapping from libgphoto2 types to their appropriate constructor functions.
CONSTRUCTORS = {
    "Camera":       _lib.gp_camera_new,
    "GPPortInfo":   _lib.gp_port_info_new,
    "CameraList":   _lib.gp_list_new,
    "CameraAbilitiesList": _lib.gp_abilities_list_new,
    "GPPortInfoList": _lib.gp_port_info_list_new}


#: Mapping from libgphoto2 widget type constants to human-readable strings
WIDGET_TYPES = {
    _lib.GP_WIDGET_MENU:     "selection",
    _lib.GP_WIDGET_RADIO:    "selection",
    _lib.GP_WIDGET_TEXT:     "text",
    _lib.GP_WIDGET_RANGE:    "range",
    _lib.GP_WIDGET_DATE:     "date",
    _lib.GP_WIDGET_TOGGLE:   "toggle",
    _lib.GP_WIDGET_WINDOW:   "window",
    _lib.GP_WIDGET_SECTION:  "section"}


#: Mapping from libgphoto2 logging levels to Python logging levels.
LOG_LEVELS = {
    _lib.GP_LOG_ERROR:   logging.ERROR,
    _lib.GP_LOG_VERBOSE: logging.INFO,
    _lib.GP_LOG_DEBUG:   logging.DEBUG}


FILE_OPS = IntEnum('FileOperations', {
    'remove': _lib.GP_FILE_OPERATION_DELETE,
    'extract_preview': _lib.GP_FILE_OPERATION_PREVIEW,
    'extract_raw': _lib.GP_FILE_OPERATION_RAW,
    'extract_audio': _lib.GP_FILE_OPERATION_AUDIO,
    'extract_exif': _lib.GP_FILE_OPERATION_EXIF})


CAM_OPS = IntEnum('CameraOperations', {
    'capture_image': _lib.GP_OPERATION_CAPTURE_IMAGE,
    'capture_video': _lib.GP_OPERATION_CAPTURE_VIDEO,
    'capture_audio': _lib.GP_OPERATION_CAPTURE_AUDIO,
    'capture_preview': _lib.GP_OPERATION_CAPTURE_PREVIEW,
    'update_config': _lib.GP_OPERATION_CONFIG,
    'trigger_capture': _lib.GP_OPERATION_TRIGGER_CAPTURE})


DIR_OPS = IntEnum('DirectoryOperations', {
    'remove': _lib.GP_FOLDER_OPERATION_REMOVE_DIR,
    'create': _lib.GP_FOLDER_OPERATION_MAKE_DIR,
    'delete_all': _lib.GP_FOLDER_OPERATION_DELETE_ALL,
    'upload': _lib.GP_FOLDER_OPERATION_PUT_FILE})


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
    logger = LOGGER.getChild(domain)

    if level not in LOG_LEVELS:
        return
    logger.log(LOG_LEVELS[level], message)


class LibraryWrapper(object):
    NO_ERROR_CHECK = (
        "gp_log_add_func",
        "gp_context_new",
        "gp_list_count",
        "gp_result_as_string",
        "gp_library_version",)

    def __init__(self, to_wrap):
        """ Wrapper around our FFI object that performs error checking.

        Wraps functions inside an anonymous function that checks the inner
        function's return code for libgphoto2 errors and throws a
        :py:class:`gphoto2.errors.GPhoto2Error` if needed.

        :param to_wrap:     FFI library to wrap
        """
        self._lib = to_wrap

        # Register logging callback with FFI
        self.logging_cb = ffi.callback(
            "void(GPLogLevel, const char*, const char*, void*)",
            _logging_callback)
        self._lib.gp_log_add_func(_lib.GP_LOG_DEBUG, self.logging_cb,
                                  ffi.NULL)

    @staticmethod
    def _check_error(rval):
        """ Check a return value for a libgphoto2 error. """
        if rval < 0:
            raise errors.error_from_code(rval)
        else:
            return rval

    def __getattr__(self, name):
        val = getattr(self._lib, name)
        if not isinstance(val, int) and name not in self.NO_ERROR_CHECK:
            return lambda *a, **kw: self._check_error(val(*a, **kw))
        else:
            return val



#: The wrapped library
lib = LibraryWrapper(_lib)
