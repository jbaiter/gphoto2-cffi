from . import backend


class SimpleNamespace(object):
    """ A simple :class:`object` subclass that provides attribute access to its
        namespace, as well as a meaningful repr.

   Unlike :class:`object`, with ``SimpleNamespace`` you can add and remove
   attributes.  If a ``SimpleNamespace`` object is initialized with keyword
   arguments, those are directly added to the underlying namespace.

   This is a backport from Python 3.3.
   """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


def get_string(cfunc, *args):
    """ Call a C function and return its return value as a Python string.

    :param cfunc:   C function to call
    :param args:    Arguments to call function with
    :rtype:         str
    """
    cstr = get_ctype("const char**", cfunc, *args)
    return backend.ffi.string(cstr).decode() if cstr else None


def get_ctype(rtype, cfunc, *args):
    """ Call a C function that takes a pointer as its last argument and
        return the C object that it contains after the function has finished.

    :param rtype:   C data type is filled by the function
    :param cfunc:   C function to call
    :param args:    Arguments to call function with
    :return:        A pointer to the specified data type
    """
    val_p = backend.ffi.new(rtype)
    args = args + (val_p,)
    cfunc(*args)
    return val_p[0]


def new_gp_object(typename):
    """ Create an indirect pointer to a GPhoto2 type, call its matching
        constructor function and return the pointer to it.

    :param typename:    Name of the type to create.
    :return:            A pointer to the specified data type.
    """
    obj_p = backend.ffi.new("{0}**".format(typename))
    backend.CONSTRUCTORS[typename](obj_p)
    return obj_p[0]
