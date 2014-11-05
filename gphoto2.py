import blinker

import util
from lib import ffi, lib

# FIXME: Error handling!

def list_cameras():
    raise NotImplementedError


class ConfigItem(object):
    def __init__(self, widget):
        self._widget = widget
        self.name = util.get_widget_name(widget)
        self.type = util.get_widget_type(widget)
        self.label = util.get_widget_label(widget)

        # FIXME: DRY!
        if self.type in ('selection', 'text'):
            val_p = ffi.new("char**")
            lib.gp_widget_get_value(widget, val_p)
            if val_p[0]:
                self.value = ffi.string(val_p[0])
            else:
                self.value = None
        elif self.type == 'range':
            val_p = ffi.new("float*")
            lib.gp_widget_get_value(widget, val_p)
            self.value = val_p[0]
        elif self.type in ('toggle', 'date'):
            val_p = ffi.new("int*")
            lib.gp_widget_get_value(widget, val_p)
            self.value = val_p[0] if self.type == 'date' else bool(val_p[0])
        else:
            raise ValueError("Unsupported widget type for ConfigItem: {0}"
                             .format(self.type))

        if self.type == 'selection':
            self.choices = util.get_widget_choices(widget)

        self.readonly = util.get_widget_readonly(widget)

    def __repr__(self):
        return ("<ConfigItem '{0}' [{1}, {2}, R{3}]>"
                .format(self.name, self.type, repr(self.value),
                        "O" if self.readonly else "W"))


class Camera(object):
    def __init__(self, bus=None, address=None):
        self.signals = blinker.Namespace()
        # TODO: Can we us a single global context?
        self._ctx = lib.gp_context_new()
        cp = ffi.new("Camera**")
        lib.gp_camera_new(cp)
        self._cam = cp[0]
        if (bus, address == None, None):
            lib.gp_camera_init(self._cam, self._ctx)
        else:
            raise NotImplementedError

    @property
    def config(self):
        root_widget = ffi.new("CameraWidget**")
        lib.gp_camera_get_config(self._cam, root_widget, self._ctx)
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
            lib.gp_widget_get_child(cwidget, idx, child_p)
            key = util.get_widget_name(child_p[0])
            if util.get_widget_type(child_p[0]) in ('window', 'section'):
                out[key] = self._widget_to_dict(child_p[0])
            else:
                itm = ConfigItem(child_p[0])
                if not itm.readonly:
                    out[key] = itm
        return out
