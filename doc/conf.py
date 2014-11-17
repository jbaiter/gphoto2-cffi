# -*- coding: utf-8 -*-
import sys

sys.path.insert(0, '../')


class Mock(object):
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    @classmethod
    def __getattr__(cls, name):
        print "Getting mock: ", name
        if name in ('__file__', '__path__'):
            return '/dev/null'
        # Special case for CFFI
        elif name in ('FFI', 'Verifier'):
            return Mock()
        elif name[0] == name[0].upper():
            mockType = type(name, (), {})
            mockType.__module__ = __name__
            return mockType
        else:
            return Mock()

MOCK_MODULES = ['cffi', 'cffi.verifier']
for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode']

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

project = u'gphoto2-cffi'
copyright = u'2014, Johannes Baiter'
version = '0.1'
release = '0.1'

exclude_patterns = ['_build']
pygments_style = 'sphinx'

html_static_path = ['_static']
htmlhelp_basename = 'gphoto2-cffidoc'

latex_elements = {
    'preamble': '',
}

latex_documents = [
    ('index', 'gphoto2-cffi.tex', u'gphoto2-cffi Documentation',
     u'Johannes Baiter', 'manual'),
]

man_pages = [
    ('index', 'gphoto2-cffi', u'gphoto2-cffi Documentation',
     [u'Johannes Baiter'], 1)
]

texinfo_documents = [
    ('index', 'gphoto2-cffi', u'gphoto2-cffi Documentation',
     u'Johannes Baiter', 'gphoto2-cffi', 'One line description of project.',
     'Miscellaneous'),
]
