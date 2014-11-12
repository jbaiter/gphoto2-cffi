from __future__ import unicode_literals, division, absolute_import

import functools
import logging
import math
import os
import re
from collections import namedtuple
from datetime import datetime

from . import backend
from . backend import ffi, lib, get_string, get_ctype, new_gp_object

Range = namedtuple("Range", ('min', 'max', 'step'))
ImageDimensions = namedtuple("ImageDimensions", ('width', 'height'))
UsbDevice = namedtuple("UsbDevice", ('name', 'bus_no', 'device_no'))

_global_ctx = lib.gp_context_new()

def _infoproperty(prop_func):
    """ Decorator that creates a property method that checks for the presence
        of the _info struct and updates it, if absent.
    """
    @functools.wraps(prop_func)
    def decorated(self, *args, **kwargs):
        if self._info is None:
            try:
                self._update_info()
            except backend.GPhoto2Error:
                raise ValueError("Could not get file info, are you sure "
                                    "the file exists on the device?")
        return prop_func(self, *args, **kwargs)
    return property(fget=decorated, doc=prop_func.__doc__)


class CameraFile(object):
    """ A file on the camera. """
    def __init__(self, name, directory, camera=None, context=None):
        self.name = name
        self.directory = directory
        self._cam = camera
        self._ctx = context
        self._info = None

    @_infoproperty
    def size(self):
        """ File size in bytes.

        :rtype: int
        """
        return self.info.file.size

    @_infoproperty
    def mimetype(self):
        """ MIME type of the file.

        :rtype: str
        """
        return ffi.string(self.info.file.type)

    @_infoproperty
    def dimensions(self):
        """ Dimensions of the image.

        :rtype: :py:class:`ImageDimensions`
        """
        return ImageDimensions(self.info.file.width, self.info.file.height)

    @_infoproperty
    def permissions(self):
        """ Permissions of the file.

        Can be "r-" (read-only), "-w" (write-only), "rw" (read-write)
        or "--" (no rights).

        :rtype: str
        """
        can_read = self.info.file.permissions & lib.GP_FILE_PERM_READ
        can_write = self.info.file.permissions & lib.GP_FILE_PERM_DELETE
        return "{0}{1}".format("r" if can_read else "-",
                               "w" if can_write else "-")

    @_infoproperty
    def last_modified(self):
        """ Date of last modification.

        :rtype: :py:class:`datetime.datetime`
        """
        return datetime.fromtimestamp(self.info.file.mtime)

    def save(self, target_path, ftype='normal'):
        """ Save file content to a local file.

        :param target_path: Path to save remote file as.
        :type target_path:  str/unicode
        :param ftype:       Select 'view' on file.
        :type ftype:        str
        """
        if ftype not in backend.FILE_TYPES:
            raise ValueError("`ftype` must be one of {0}"
                             .format(backend.FILE_TYPES.keys()))
        camfile_p = ffi.new("CameraFile**")
        with open(target_path, 'wb') as fp:
            lib.gp_file_new_from_fd(camfile_p, fp.fileno())
            lib.gp_camera_file_get(self._cam, self.directory, self.name,
                                   backend.FILE_TYPES[ftype], camfile_p[0],
                                   self._ctx)

    def get_data(self, ftype='normal'):
        """ Get file content as a bytestring.

        :param ftype:       Select 'view' on file.
        :type ftype:        str
        :return:            File content
        :rtype:             bytes
        """
        if ftype not in backend.FILE_TYPES:
            raise ValueError("`ftype` must be one of {0}"
                             .format(backend.FILE_TYPES.keys()))
        camfile_p = ffi.new("CameraFile**")
        lib.gp_file_new(camfile_p)
        lib.gp_camera_file_get(self._cam, self.directory, self.name,
                               backend.FILE_TYPES[ftype], camfile_p[0],
                               self._ctx)
        data_p = ffi.new("char**")
        length_p = ffi.new("unsigned long*")
        lib.gp_file_get_data_and_size(camfile_p[0], data_p, length_p)
        return ffi.buffer(data_p[0], length_p[0])[:]

    def iter_data(self, ftype='normal', chunk_size=2**16):
        """ Get an iterator that yields chunks of the file content.

        :param ftype:       Select 'view' on file.
        :type ftype:        str
        :param chunk_size:  Size of yielded chunks in bytes
        :type chunk_size:   int
        :return:            Iterator
        """
        if ftype not in backend.FILE_TYPES:
            raise ValueError("`ftype` must be one of {0}"
                             .format(backend.FILE_TYPES.keys()))
        camfile_p = ffi.new("CameraFile**")
        buf_p = ffi.new("char[{0}]".format(chunk_size))
        size_p = ffi.new("uint64_t*")
        offset_p = ffi.new("uint64_t*")
        for chunk_idx in xrange(math.ceil(self.size/chunk_size)):
            size_p[0] = chunk_size
            lib.gp_camera_file_read(
                self._cam, self.directory, self.name,
                backend.FILE_TYPES[ftype], offset_p[0],
                buf_p, size_p, self._ctx)
            yield ffi.buffer(buf_p, size_p[0])[:]

    def remove(self):
        """ Remove file from device. """
        lib.gp_camera_file_delete(self._cam, self.directory, self.name,
                                  self._ctx)

    def _update_info(self):
        info = ffi.new("CameraFileInfo*")
        lib.gp_camera_file_get_info(self._cam, self.directory, self.name,
                                    info, self._ctx)
        self._info = info

    def __repr__(self):
        return "CameraFile(\"{0}/{1}\")".format(self.directory.rstrip("/"),
                                                self.name)


class ConfigItem(object):
    """ A configuration option on the device.

    :attr name:     Short name
    :attr value:    Current value
    :attr type:     Type of option, can be one of `selection`, `text`,
                    `range`, `toggle` or `date`.
    :attr label:    Human-readable label
    :attr info:     Information about the widget
    :attr choices:  Valid choices for value, only present when :py:attr:`type`
                    is `selection`.
    :attr range:    Valid range for value, only present when :py:attr:`type`
                    is `range`.
    :attr readonly: Whether the value can be written to or not
    """
    def __init__(self, widget, cam, ctx):
        self._widget = widget
        root_p = ffi.new("CameraWidget**")
        lib.gp_widget_get_root(self._widget, root_p)
        self._root = root_p[0]
        self._cam = cam
        self._ctx = ctx
        self.name = get_string(lib.gp_widget_get_name, widget)
        typenum = get_ctype("CameraWidgetType*", lib.gp_widget_get_type,
                            widget)
        self.type = backend.WIDGET_TYPES[typenum]
        self.label = get_string(lib.gp_widget_get_label, widget)
        self.info = get_string(lib.gp_widget_get_info, widget)

        value_fn = lib.gp_widget_get_value
        if self.type in ('selection', 'text'):
            self.value = get_string(value_fn, widget)
        elif self.type == 'range':
            self.value = get_ctype("float*", value_fn, widget)
            self.range = self._read_range()
        elif self.type in ('toggle', 'date'):
            val = get_ctype("int*", value_fn, widget)
            self.value = val if self.type == 'date' else bool(val)
        else:
            raise ValueError("Unsupported widget type for ConfigItem: {0}"
                             .format(self.type))
        if self.type == 'selection':
            self.choices = self._read_choices()
        self.readonly = bool(get_ctype(
            "int*", lib.gp_widget_get_readonly, widget))

    def set(self, value):
        """ Update value of the option.

        Only possible for options with :py:attr:`readonly` set to `False`.
        If :py:attr:`type` is `choice`, the value must be one of the
        :py:attr:`choices`.
        If :py:attr:`type` is `range`, the value must be in the range
        described by :py:attr:`range`.

        :param value:   Value to set
        """
        if self.readonly:
            raise ValueError("Option is read-only.")
        val_p = None
        if self.type == 'selection':
            if value not in self.choices:
                raise ValueError("Invalid choice (valid: {0}",
                                 repr(self.choices))
            val_p = ffi.new("const char[]", bytes(value))
        elif self.type == 'text':
            if not isinstance(value, basestring):
                raise ValueError("Value must be a string.")
            val_p = ffi.new("char**")
            val_p[0] = ffi.new("char[]", bytes(value))
        elif self.type == 'range':
            if value < self.range.min or value > self.range.max:
                raise ValueError("Value exceeds valid range ({0}-{1}."
                                 .format(self.range.min, self.range.max))
            if value%self.range.step:
                raise ValueError("Value can only be changed in steps of {0}."
                                 .format(self.range.step))
            val_p = ffi.new("float*")
            val_p[0] = value
        elif self.type == 'toggle':
            if not isinstance(value, bool):
                raise ValueError("Value must be bool.")
            val_p = ffi.new("int*")
            val_p[0] = value
        elif self.type == 'date':
            val_p = ffi.new("int*")
            val_p[0] = value
        lib.gp_widget_set_value(self._widget, val_p)
        lib.gp_camera_set_config(self._cam, self._root, self._ctx)

    def _read_choices(self):
        if self.type != 'selection':
            raise ValueError("Can only read choices for items of type "
                             "'selection'.")
        choices = []
        for idx in xrange(lib.gp_widget_count_choices(self._widget)):
            choices.append(
                get_string(lib.gp_widget_get_choice, self._widget, idx))
        return choices

    def _read_range(self):
        rmin = ffi.new("float*")
        rmax = ffi.new("float*")
        rinc = ffi.new("float*")
        lib.gp_widget_get_range(self._widget, rmin, rmax, rinc)
        return Range(rmin, rmax, rinc)

    def __repr__(self):
        return ("ConfigItem('{0}', {1}, ,{2}, 'r{3}')"
                .format(self.label, self.type, repr(self.value),
                        "o" if self.readonly else "w"))


class Camera(object):
    def __init__(self, bus=None, device=None):
        """ A camera device.

        The specific device can be auto-detected or set manually by
        specifying the USB bus and device number.

        :param bus:     USB bus number
        :param device: USB device number
        """
        self._logger = logging.getLogger()

        # NOTE: It is not strictly neccessary to create a context for every
        #       device, however it is significantly (>500ms) faster when
        #       actions are to be performed simultaneously.
        self._ctx = lib.gp_context_new()

        self._cam = new_gp_object("Camera")
        if (bus, device) != (None, None):
            port_name = b"usb:{0:03},{1:03}".format(bus, device)
            port_list_p = new_gp_object("GPPortInfoList")
            lib.gp_port_info_list_load(port_list_p)
            port_info_p = ffi.new("GPPortInfo*")
            lib.gp_port_info_new(port_info_p)
            port_num = lib.gp_port_info_list_lookup_path(
                port_list_p, port_name)
            lib.gp_port_info_list_get_info(port_list_p, port_num,
                                           port_info_p)
            lib.gp_camera_set_port_info(self._cam, port_info_p[0])
        lib.gp_camera_init(self._cam, self._ctx)

    def __del__(self):
        lib.gp_camera_free(self._cam)

    @property
    def config(self):
        """ Configuration for the camera.

        :rtype:     dict
        """
        root_widget = ffi.new("CameraWidget**")
        lib.gp_camera_get_config(self._cam, root_widget, self._ctx)
        return self._widget_to_dict(root_widget[0])

    @property
    def files(self):
        """ List of files on the camera's permanent storage. """
        return self._recurse_files(b"/")

    def upload_file(self, source_path, target_path, ftype='normal'):
        if ftype not in backend.FILE_TYPES:
            raise ValueError("`ftype` must be one of {0}"
                             .format(backend.FILE_TYPES.keys()))
        target_dirname, target_fname = (os.path.dirname(target_path),
                                        os.path.basename(target_path))
        camerafile_p = ffi.new("CameraFile**")
        with open(source_path, 'rb') as fp:
            lib.gp_file_new_from_fd(camerafile_p, fp.fileno())
            lib.gp_camera_folder_put_file(
                self._cam, target_dirname, target_fname,
                backend.FILE_TYPES[ftype], camerafile_p[0], self._ctx)

    def capture(self, to_camera_storage=False):
        """ Capture an image.

        :param to_camera_storage:   Save image to the camera's internal storage
        :type to_camera_storage:    bool
        :return:    A :py:class:`CameraFile` if `to_camera_storage` was `True`,
                    otherwise the captured image as a bytestring.
        :rtype:     :py:class:`CameraFile` or bytes
        """
        target = self.config['settings']['capturetarget']
        if to_camera_storage and target.value != "Memory card":
            target.set("Memory card")
        elif not to_camera_storage and target.value != "Internal RAM":
            target.set("Internal RAM")
        lib.gp_camera_trigger_capture(self._cam, self._ctx)

        # Wait for capture to finish
        event_type = ffi.new("CameraEventType*")
        event_data_p = ffi.new("void**", ffi.NULL)
        while True:
            lib.gp_camera_wait_for_event(self._cam, 1000, event_type,
                                            event_data_p, self._ctx)
            if event_type[0] == lib.GP_EVENT_CAPTURE_COMPLETE:
                self._logger.info("Capture completed.")
            if event_type[0] == lib.GP_EVENT_FILE_ADDED:
                break
        camfile_p = ffi.cast("CameraFilePath*", event_data_p[0])
        fobj = CameraFile(ffi.string(camfile_p[0].name),
                          ffi.string(camfile_p[0].folder),
                          self._cam, self._ctx)
        if to_camera_storage:
            self._logger.info("File written to storage at {0}."
                                .format(fobj))
            return fobj
        else:
            data = fobj.get_data()
            fobj.remove()
            return data

    def get_preview(self):
        """ Get a preview from the camera's viewport.

        :return:    The preview image as a bytestring
        :rtype:     bytes
        """
        camfile_p = ffi.new("CameraFile**")
        lib.gp_file_new(camfile_p)
        lib.gp_camera_capture_preview(self._cam, camfile_p[0], self._ctx)
        data_p = ffi.new("char**")
        length_p = ffi.new("unsigned long*")
        lib.gp_file_get_data_and_size(camfile_p[0], data_p, length_p)
        return ffi.buffer(data_p[0], length_p[0])[:]

    def _widget_to_dict(self, cwidget):
        out = {}
        for idx in xrange(lib.gp_widget_count_children(cwidget)):
            child_p = ffi.new("CameraWidget**")
            lib.gp_widget_get_child(cwidget, idx, child_p)
            key = get_string(lib.gp_widget_get_name, child_p[0])
            typenum = get_ctype("CameraWidgetType*", lib.gp_widget_get_type,
                                child_p[0])
            if typenum in (lib.GP_WIDGET_WINDOW, lib.GP_WIDGET_SECTION):
                out[key] = self._widget_to_dict(child_p[0])
            else:
                itm = ConfigItem(child_p[0], self._cam, self._ctx)
                out[key] = itm
        return out

    def _recurse_files(self, path):
        # Skip files in internal RAM
        files = [] if path == "/" else self._list_files(path)
        for subdir in self._list_directories(path):
            files.extend(self._recurse_files(
                b"{0}/{1}".format(path.rstrip("/"), subdir)))
        return files

    def _list_directories(self, path):
        out = []
        dirlist_p = new_gp_object("CameraList")
        lib.gp_camera_folder_list_folders(self._cam, path, dirlist_p,
                                          self._ctx)
        for idx in xrange(lib.gp_list_count(dirlist_p)):
            out.append(get_string(lib.gp_list_get_name, dirlist_p, idx))
        lib.gp_list_free(dirlist_p)
        return out

    def _list_files(self, path):
        files = []
        filelist_p = new_gp_object("CameraList")
        lib.gp_camera_folder_list_files(self._cam, path, filelist_p,
                                        self._ctx)
        for idx in xrange(lib.gp_list_count(filelist_p)):
            name = ffi.new("const char**")
            lib.gp_list_get_name(filelist_p, idx, name)
            files.append(CameraFile(ffi.string(name[0]), path, self._cam,
                                    self._ctx))
        lib.gp_list_free(filelist_p)
        return files


def list_cameras():
    """ List all attached USB cameras that are supported by libgphoto2.

    :return:    All recognized cameras
    :rtype:     list of :py:class:`UsbDevice`
    """
    camlist_p = new_gp_object("CameraList")
    port_list_p = new_gp_object("GPPortInfoList")
    lib.gp_port_info_list_load(port_list_p)
    abilities_list_p = new_gp_object("CameraAbilitiesList")
    lib.gp_abilities_list_load(abilities_list_p, _global_ctx)
    lib.gp_abilities_list_detect(abilities_list_p, port_list_p,
                                 camlist_p, _global_ctx)
    out = []
    for idx in xrange(lib.gp_list_count(camlist_p)):
        name = get_string(lib.gp_list_get_name, camlist_p, idx)
        value = get_string(lib.gp_list_get_value, camlist_p, idx)
        bus_no, device_no = (int(x) for x in
                             re.match(r"usb:(\d+),(\d+)", value).groups())
        out.append(UsbDevice(name, bus_no, device_no))
    lib.gp_list_free(camlist_p)
    lib.gp_port_info_list_free(port_list_p)
    lib.gp_abilities_list_free(abilities_list_p)
    return out
