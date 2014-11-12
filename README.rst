gphoto2-cffi
============

Python bindings for `libgphoto2`_ with an idiomatic interface and `PyPy`_
support, using `cffi`_. In contrast to other bindings for Python, gphoto2-cffi
hides most of the lower-level abstractions and allows you to work with an
elegent API that exposes most of the library's features in an idiomatic
interface::

    import gphoto2 as gp

    # List all attached cameras that are supported
    cams = gp.list_cameras()

    # Get a camera instance by specifying a USB bus and device number
    my_cam = gp.Camera(bus=4, device=1)

    # Get an instance for the first supported camera
    my_cam = gp.Camera()

    # Capture an image to the camera's RAM and get its data
    imgdata = my_cam.capture()

    # Grab a preview from the camera
    previewdata = my_cam.get_preview()

    # Get a list of files on the camera
    files = my_cam.files

    # Iterate over a file's content
    with open("image.jpg", "wb") as fp:
        for chunk in my_cam.files[0].iter_data():
            fp.write(chunk)

    # Get a configuration value
    image_quality = my_cam.config['capturesettings']['imagequality'].value
    # Set a configuration value
    my_cam.config['capturesettings']['imagequality'].set("JPEG Fine")

Currently only Python 2.7 (CPython and PyPy) is supported, however support
for 2.6 and 3.x is planned for the future.

.. _libgphoto2: http://www.gphoto.org/proj/libgphoto2/
.. _PyPy: http://pypy.org/
.. _cffi: https://cffi.readthedocs.org/

Requirements
------------

* libgphoto2 with development headers
* A working C compiler
* cffi

Installation
------------

From Source::

    $ pip install git+https://github.com/jbaiter/gphoto2-cffi.git

Similar projects
----------------

* `piggyphoto<https://github.com/alexdu/piggyphoto>`_: Uses ctypes
* `python-gphoto2<https://github.com/jim-easterbrook/python-gphoto2>`_: Uses SWIG
