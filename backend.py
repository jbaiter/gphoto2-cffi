import logging

from cffi import FFI
ffi = FFI()

ffi.cdef("""
// gphoto2-context.h
typedef long time_t; // Dangerous, might not be portable

typedef struct _GPContext GPContext;
GPContext *gp_context_new (void);
void gp_context_ref   (GPContext *context);
void gp_context_unref (GPContext *context);
const char * gp_result_as_string (int result);

//gphoto2-camera.h
typedef struct {
    char text [32768];
} CameraText;
typedef struct {
    char name [128];
    char folder [1024];
} CameraFilePath;
typedef enum {
    GP_CAPTURE_IMAGE,
    GP_CAPTURE_MOVIE,
    GP_CAPTURE_SOUND
} CameraCaptureType;
typedef enum {
    GP_EVENT_UNKNOWN,
    GP_EVENT_TIMEOUT,
    GP_EVENT_FILE_ADDED,
    GP_EVENT_FOLDER_ADDED,
    GP_EVENT_CAPTURE_COMPLETE
} CameraEventType;
typedef struct {
        char model [128];
        int usb_vendor;
        int usb_product;
        int usb_class;
        int usb_subclass;
        int usb_protocol;
        char library [1024];
        char id [1024];
        ...;
} CameraAbilities;

typedef enum {
    GP_FILE_STATUS_NOT_DOWNLOADED,  /**< File is not downloaded. */
    GP_FILE_STATUS_DOWNLOADED   /**< File is already downloaded. */
} CameraFileStatus;

typedef enum {
    GP_FILE_INFO_NONE            = 0,   /**< \brief No fields set. */
    GP_FILE_INFO_TYPE            = 1,   /**< \brief The MIME type is set. */
    GP_FILE_INFO_SIZE            = 4,   /**< \brief The filesize is set. */
    GP_FILE_INFO_WIDTH           = 8,   /**< \brief The width is set. */
    GP_FILE_INFO_HEIGHT          = 16,  /**< \brief The height is set. */
    GP_FILE_INFO_PERMISSIONS     = 32,  /**< \brief The access permissions are set. */
    GP_FILE_INFO_STATUS      = 64,  /**< \brief The status is set (downloaded). */
    GP_FILE_INFO_MTIME       = 128, /**< \brief The modification time is set. */
    GP_FILE_INFO_ALL             = 0xFF /**< \brief All possible fields set. Internal. */
} CameraFileInfoFields;

/**
 * \brief Bitmask containing the file permission flags.
 *
 * Possible flag values of the permission entry in the file information.
 */
typedef enum {
    GP_FILE_PERM_NONE       = 0,        /**< \brief No permissions. */
    GP_FILE_PERM_READ       = 1,    /**< \brief Read permissions. */
    GP_FILE_PERM_DELETE     = 2,    /**< \brief Write permissions */
    GP_FILE_PERM_ALL        = 0xFF      /**< \brief Internal. */
} CameraFilePermissions;

typedef enum {
    GP_FILE_ACCESSTYPE_MEMORY,  /**< File is in system memory. */
    GP_FILE_ACCESSTYPE_FD,      /**< File is associated with a UNIX filedescriptor. */
    GP_FILE_ACCESSTYPE_HANDLER  /**< File is associated with a programmatic handler. */
} CameraFileAccessType;

typedef enum {
    GP_FILE_TYPE_PREVIEW,   /**< A preview of an image. */
    GP_FILE_TYPE_NORMAL,    /**< The regular normal data of a file. */
    GP_FILE_TYPE_RAW,   /**< The raw mode of a file, for instance the raw bayer data for cameras
                 * where postprocessing is done in the driver. The RAW files of modern
                 * DSLRs are GP_FILE_TYPE_NORMAL usually. */
    GP_FILE_TYPE_AUDIO, /**< The audio view of a file. Perhaps an embedded comment or similar. */
    GP_FILE_TYPE_EXIF,  /**< The embedded EXIF data of an image. */
    GP_FILE_TYPE_METADATA   /**< The metadata of a file, like Metadata of files on MTP devices. */
} CameraFileType;

typedef struct _CameraFileInfoPreview {
    CameraFileInfoFields fields;    /**< \brief Bitmask containing the set members. */
    CameraFileStatus status;    /**< \brief Status of the preview. */
    uint64_t size;          /**< \brief Size of the preview. */
    char type[64];          /**< \brief MIME type of the preview. */

    uint32_t width;         /**< \brief Width of the preview. */
    uint32_t height;        /**< \brief Height of the preview. */
} CameraFileInfoPreview;

typedef struct _CameraFileInfoFile {
    CameraFileInfoFields fields;    /**< \brief Bitmask containing the set members. */
    CameraFileStatus status;    /**< \brief Status of the file. */
    uint64_t size;          /**< \brief Size of the file. */
    char type[64];          /**< \brief MIME type of the file. */
    uint32_t width;         /**< \brief Height of the file. */
    uint32_t height;        /**< \brief Width of the file. */
    CameraFilePermissions permissions;/**< \brief Permissions of the file. */
    time_t mtime;           /**< \brief Modification time of the file. */
} CameraFileInfoFile;

typedef struct _CameraFileInfo {
    CameraFileInfoPreview preview;
    CameraFileInfoFile    file;
    ...;
} CameraFileInfo;

typedef struct _CameraFileHandler {
    int (*size) (void*priv, uint64_t *size);
    int (*read) (void*priv, unsigned char *data, uint64_t *len);
    int (*write) (void*priv, unsigned char *data, uint64_t *len);
} CameraFileHandler;

typedef ... CameraFile;
int gp_file_new            (CameraFile **file);
int gp_file_new_from_fd    (CameraFile **file, int fd);
int gp_file_new_from_handler (CameraFile **file, CameraFileHandler *handler, void*priv);
int gp_file_ref            (CameraFile *file);
int gp_file_unref          (CameraFile *file);
int gp_file_free           (CameraFile *file);

int gp_file_set_name       (CameraFile *file, const char  *name);
int gp_file_get_name       (CameraFile *file, const char **name);

int gp_file_set_mime_type  (CameraFile *file, const char  *mime_type);
int gp_file_get_mime_type  (CameraFile *file, const char **mime_type);

int gp_file_get_mtime   (CameraFile *file, time_t *mtime);

int gp_file_detect_mime_type          (CameraFile *file);
int gp_file_adjust_name_for_mime_type (CameraFile *file);
int gp_file_get_name_by_type (CameraFile *file, const char *basename, CameraFileType type, char **newname);

int gp_file_set_data_and_size (CameraFile*,       char *data,
                   unsigned long int size);
int gp_file_get_data_and_size (CameraFile*, const char **data,
                   unsigned long int *size);

typedef ... CameraWidget;

typedef enum {                                  /* Value (get/set): */
    GP_WIDGET_WINDOW,   /**< \brief Window widget
                 *   This is the toplevel configuration widget. It should likely contain multiple #GP_WIDGET_SECTION entries.
                 */
    GP_WIDGET_SECTION,  /**< \brief Section widget (think Tab) */
    GP_WIDGET_TEXT,     /**< \brief Text widget. */         /* char *       */
    GP_WIDGET_RANGE,    /**< \brief Slider widget. */           /* float        */
    GP_WIDGET_TOGGLE,   /**< \brief Toggle widget (think check box) */  /* int          */
    GP_WIDGET_RADIO,    /**< \brief Radio button widget. */     /* char *       */
    GP_WIDGET_MENU,     /**< \brief Menu widget (same as RADIO). */ /* char *       */
    GP_WIDGET_BUTTON,   /**< \brief Button press widget. */     /* CameraWidgetCallback */
    GP_WIDGET_DATE      /**< \brief Date entering widget. */        /* int          */
} CameraWidgetType;

int     gp_widget_new   (CameraWidgetType type, const char *label,
                 CameraWidget **widget);
int     gp_widget_free  (CameraWidget *widget);
int     gp_widget_ref   (CameraWidget *widget);
int     gp_widget_unref (CameraWidget *widget);

int gp_widget_append    (CameraWidget *widget, CameraWidget *child);
int     gp_widget_prepend   (CameraWidget *widget, CameraWidget *child);

int     gp_widget_count_children     (CameraWidget *widget);
int gp_widget_get_child      (CameraWidget *widget, int child_number,
                      CameraWidget **child);

/* Retrieve Widgets */
int gp_widget_get_child_by_label (CameraWidget *widget,
                      const char *label,
                      CameraWidget **child);
int gp_widget_get_child_by_id    (CameraWidget *widget, int id,
                      CameraWidget **child);
int gp_widget_get_child_by_name  (CameraWidget *widget,
                                      const char *name,
                      CameraWidget **child);
int gp_widget_get_root           (CameraWidget *widget,
                                      CameraWidget **root);
int     gp_widget_get_parent         (CameraWidget *widget,
                      CameraWidget **parent);

int gp_widget_set_value     (CameraWidget *widget, const void *value);
int gp_widget_get_value     (CameraWidget *widget, void *value);

int     gp_widget_set_name      (CameraWidget *widget, const char  *name);
int     gp_widget_get_name      (CameraWidget *widget, const char **name);

int gp_widget_set_info      (CameraWidget *widget, const char  *info);
int gp_widget_get_info      (CameraWidget *widget, const char **info);

int gp_widget_get_id    (CameraWidget *widget, int *id);
int gp_widget_get_type  (CameraWidget *widget, CameraWidgetType *type);
int gp_widget_get_label (CameraWidget *widget, const char **label);

int gp_widget_set_range (CameraWidget *range,
                 float  low, float  high, float  increment);
int gp_widget_get_range (CameraWidget *range,
                 float *min, float *max, float *increment);

int gp_widget_add_choice     (CameraWidget *widget, const char *choice);
int gp_widget_count_choices  (CameraWidget *widget);
int gp_widget_get_choice     (CameraWidget *widget, int choice_number,
                                  const char **choice);

int gp_widget_changed        (CameraWidget *widget);
int     gp_widget_set_changed    (CameraWidget *widget, int changed);

int     gp_widget_set_readonly   (CameraWidget *widget, int readonly);
int     gp_widget_get_readonly   (CameraWidget *widget, int *readonly);

typedef ... CameraList;
typedef ... Camera;
typedef ... CameraStorageInformation;
typedef ... GPPortInfoList;
typedef ... CameraAbilitiesList;
struct _GPPortInfo;
typedef struct _GPPortInfo *GPPortInfo;
int     gp_port_info_list_load (GPPortInfoList *list);
int     gp_port_info_list_new(GPPortInfoList** list);
int     gp_port_info_list_free (GPPortInfoList *list);
int     gp_port_info_list_lookup_path (GPPortInfoList *list, const char *path);
int     gp_port_info_new(GPPortInfo* info);
int     gp_port_info_list_get_info (GPPortInfoList *list, int n, GPPortInfo *info);
int gp_abilities_list_new   (CameraAbilitiesList** list);
int gp_abilities_list_load  (CameraAbilitiesList* list, GPContext* context);
int gp_abilities_list_detect(CameraAbilitiesList* list, GPPortInfoList* info_list,
                             CameraList* l, GPContext* context);
int gp_abilities_list_free (CameraAbilitiesList *list);

int gp_list_count (CameraList *list);
int gp_list_get_name (CameraList *list, int index, const char **name);
int gp_list_get_value (CameraList *list, int index, const char **value);
int gp_list_free (CameraList *list);

int gp_list_new             (CameraList **list);
int gp_camera_new           (Camera **camera);
int gp_camera_get_abilities (Camera *camera, CameraAbilities *abilities);
int gp_camera_autodetect    (CameraList *list, GPContext *context);
int gp_camera_init          (Camera *camera, GPContext *context);
int gp_camera_exit          (Camera *camera, GPContext *context);
int gp_camera_ref           (Camera *camera);
int gp_camera_unref         (Camera *camera);
int gp_camera_free          (Camera *camera);
int gp_camera_set_port_info (Camera *camera, GPPortInfo info);
int gp_camera_get_config    (Camera *camera, CameraWidget **window,
                             GPContext *context);
int gp_camera_set_config    (Camera *camera, CameraWidget  *window,
                             GPContext *context);
int gp_camera_get_summary   (Camera *camera, CameraText *summary,
                             GPContext *context);
int gp_camera_get_manual    (Camera *camera, CameraText *manual,
                             GPContext *context);
int gp_camera_get_about     (Camera *camera, CameraText *about,
                             GPContext *context);
int gp_camera_capture       (Camera *camera, CameraCaptureType type,
                             CameraFilePath *path, GPContext *context);
int gp_camera_trigger_capture (Camera *camera, GPContext *context);
int gp_camera_capture_preview (Camera *camera, CameraFile *file,
                               GPContext *context);
int gp_camera_wait_for_event  (Camera *camera, int timeout,
                               CameraEventType *eventtype, void **eventdata,
                               GPContext *context);
int gp_camera_get_storageinfo (Camera *camera, CameraStorageInformation**,
                               int *, GPContext *context);

int gp_camera_folder_list_files   (Camera *camera, const char *folder,
                                   CameraList *list, GPContext *context);
int gp_camera_folder_list_folders (Camera *camera, const char *folder,
                                   CameraList *list, GPContext *context);
int gp_camera_folder_delete_all   (Camera *camera, const char *folder,
                                   GPContext *context);
int gp_camera_folder_put_file     (Camera *camera, const char *folder,
                                   const char *filename, CameraFileType type,
                                   CameraFile *file, GPContext *context);
int gp_camera_folder_make_dir     (Camera *camera, const char *folder,
                                   const char *name, GPContext *context);
int gp_camera_folder_remove_dir   (Camera *camera, const char *folder,
                                   const char *name, GPContext *context);

int gp_camera_file_get_info   (Camera *camera, const char *folder,
                               const char *file, CameraFileInfo *info,
                               GPContext *context);
int gp_camera_file_set_info   (Camera *camera, const char *folder,
                               const char *file, CameraFileInfo info,
                               GPContext *context);
int gp_camera_file_get        (Camera *camera, const char *folder,
                               const char *file, CameraFileType type,
                               CameraFile *camera_file, GPContext *context);
int gp_camera_file_read       (Camera *camera, const char *folder, const char *file,
                               CameraFileType type,
                               uint64_t offset, char *buf, uint64_t *size,
                               GPContext *context);
int gp_camera_file_delete     (Camera *camera, const char *folder,
                               const char *file, GPContext *context);

typedef enum {
    GP_LOG_ERROR = 0,
    GP_LOG_VERBOSE = 1,
    GP_LOG_DEBUG = 2,
    GP_LOG_DATA = 3
} GPLogLevel;
typedef void(*  GPLogFunc )(GPLogLevel level, const char *domain, const char *str, void *data);
int gp_log_add_func (GPLogLevel level, GPLogFunc func, void *data);

typedef struct {
    unsigned long  size;
    char*          data;
} StreamingBuffer;
""")

_lib = ffi.verify("""
#include "gphoto2/gphoto2-context.h"
#include "gphoto2/gphoto2-camera.h"
#include <time.h>

typedef struct {
    unsigned long  size;
    char*          data;
} StreamingBuffer;
""", libraries=["gphoto2"])

#: Mapping from libgphoto2 logging levels to Python logging levels
LOG_LEVELS = {
    _lib.GP_LOG_ERROR:   logging.ERROR,
    _lib.GP_LOG_VERBOSE: logging.INFO,
    _lib.GP_LOG_DEBUG:   logging.DEBUG
}

#: Root logger that all other libgphoto2 loggers are children of
_root_logger = logging.getLogger("libgphoto2")

@ffi.callback("void(GPLogLevel, const char*, const char*, void*)")
def logging_callback(level, domain, message, data):
    """ Callback that outputs libgphoto2's logging message via Python's
        standard logging facilities.

    :param level:   libgphoto2 logging level
    :param domain:  component the message originates from
    :param message: logging message
    :param data:    Other data in the logging record (unused)
    """
    domain = ffi.string(domain)
    message = ffi.string(message)
    logger = _root_logger.getChild(domain)

    #FIXME: This has got to be the weirdest bug ever... Removing this statement
    #       increases the number of calls to this callback manifold and
    #       subsequently more than doubles the runtime in my benchmarks.
    #       It does not matter which file is opened, and you don't have to
    #       write anything to it, you don't even have to close it
    #       (though this is done here anyway...).
    open("/dev/null").close()

    if level not in LOG_LEVELS:
        return
    logger.log(LOG_LEVELS[level], message)

# Register our logging callback
_lib.gp_log_add_func(_lib.GP_LOG_DEBUG, logging_callback, ffi.NULL)


class GPhoto2Error(Exception):
    def __init__(self, errcode):
        """ Generic exception type for all errors that originate in libgphoto2.

        Converts libgphoto2 error codes to their human readable message.

        :param errcode:     The libgphoto2 error code
        """
        self.error_code = errcode
        msg = ffi.string(lib.gp_result_as_string(errcode))
        super(GPhoto2Error, self).__init__(msg)


def check_error(rval):
    """ Check a return value for a libgphoto2 error. """
    if rval != 0:
        raise GPhoto2Error(rval)


class LibraryWrapper(object):
    NO_ERROR_CHECK = (
        "gp_log_add_func",
        "gp_context_new",
        "gp_list_count",
        "gp_widget_count_choices",
        "gp_widget_count_children",
        "gp_result_as_string",
        # This one's a bit nasty, since its return value can be both an index
        # *or* an error code...
        "gp_port_info_list_lookup_path"
    )
    def __init__(self, to_wrap):
        """ Wrapper around our libgphoto2 FFI object.

        Wraps functions inside an anonymous function that checks the inner
        function's return code for libgphoto2 errors and throws a
        :py:class:`GPhoto2Error` if needed.

        :param to_wrap:     FFI library to wrap
        """
        self._wrapped = to_wrap

    def __getattribute__(self, name):
        # Use the parent class' implementation to avoid infinite recursion
        val = getattr(object.__getattribute__(self, '_wrapped'), name)
        blacklist = object.__getattribute__(self, 'NO_ERROR_CHECK')
        if not isinstance(val, int) and name not in blacklist:
            return lambda *a, **kw: check_error(val(*a, **kw))
        else:
            return val

#: The wrapped library
lib = LibraryWrapper(_lib)

#: Mapping from libgphoto2 file type constants to human-readable strings
FILE_TYPES = {
    'normal': _lib.GP_FILE_TYPE_NORMAL,
    'exif': _lib.GP_FILE_TYPE_EXIF,
    'metadata': _lib.GP_FILE_TYPE_METADATA,
    'preview': _lib.GP_FILE_TYPE_PREVIEW,
    'raw': _lib.GP_FILE_TYPE_RAW,
    'audio': _lib.GP_FILE_TYPE_AUDIO
}

#: Mapping from libgphoto2 types to their appropriate constructor functions
CONSTRUCTORS = {
    "Camera":       lib.gp_camera_new,
    "GPPortInfo":   lib.gp_port_info_new,
    "CameraList":   lib.gp_list_new,
    "CameraAbilitiesList": lib.gp_abilities_list_new,
    "GPPortInfoList": lib.gp_port_info_list_new,
}

#: Mapping from libgphoto2 widget type constants to human-readable strings
WIDGET_TYPES = {
    lib.GP_WIDGET_MENU:     "selection",
    lib.GP_WIDGET_RADIO:    "selection",
    lib.GP_WIDGET_TEXT:     "text",
    lib.GP_WIDGET_RANGE:    "range",
    lib.GP_WIDGET_DATE:     "date",
    lib.GP_WIDGET_TOGGLE:   "toggle",
    lib.GP_WIDGET_WINDOW:   "window",
    lib.GP_WIDGET_SECTION:  "section",
}

def get_string(cfunc, *args):
    """ Call a C function and return its return value as a Python string.

    :param cfunc:   C function to call
    :param args:    Arguments to call function with
    :rtype:         str
    """
    cstr = get_ctype("const char**", cfunc, *args)
    return ffi.string(cstr) if cstr else None


def get_ctype(rtype, cfunc, *args):
    """ Call a C function that takes a pointer as its last argument and
        return the C object that it contains after the function has finished.

    :param rtype:   C data type is filled by the function
    :param cfunc:   C function to call
    :param args:    Arguments to call function with
    :return:        A pointer to the specified data type
    """
    val_p = ffi.new(rtype)
    args = args + (val_p,)
    cfunc(*args)
    return val_p[0]


def new_gp_object(typename):
    """ Create an indirect pointer to a GPhoto2 type, call its matching
        constructor function and return the pointer to it.

    :param typename:    Name of the type to create.
    :return:            A pointer to the specified data type.
    """
    obj_p = ffi.new("{0}**".format(typename))
    CONSTRUCTORS[typename](obj_p)
    return obj_p[0]
