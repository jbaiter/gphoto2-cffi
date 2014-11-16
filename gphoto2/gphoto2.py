from __future__ import unicode_literals, division, absolute_import

import functools
import itertools
import logging
import math
import os
import re
from collections import namedtuple
from datetime import datetime

from enum import IntEnum

from . import backend, errors
from .backend import ffi, lib, get_string, get_ctype, new_gp_object
from .util import SimpleNamespace

Range = namedtuple("Range", ('min', 'max', 'step'))
ImageDimensions = namedtuple("ImageDimensions", ('width', 'height'))
UsbInformation = namedtuple("UsbInformation", ('vendor', 'product', 'devclass',
                                               'subclass', 'protocol'))
StorageInformation = namedtuple(
    "StorageInformation",
    ('label', 'directory', 'description', 'type', 'accesstype',
     'total_space', 'free_space', 'remaining_images'))
FileOperations = IntEnum(b'FileOperations', {
    'remove': lib.GP_FILE_OPERATION_DELETE,
    'extract_preview': lib.GP_FILE_OPERATION_PREVIEW,
    'extract_raw': lib.GP_FILE_OPERATION_RAW,
    'extract_audio': lib.GP_FILE_OPERATION_AUDIO,
    'extract_exif': lib.GP_FILE_OPERATION_EXIF})
CameraOperations = IntEnum(b'CameraOperations', {
    'capture_image': lib.GP_OPERATION_CAPTURE_IMAGE,
    'capture_video': lib.GP_OPERATION_CAPTURE_VIDEO,
    'capture_audio': lib.GP_OPERATION_CAPTURE_AUDIO,
    'capture_preview': lib.GP_OPERATION_CAPTURE_PREVIEW,
    'update_config': lib.GP_OPERATION_CONFIG,
    'trigger_capture': lib.GP_OPERATION_TRIGGER_CAPTURE})
DirectoryOperations = IntEnum(b'DirectoryOperations', {
    'remove': lib.GP_FOLDER_OPERATION_REMOVE_DIR,
    'create': lib.GP_FOLDER_OPERATION_MAKE_DIR,
    'delete_all': lib.GP_FOLDER_OPERATION_DELETE_ALL,
    'upload': lib.GP_FOLDER_OPERATION_PUT_FILE})

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
            except errors.GPhoto2Error:
                raise ValueError("Could not get file info, are you sure "
                                 "the file exists on the device?")
        return prop_func(self, *args, **kwargs)
    return property(fget=decorated, doc=prop_func.__doc__)


def _needs_initialized(func):
    """ Decorator that checks if the :py:class:`Camera` is already initialized
        and does so, if not.
    """
    @functools.wraps(func)
    def decorated(self, *args, **kwargs):
        if not self._initialized:
            self._initialize()
        return func(self, *args, **kwargs)
    return decorated


def _needs_op(op):
    """ Decorator that checks the `supported_operations` for the specified
        operation and throws a RuntimeException if it is unsupported.
    """
    # TODO: Is this really needed? Check if the library responds with sensible
    # error messages on unsupported operations?
    def decorator(func):
        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            if self._op_check and op not in self.supported_operations:
                raise RuntimeError("Device does not support this operation.")
            return func(self, *args, **kwargs)
        return wrapped
    return decorator


class Directory(object):
    """ A directory on the camera. """
    def __init__(self, name, parent, camera):
        self.name = name
        self.parent = parent
        self._file_ops = camera._abilities.file_operations
        self._dir_ops = camera._abilities.folder_operations
        self._op_check = camera._op_check
        self._cam = camera

    @property
    def path(self):
        if self.parent is None:
            return "/"
        else:
            return os.path.join(self.parent.path, self.name)

    @property
    def supported_operations(self):
        return tuple(op for op in DirectoryOperations
                     if self._dir_ops & op)

    @property
    def exists(self):
        if self.name in ("", "/") and self.parent is None:
            return True
        else:
            return self in self.parent.directories

    @property
    def files(self):
        filelist_p = new_gp_object("CameraList")
        lib.gp_camera_folder_list_files(self._cam._cam, bytes(self.path),
                                        filelist_p, self._cam._ctx)
        for idx in xrange(lib.gp_list_count(filelist_p)):
            yield File(name=get_string(lib.gp_list_get_name, filelist_p, idx),
                       directory=self, camera=self._cam)
        lib.gp_list_free(filelist_p)

    @property
    def directories(self):
        dirlist_p = new_gp_object("CameraList")
        lib.gp_camera_folder_list_folders(self._cam._cam, bytes(self.path),
                                          dirlist_p, self._cam._ctx)
        for idx in xrange(lib.gp_list_count(dirlist_p)):
            name = os.path.join(self.path, get_string(
                lib.gp_list_get_name, dirlist_p, idx))
            yield Directory(name=name, parent=self, camera=self._cam)
        lib.gp_list_free(dirlist_p)

    @_needs_op(DirectoryOperations.create)
    def create(self):
        lib.gp_camera_folder_make_dir(self._cam._cam, self.parent.path,
                                      self.name, self._cam._ctx)

    @_needs_op(DirectoryOperations.remove)
    def remove(self, recurse=False):
        lib.gp_camera_folder_remove_dir(self._cam._cam, self.parent.path,
                                        self.name, self._cam._ctx)

    @_needs_op(DirectoryOperations.upload)
    def upload(self, local_path):
        """ Upload a file to the camera's permanent storage.

        :param local_path: Path to file to copy
        :type local_path:  str/unicode
        """
        camerafile_p = ffi.new("CameraFile**")
        with open(local_path, 'rb') as fp:
            lib.gp_file_new_from_fd(camerafile_p, fp.fileno())
            lib.gp_camera_folder_put_file(
                self._cam._cam, bytes(self.path) + b"/",
                bytes(os.path.basename(local_path)),
                backend.FILE_TYPES['normal'], camerafile_p[0], self.__cam.ctx)

    def __eq__(self, other):
        return (self.name == other.name and
                self.parent == other.parent and
                self._cam == other._cam)

    def __repr__(self):
        return "Directory(\"{0}\")".format(self.path)


class File(object):
    """ A file on the camera. """
    def __init__(self, name, directory, camera):
        self.name = name
        self.directory = directory
        self._cam = camera
        self._operations = camera._abilities.file_operations
        self._op_check = camera._op_check
        self._info = None

    @property
    def supported_operations(self):
        return tuple(op for op in FileOperations
                     if self._operations & op)

    @_infoproperty
    def size(self):
        """ File size in bytes.

        :rtype: int
        """
        return self._info.file.size

    @_infoproperty
    def mimetype(self):
        """ MIME type of the file.

        :rtype: str
        """
        return ffi.string(self._info.file.type)

    @_infoproperty
    def dimensions(self):
        """ Dimensions of the image.

        :rtype: :py:class:`ImageDimensions`
        """
        return ImageDimensions(self._info.file.width, self._info.file.height)

    @_infoproperty
    def permissions(self):
        """ Permissions of the file.

        Can be "r-" (read-only), "-w" (write-only), "rw" (read-write)
        or "--" (no rights).

        :rtype: str
        """
        can_read = self._info.file.permissions & lib.GP_FILE_PERM_READ
        can_write = self._info.file.permissions & lib.GP_FILE_PERM_DELETE
        return "{0}{1}".format("r" if can_read else "-",
                               "w" if can_write else "-")

    @_infoproperty
    def last_modified(self):
        """ Date of last modification.

        :rtype: :py:class:`datetime.datetime`
        """
        return datetime.fromtimestamp(self._info.file.mtime)

    def save(self, target_path, ftype='normal'):
        """ Save file content to a local file.

        :param target_path: Path to save remote file as.
        :type target_path:  str/unicode
        :param ftype:       Select 'view' on file.
        :type ftype:        str
        """
        if self._op_check:
            self._check_type_supported(ftype)
        camfile_p = ffi.new("CameraFile**")
        with open(target_path, 'wb') as fp:
            lib.gp_file_new_from_fd(camfile_p, fp.fileno())
            lib.gp_camera_file_get(self._cam._cam, bytes(self.directory.path),
                                   self.name, backend.FILE_TYPES[ftype],
                                   camfile_p[0], self._cam._ctx)

    def get_data(self, ftype='normal'):
        """ Get file content as a bytestring.

        :param ftype:       Select 'view' on file.
        :type ftype:        str
        :return:            File content
        :rtype:             bytes
        """
        if self._op_check:
            self._check_type_supported(ftype)
        camfile_p = ffi.new("CameraFile**")
        lib.gp_file_new(camfile_p)
        lib.gp_camera_file_get(self._cam._cam, bytes(self.directory.path),
                               self.name, backend.FILE_TYPES[ftype],
                               camfile_p[0], self._cam._ctx)
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
        self._check_type_supported(ftype)
        buf_p = ffi.new("char[{0}]".format(chunk_size))
        size_p = ffi.new("uint64_t*")
        offset_p = ffi.new("uint64_t*")
        for chunk_idx in xrange(int(math.ceil(self.size/chunk_size))):
            size_p[0] = chunk_size
            lib.gp_camera_file_read(
                self._cam._cam, bytes(self.directory.path), self.name,
                backend.FILE_TYPES[ftype], offset_p[0],
                buf_p, size_p, self._cam._ctx)
            yield ffi.buffer(buf_p, size_p[0])[:]

    @_needs_op(FileOperations.remove)
    def remove(self):
        """ Remove file from device. """
        lib.gp_camera_file_delete(self._cam._cam, bytes(self.directory.path),
                                  self.name, self._cam._ctx)

    def _check_type_supported(self, ftype):
        if ftype not in backend.FILE_TYPES:
            raise ValueError("`ftype` must be one of {0}"
                             .format(backend.FILE_TYPES.keys()))
        valid_ops = self.supported_operations
        fops = FileOperations
        op_is_unsupported = (
            (ftype == 'exif' and fops.extract_exif not in valid_ops) or
            (ftype == 'preview' and fops.extract_preview not in valid_ops) or
            (ftype == 'raw' and fops.extract_raw not in valid_ops) or
            (ftype == 'audio' and fops.extract_audio not in valid_ops))
        if op_is_unsupported:
            raise RuntimeError("Operation is not supported for this type.")

    def _update_info(self):
        info = ffi.new("CameraFileInfo*")
        lib.gp_camera_file_get_info(self._cam._cam, bytes(self.directory.path),
                                    self.name, info, self._cam._ctx)
        self._info = info

    def __eq__(self, other):
        return (self.name == other.name and
                self.directory == other.directory and
                self._cam == other._cam)

    def __repr__(self):
        return "File(\"{0}/{1}\")".format(self.directory.path.rstrip("/"),
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
    def __init__(self, widget, camera):
        self._widget = widget
        root_p = ffi.new("CameraWidget**")
        lib.gp_widget_get_root(self._widget, root_p)
        self._root = root_p[0]
        self._cam = camera
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
            if self.type == 'date':
                self.value = val
            else:
                self.value = None if val == 2 else bool(val)
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
            if value % self.range.step:
                raise ValueError("Value can only be changed in steps of {0}."
                                 .format(self.range.step))
            val_p = ffi.new("float*")
            val_p[0] = value
        elif self.type == 'toggle':
            if not isinstance(value, bool):
                raise ValueError("Value must be bool.")
            val_p = ffi.new("int*")
            val_p[0] = int(value)
        elif self.type == 'date':
            val_p = ffi.new("int*")
            val_p[0] = value
        lib.gp_widget_set_value(self._widget, val_p)
        lib.gp_camera_set_config(self._cam._cam, self._root, self._cam._ctx)

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
        return ("ConfigItem('{0}', {1}, {2}, r{3})"
                .format(self.label, self.type, repr(self.value),
                        "o" if self.readonly else "w"))


class Camera(object):
    def __init__(self, bus=None, device=None, lazy=False, op_check=True,
                 _abilities=None):
        """ A camera device.

        The specific device can be auto-detected or set manually by
        specifying the USB bus and device number.

        :param bus:         USB bus number
        :param device:      USB device number
        :param lazy:        Only initialize the device when needed
        :param op_check:    Check for support before doing any operation
                            (Some devices can do more than they admit to, hence
                            the option to disable it)
        """
        self._logger = logging.getLogger()

        # NOTE: It is not strictly neccessary to create a context for every
        #       device, however it is significantly (>500ms) faster when
        #       actions are to be performed simultaneously.
        self._ctx = lib.gp_context_new()
        self._initialized = False
        self._op_check = op_check
        self._usb_address = (bus, device)
        self._abilities = _abilities
        if not lazy:
            self._initialize()

    @property
    def supported_operations(self):
        if self._abilities is None:
            self._initialize()
        return tuple(op for op in CameraOperations
                     if self._abilities.operations & op)

    @property
    def usb_info(self):
        if self._abilities is None:
            self._initialize()
        return UsbInformation(self._abilities.usb_vendor,
                              self._abilities.usb_product,
                              self._abilities.usb_class,
                              self._abilities.usb_subclass,
                              self._abilities.usb_protocol)

    @property
    def model_name(self):
        if self._abilities is None:
            self._initialize()
        return ffi.string(self._abilities.model)

    @property
    @_needs_initialized
    @_needs_op(CameraOperations.update_config)
    def config(self):
        """ Configuration for the camera.

        :rtype:     dict
        """
        root_widget = ffi.new("CameraWidget**")
        lib.gp_camera_get_config(self._cam, root_widget, self._ctx)
        return self._widget_to_dict(root_widget[0])

    @property
    @_needs_initialized
    def filesystem(self):
        """ The camera's root directory. """
        return Directory(name="/", parent=None, camera=self)

    @property
    @_needs_initialized
    def storage_info(self):
        """ Information about the camera's storage. """
        info_p = ffi.new("CameraStorageInformation**")
        num_info_p = ffi.new("int*")
        lib.gp_camera_get_storageinfo(self._cam, info_p, num_info_p, self._ctx)
        infos = []
        for idx in xrange(num_info_p[0]):
            out = SimpleNamespace()
            struc = (info_p[0] + idx)
            fields = struc.fields
            if lib.GP_STORAGEINFO_BASE & fields:
                out.directory = next(
                    (d for d in self.list_all_directories()
                     if d.path == ffi.string(struc.basedir)), None)
            if lib.GP_STORAGEINFO_LABEL & fields:
                out.label = ffi.string(struc.label)
            if lib.GP_STORAGEINFO_DESCRIPTION & fields:
                out.description = ffi.string(struc.description)
            if lib.GP_STORAGEINFO_STORAGETYPE & fields:
                stype = struc.type
                if lib.GP_STORAGEINFO_ST_FIXED_ROM & stype:
                    out.type = 'fixed_rom'
                elif lib.GP_STORAGEINFO_ST_REMOVABLE_ROM & stype:
                    out.type = 'removable_rom'
                elif lib.GP_STORAGEINFO_ST_FIXED_RAM & stype:
                    out.type = 'fixed_ram'
                elif lib.GP_STORAGEINFO_ST_REMOVABLE_RAM & stype:
                    out.type = 'removable_ram'
                else:
                    out.type = 'unknown'
            if lib.GP_STORAGEINFO_ACCESS & fields:
                if lib.GP_STORAGEINFO_AC_READWRITE & struc.access:
                    out.access = 'read-write'
                elif lib.GP_STORAGEINFO_AC_READONLY & struc.access:
                    out.access = 'read-only'
                elif lib.GP_STORAGEINFO_AC_READONLY_WITH_DELETE & struc.access:
                    out.access = 'read-delete'
            if lib.GP_STORAGEINFO_MAXCAPACITY & fields:
                out.capacity = int(struc.capacitykbytes)
            if lib.GP_STORAGEINFO_FREESPACEKBYTES & fields:
                out.free_space = int(struc.freekbytes)
            if lib.GP_STORAGEINFO_FREESPACEIMAGES & fields:
                out.remaining_images = int(struc.freeimages)
            infos.append(out)
        return infos

    def list_all_files(self):
        """ Utility method that yields all files on the device's file
            systems.
        """
        def list_files_recursively(directory):
            f_gen = itertools.chain(
                directory.files,
                *(list_files_recursively(d) for d in directory.directories))
            for f in f_gen:
                yield f
        return list_files_recursively(self.filesystem)

    def list_all_directories(self):
        """ Utility method that yields all directories on the device's file
            systems.
        """
        def list_dirs_recursively(directory):
            if directory == self.filesystem:
                yield directory
            d_gen = itertools.chain(
                directory.directories,
                *(list_dirs_recursively(d) for d in directory.directories))
            for d in d_gen:
                yield d
        return list_dirs_recursively(self.filesystem)

    @_needs_initialized
    @_needs_op(CameraOperations.capture_image)
    def capture(self, to_camera_storage=False):
        """ Capture an image.

        Some cameras (mostly Canon and Nikon) support capturing to internal
        RAM. On these devices, you have to specify `to_camera_storage` if
        you want to save the images to the memory card. On devices that
        do not support saving to RAM, the only difference is that the file
        is automatically downloaded and deleted when set to `False`.

        :param to_camera_storage:   Save image to the camera's internal storage
        :type to_camera_storage:    bool
        :return:    A :py:class:`File` if `to_camera_storage` was `True`,
                    otherwise the captured image as a bytestring.
        :rtype:     :py:class:`File` or bytes
        """
        target = self.config['settings']['capturetarget']
        if to_camera_storage and target.value != "Memory card":
            target.set("Memory card")
        elif not to_camera_storage and target.value != "Internal RAM":
            target.set("Internal RAM")
        lib.gp_camera_trigger_capture(self._cam, self._ctx)

        fobj = self._wait_for_event(lib.GP_EVENT_FILE_ADDED)
        if to_camera_storage:
            self._logger.info("File written to storage at {0}.".format(fobj))
            return fobj
        else:
            data = fobj.get_data()
            fobj.remove()
            return data

    @_needs_initialized
    @_needs_op(CameraOperations.capture_preview)
    def get_preview(self):
        """ Get a preview from the camera's viewport.

        This will usually be a JPEG image with the dimensions depending on
        the camera.

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

    def _initialize(self):
        self._cam = new_gp_object("Camera")
        if self._usb_address != (None, None):
            port_name = b"usb:{0:03},{1:03}".format(*self._usb_address)
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
        else:
            try:
                lib.gp_camera_init(self._cam, self._ctx)
            except errors.UnsupportedDevice as e:
                raise errors.UnsupportedDevice(
                    e.error_code, "Could not find any supported devices.")

        if self._abilities is None:
            self._abilities = ffi.new("CameraAbilities*")
            lib.gp_camera_get_abilities(self._cam, self._abilities)
        self._initialized = True

    def _wait_for_event(self, event_type=None, duration=0):
        if event_type is None and not duration:
            raise ValueError("Please specifiy either `event_type` or "
                             "`duration!`")
        start_time = time.time()
        event_type_p = ffi.new("CameraEventType*")
        event_data_p = ffi.new("void**", ffi.NULL)
        while True:
            try:
                lib.gp_camera_wait_for_event(self._cam, 1000, event_type_p,
                                             event_data_p, self._ctx)
            except errors.GPhoto2Error as e:
                self._logger.error(e)
                continue
            if event_type_p[0] == lib.GP_EVENT_CAPTURE_COMPLETE:
                self._logger.info("Capture completed.")
            elif event_type_p[0] == lib.GP_EVENT_FILE_ADDED:
                self._logger.info("File added.")
            elif event_type_p[0] == lib.GP_EVENT_TIMEOUT:
                self._logger.debug("Timeout while waiting for event.")
                continue
            do_break = (event_type_p[0] == event_type or
                        ((time.time() - start_time > duration)
                         if duration else False))
            if do_break:
                break
        if event_type == lib.GP_EVENT_FILE_ADDED:
            camfile_p = ffi.cast("CameraFilePath*", event_data_p[0])
            directory = next(f for f in self.list_all_directories()
                             if f.path == ffi.string(camfile_p[0].folder))
            return File(name=ffi.string(camfile_p[0].name),
                        directory=directory, camera=self)

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
                itm = ConfigItem(child_p[0], self)
                out[key] = itm
        return out

    def __repr__(self):
        return "<Camera \"{0}\" at usb:{1:03}:{2:03}>".format(
            self.model_name, *self._usb_address)

    def __del__(self):
        if self._initialized:
            lib.gp_camera_free(self._cam)


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
        abilities = ffi.new("CameraAbilities*")
        ability_idx = lib.gp_abilities_list_lookup_model(
            abilities_list_p, name)
        lib.gp_abilities_list_get_abilities(abilities_list_p, ability_idx,
                                            abilities)
        if abilities.device_type == lib.GP_DEVICE_STILL_CAMERA:
            out.append(Camera(bus_no, device_no, lazy=True,
                              _abilities=abilities))
    lib.gp_list_free(camlist_p)
    lib.gp_port_info_list_free(port_list_p)
    lib.gp_abilities_list_free(abilities_list_p)
    return out
