from lib import lib, ffi

def get_string(cfunc, *args):
    cstr = get_ctype("const char**", cfunc, *args)
    return ffi.string(cstr) if cstr else None


def get_ctype(rtype, cfunc, *args):
    val_p = ffi.new(rtype)
    args = args + (val_p,)
    cfunc(*args)
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
