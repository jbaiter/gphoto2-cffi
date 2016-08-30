import os

from cffi import FFI

with open(os.path.join(os.path.dirname(__file__), 'gphoto2.cdef')) as fp:
    CDEF = fp.read()

SOURCE = """
#include "gphoto2/gphoto2-version.h"
#include "gphoto2/gphoto2-context.h"
#include "gphoto2/gphoto2-camera.h"
#include <time.h>
"""

ffi = FFI()
ffi.set_source("gphoto2cffi._backend", SOURCE, libraries=['gphoto2'])
ffi.cdef(CDEF)

if __name__ == "__main__":
    ffi.compile()
