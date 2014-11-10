import os
import re
from collections import namedtuple
from datetime import datetime

import blinker

import util
from lib import ffi, lib

Range = namedtuple("Range", ('min', 'max', 'step'))
FileInfo = namedtuple("FileInfo", ('size', 'mime', 'dimensions',
                                   'permissions', 'last_modified'))

_global_ctx = lib.gp_context_new()

class ConfigItem(object):
    def __init__(self, widget):
        self._widget = widget
        self.name = util.get_string(lib.gp_widget_get_name, widget)
        self.type = util.get_widget_type(widget)
        self.label = util.get_string(lib.gp_widget_get_label, widget)
        self.info = util.get_string(lib.gp_widget_get_info, widget)

        value_fn = lib.gp_widget_get_value
        if self.type in ('selection', 'text'):
            self.value = util.get_string(value_fn, widget)
        elif self.type == 'range':
            self.value = util.get_ctype("float*", value_fn, widget)
            self.range = self._read_range()
        elif self.type in ('toggle', 'date'):
            val = util.get_ctype("int*", value_fn, widget)
            self.value = val if self.type == 'date' else bool(val)
        else:
            raise ValueError("Unsupported widget type for ConfigItem: {0}"
                             .format(self.type))
        if self.type == 'selection':
            self.choices = self._read_choices()
        self.readonly = bool(util.get_ctype(
            "int*", lib.gp_widget_get_readonly, widget))

    def set(self, value):
        val_p = None
        if self.type == 'selection':
            if value not in self.choices:
                raise ValueError("Invalid choice (valid: {0}",
                                 repr(self.choices))
            val = ffi.new("char*", value)
            val_p = ffi.new("char*[]", [value])
        elif self.type == 'text':
            if not isinstance(value, basestring):
                raise ValueError("Value must be a string.")
            val = ffi.new("char*", value)
            val_p = ffi.new("char*[]", [value])
        elif self.type == 'range':
            if value < self.range.min or value > self.range.max:
                raise ValueError("Value exceeds valid range ({0}-{1}."
                                 .format(self.range.min, self.range.max))
            if value%self.range.step:
                raise ValueError("Value can only be changed in steps of {0}."
                                 .format(self.range.step))
            val_p = ffi.new("float*")
        elif self.type == 'toggle':
            if not isinstance(value, bool):
                raise ValueError("Value must be bool.")
            val_p = ffi.new("int*")
        elif self.type == 'date':
            val_p = ffi.new("int*")
        check_error(lib.gp_widget_set_value(self._widget, val_p))

    def _read_choices(self):
        if self.type != 'selection':
            raise ValueError("Can only read choices for items of type "
                             "'selection'.")
        choices = []
        for idx in xrange(lib.gp_widget_count_choices(self._widget)):
            choices.append(
                util.get_string(lib.gp_widget_get_choice, self._widget, idx))
        return choices

    def _read_range(self):
        rmin = ffi.new("float*")
        rmax = ffi.new("float*")
        rinc = ffi.new("float*")
        lib.gp_widget_get_range(self._widget, rmin, rmax, rinc)
        return Range(rmin, rmax, rinc)

    def __repr__(self):
        return ("<ConfigItem '{0}' [{1}, {2}, R{3}]>"
                .format(self.label, self.type, repr(self.value),
                        "O" if self.readonly else "W"))


class Camera(object):
    def __init__(self, bus=None, address=None):
        # TODO: Can we use a single global context?
        self._ctx = lib.gp_context_new()
        camera_p = ffi.new("Camera**")
        lib.gp_camera_new(camera_p)
        self._cam = camera_p[0]
        if (bus, address) != (None, None):
            port_name = "usb:{0:03},{1:03}".format(bus, address)
            port_list_p = _get_portinfo_list()[0]
            port_info_p = ffi.new("GPPortInfo**")
            lib.gp_port_info_new(port_info_p)
            port_num = lib.gp_port_info_list_lookup_path(
                port_list_p, port_name)
            lib.gp_port_info_list_get_info(port_list_p, port_num,
                                           port_info_p[0])
            lib.gp_camera_set_port_info(self._cam, port_info_p[0][0])
        lib.gp_camera_init(self._cam, self._ctx)

    @property
    def config(self):
        root_widget = ffi.new("CameraWidget**")
        lib.gp_camera_get_config(self._cam, root_widget, self._ctx)
        return self._widget_to_dict(root_widget[0])

    @property
    def files(self):
        return self._list_files("/")

    def capture(self, wait=False, retrieve=True, keep=False):
        raise NotImplementedError

    def get_preview(self):
        raise NotImplementedError

    def _widget_to_dict(self, cwidget):
        out = {}
        for idx in xrange(lib.gp_widget_count_children(cwidget)):
            child_p = ffi.new("CameraWidget**")
            lib.gp_widget_get_child(cwidget, idx, child_p)
            key = util.get_string(lib.gp_widget_get_name, child_p[0])
            if util.get_widget_type(child_p[0]) in ('window', 'section'):
                out[key] = self._widget_to_dict(child_p[0])
            else:
                itm = ConfigItem(child_p[0])
                out[key] = itm
        return out

    def _list_files(self, path="/"):
        files = {}
        filelist_p = ffi.new("CameraList**")
        dirlist_p = ffi.new("CameraList**")
        lib.gp_list_new(filelist_p)
        lib.gp_list_new(dirlist_p)
        lib.gp_camera_folder_list_files(self._cam, path, filelist_p[0],
                                        self._ctx)
        lib.gp_camera_folder_list_folders(self._cam, path, dirlist_p[0],
                                          self._ctx)
        for idx in xrange(lib.gp_list_count(filelist_p[0])):
            name = ffi.new("const char**")
            lib.gp_list_get_name(filelist_p[0], idx, name)
            info = ffi.new("CameraFileInfo*")
            lib.gp_camera_file_get_info(self._cam, path, name[0], info, self._ctx)
            permissions = ["--", "r-", "-w", "rw"][info.file.permissions]
            files[os.path.join(path, ffi.string(name[0]))] = FileInfo(
                info.file.size, ffi.string(info.file.type),
                (info.file.width, info.file.height),
                permissions, datetime.fromtimestamp(info.file.mtime))
        for idx in xrange(lib.gp_list_count(dirlist_p[0])):
            name = ffi.new("const char**")
            lib.gp_list_get_name(dirlist_p[0], idx, name)
            files.update(self._list_files(
                os.path.join(path, ffi.string(name[0]))))
        lib.gp_list_free(filelist_p[0])
        lib.gp_list_free(dirlist_p[0])
        return files

def _get_portinfo_list():
    port_list_p = ffi.new("GPPortInfoList**")
    lib.gp_port_info_list_new(port_list_p)
    lib.gp_port_info_list_load(port_list_p[0])
    return port_list_p


def list_cameras():
    camlist_p = ffi.new("CameraList**")
    lib.gp_list_new(camlist_p)
    port_list_p = _get_portinfo_list()
    abilities_list_p = ffi.new("CameraAbilitiesList**")
    lib.gp_abilities_list_new(abilities_list_p)
    lib.gp_abilities_list_load(abilities_list_p[0], _global_ctx)
    lib.gp_abilities_list_detect(abilities_list_p[0], port_list_p[0],
                                 camlist_p[0], _global_ctx)
    out = {}
    for idx in xrange(lib.gp_list_count(camlist_p[0])):
        name = util.get_string(lib.gp_list_get_name, camlist_p[0], idx)
        value = util.get_string(lib.gp_list_get_value, camlist_p[0], idx)
        out[name] = tuple(int(x) for x in
                          re.match(r"usb:(\d+),(\d+)", value).groups())
    lib.gp_list_free(camlist_p[0])
    lib.gp_port_info_list_free(port_list_p[0])
    lib.gp_abilities_list_free(abilities_list_p[0])
    return out
