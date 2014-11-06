from collections import namedtuple

import blinker

import util
from lib import ffi, lib

# FIXME: Error handling!

def list_cameras():
    raise NotImplementedError

Range = namedtuple("Range", ('min', 'max', 'step'))

class ConfigItem(object):
    def __init__(self, widget):
        self._widget = widget
        self.name = util.get_string(lib.gp_widget_get_name, widget)
        self.type = util.get_widget_type(widget)
        self.label = util.get_string(lib.gp_widget_get_label, widget)
        self.info = util.get_string(lib.gp_widget_get_info, widget)

        # FIXME: DRY!
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
        util.check_error(
            lib.gp_widget_get_range(self._widget, rmin, rmax, rinc))
        return Range(rmin, rmax, rinc)

    def __repr__(self):
        return ("<ConfigItem '{0}' [{1}, {2}, R{3}]>"
                .format(self.label, self.type, repr(self.value),
                        "O" if self.readonly else "W"))


class Camera(object):
    def __init__(self, bus=None, address=None):
        self.signals = blinker.Namespace()
        # TODO: Can we us a single global context?
        self._ctx = lib.gp_context_new()
        cp = ffi.new("Camera**")
        util.check_error(lib.gp_camera_new(cp))
        self._cam = cp[0]
        if (bus, address == None, None):
            util.check_error(lib.gp_camera_init(self._cam, self._ctx))
        else:
            raise NotImplementedError

    @property
    def config(self):
        root_widget = ffi.new("CameraWidget**")
        util.check_error(
            lib.gp_camera_get_config(self._cam, root_widget, self._ctx))
        return self._widget_to_dict(root_widget[0])

    def available_settings(self):
        raise NotImplementedError

    def capture(self, wait=False, retrieve=True, keep=False):
        raise NotImplementedError

    def get_preview(self):
        raise NotImplementedError

    def _widget_to_dict(self, cwidget):
        out = {}
        for idx in xrange(lib.gp_widget_count_children(cwidget)):
            child_p = ffi.new("CameraWidget**")
            util.check_error(lib.gp_widget_get_child(cwidget, idx, child_p))
            key = util.get_string(lib.gp_widget_get_name, child_p[0])
            if util.get_widget_type(child_p[0]) in ('window', 'section'):
                out[key] = self._widget_to_dict(child_p[0])
            else:
                itm = ConfigItem(child_p[0])
                if not itm.readonly:
                    out[key] = itm
        return out
