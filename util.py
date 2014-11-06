from lib import lib, ffi

class GPhoto2Error(Exception):
    def __init__(self, errcode):
        self.error_code = errcode
        msg = ffi.string(lib.gp_result_as_string(errcode))
        super(GPhoto2Error, self).__init__(msg)


def check_error(rval):
    if rval != 0:
        raise GPhoto2Error(rval)


def get_string(cfunc, *args):
    cstr = get_ctype("const char**", cfunc, *args)
    return ffi.string(cstr) if cstr else None


def get_ctype(rtype, cfunc, *args):
    val_p = ffi.new(rtype)
    args = args + (val_p,)
    check_error(cfunc(*args))
    return val_p[0]


def get_widget_type(widget):
    wtype = get_ctype("CameraWidgetType*", lib.gp_widget_get_type, widget)
    if wtype in (lib.GP_WIDGET_MENU, lib.GP_WIDGET_RADIO):
        return 'selection'
    elif wtype == lib.GP_WIDGET_TEXT:
        return 'text'
    elif wtype == lib.GP_WIDGET_RANGE:
        return 'range'
    elif wtype == lib.GP_WIDGET_DATE:
        return 'date'
    elif wtype == lib.GP_WIDGET_TOGGLE:
        return 'toggle'
    elif wtype == lib.GP_WIDGET_WINDOW:
        return 'window'
    elif wtype == lib.GP_WIDGET_SECTION:
        return 'section'
