def error_from_code(errcode):
    from .backend import ffi, lib
    if errcode == lib.GP_ERROR_CORRUPTED_DATA:
        return CameraIOError(errcode, "Corrupted data received.")
    elif errcode == lib.GP_ERROR_FILE_EXISTS:
        return CameraIOError(errcode, "File already exists.")
    elif errcode == lib.GP_ERROR_FILE_NOT_FOUND:
        return CameraIOError(errcode, "File not found.")
    elif errcode == lib.GP_ERROR_DIRECTORY_NOT_FOUND:
        return CameraIOError(errcode, "Directory not found.")
    elif errcode == lib.GP_ERROR_DIRECTORY_EXISTS:
        return CameraIOError(errcode, "Directory already exists.")
    elif errcode == lib.GP_ERROR_NO_SPACE:
        return CameraIOError(errcode, "Not enough space.")
    elif errcode == lib.GP_ERROR_MODEL_NOT_FOUND:
        return UnsupportedDevice(errcode)
    elif errcode == lib.GP_ERROR_CAMERA_BUSY:
        return CameraBusy(errcode)
    elif errcode == lib.GP_ERROR_PATH_NOT_ABSOLUTE:
        return ValueError("Specified path is not absolute.")
    elif errcode == lib.GP_ERROR_CANCEL:
        return OperationCancelled(errcode)
    elif errcode == lib.GP_ERROR_CAMERA_ERROR:
        return CameraError(errcode, "Unspecified camera error.")
    elif errcode == lib.GP_ERROR_OS_FAILURE:
        return OSError("Unspecified failure of the operation system.")
    else:
        return GPhoto2Error(errcode,
                            ffi.string(lib.gp_result_as_string(errcode)))


class GPhoto2Error(Exception):
    def __init__(self, errcode=None, message=None):
        """ Generic exception type for all errors that originate in libgphoto2.

        Converts libgphoto2 error codes to their human readable message.

        :param errcode:     The libgphoto2 error code
        """
        self.error_code = errcode
        if message:
            super(GPhoto2Error, self).__init__(message)


class CameraIOError(GPhoto2Error, IOError):
    """ IOError on the camera itself. """
    pass


class UnsupportedDevice(GPhoto2Error):
    """ Specified camera model was not found.

    The specified model could not be found. This error is reported when the
    user specified a model that does not seem to be supported by any driver.
    """
    pass


class CameraBusy(GPhoto2Error):
    """ The camera is already busy.

    Camera I/O or a command is in progress.
    """
    pass


class OperationCancelled(GPhoto2Error):
    """ Cancellation successful.

    A cancellation requestion by the frontend via progress callback and
    GP_CONTEXT_FEEDBACK_CANCEL was successful and the transfer has been
    aborted.
    """
    pass


class CameraError(GPhoto2Error):
    """ Unspecified camera error

    The camera reported some kind of error. This can be either a photographic
    error, such as failure to autofocus, underexposure, or violating storage
    permission, anything else that stops the camera from performing the
    operation.
    """
    pass
