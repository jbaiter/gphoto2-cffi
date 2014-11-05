from lib import lib, ffi

# FIXME: DRY!
# FIXME: Error handling!

def get_widget_name(widget):
    name = ffi.new("const char**")
    lib.gp_widget_get_name(widget, name)
    return ffi.string(name[0])

def get_widget_type(widget):
    type_p = ffi.new("CameraWidgetType*")
    lib.gp_widget_get_type(widget, type_p)
    if type_p[0] in (lib.GP_WIDGET_MENU, lib.GP_WIDGET_RADIO):
        return 'selection'
    elif type_p[0] == lib.GP_WIDGET_TEXT:
        return 'text'
    elif type_p[0] == lib.GP_WIDGET_RANGE:
        return 'range'
    elif type_p[0] == lib.GP_WIDGET_DATE:
        return 'date'
    elif type_p[0] == lib.GP_WIDGET_TOGGLE:
        return 'toggle'
    elif type_p[0] == lib.GP_WIDGET_WINDOW:
        return 'window'
    elif type_p[0] == lib.GP_WIDGET_SECTION:
        return 'section'

def get_widget_choices(widget):
    choices = []
    cur = ffi.new("const char**")
    for idx in xrange(lib.gp_widget_count_choices(widget)):
        lib.gp_widget_get_choice(widget, idx, cur)
        choices.append(ffi.string(cur[0]))
    return choices

def get_widget_readonly(widget):
    val_p = ffi.new("int*")
    lib.gp_widget_get_readonly(widget, val_p)
    return bool(val_p[0])

def get_widget_label(widget):
    label = ffi.new("const char**")
    lib.gp_widget_get_label(widget, label)
    return ffi.string(label[0])
