import builtins
from pathlib import Path
from typing import Union

import numpy as np
import toml
from sphinx.domains.python import PythonDomain
from sphinx.ext import autodoc

import labbench as lb

lb.util.force_full_traceback(False)

# load and validate the project definition from pyproject.toml
project_info = toml.load('../pyproject.toml')
missing_fields = {'name', 'version'} - set(project_info['project'].keys())
if len(missing_fields) > 0:
    raise ValueError(
        f'fields {missing_fields} missing from [project] in pyproject.toml'
    )

# Location of the API source code
autoapi_dirs = [f'../src/{project_info["project"]["name"]}']
if not Path(autoapi_dirs[0]).exists():
    raise OSError(f'did not find source directory at expected path "{autoapi_dirs[0]}"')

# -------- General information about the project ------------------
project = project_info['project']['name']

if 'authors' in project_info['project']:
    authors = [author['name'] for author in project_info['project']['authors']]
    author_groups = [
        ', '.join(a) for a in np.array_split(authors, np.ceil(len(authors) / 3))
    ]
else:
    author_groups = []

copyright = (
    'United States government work, not subject to copyright in the United States'
)
version = release = lb.__version__
language = 'en'

# ------------- base sphinx setup -------------------------------
extensions = [
    #
    # base sphinx capabilities
    'sphinx.ext.autodoc',
    'sphinx.ext.coverage',
    #
    # handles notebooks
    'myst_nb',
    #
    # numpy- and google-style docstrings
    'sphinx.ext.napoleon',
    #
    # for code that will be hosted on github pages (or NIST pages)
    'sphinx.ext.githubpages',
]

exclude_patterns = [
    '_build',
    'jupyter_execute',
    f'{project}/_version.py',
    '**.ipynb_checkpoints',
    'setup*',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# Force handlers
source_suffix = {
    '.rst': 'restructuredtext',
    '.ipynb': 'myst-nb',
    '.md': 'myst-nb',
}

autodoc_mock_imports = []

# The master toctree document.
master_doc = 'index'


# ------------------ myst_nb ---------------------------------------
# For debug: uncomment this
# nb_execution_mode = "off"

# merge consecutive notebook logger outputs into shared text box
nb_merge_streams = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'default'
todo_include_todos = False

# ------------- HTML output ----------------------------------------
html_theme = 'pyramid'
html_title = f'{project}'
html_static_path = ['_static']
html_use_index = False
html_show_sphinx = False
html_theme_options = {'sidebarwidth': '28em'}
htmlhelp_basename = project + 'doc'

# ------ LaTeX output ---------------------------------------------
latex_elements = {
    'papersize': 'letterpaper',
    'pointsize': '10pt',
    'preamble': r'\setcounter{tocdepth}{5}',
}

latex_documents = [
    (
        master_doc,
        f'{project}-api.tex',
        rf'API reference for {project}',
        r', \\'.join(author_groups),
        'manual',
    ),
]
latex_show_urls = 'False'
latex_domain_indices = False

# ------------- misc ---------------------------------------------
mathjax_config = {
    'TeX': {'equationNumbers': {'autoNumber': 'AMS', 'useLabelIds': True}},
}


# -- Dynamic processing to get the library introspection right ----
class PatchedPythonDomain(PythonDomain):
    """avoid clobbering references to builtins"""

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        # ref: https://github.com/sphinx-doc/sphinx/issues/3866#issuecomment-311181219
        exclude_targets = set(dir(builtins))

        if 'refspecific' in node:
            if not node['refspecific'] and node['reftarget'] in exclude_targets:
                del node['refspecific']

        return super(PatchedPythonDomain, self).resolve_xref(
            env, fromdocname, builder, typ, target, node, contnode
        )


class AttributeDocumenter(autodoc.AttributeDocumenter):
    """Document lb.value trait class attributes in the style of python class attributes"""

    @classmethod
    def can_document_member(cls, member, membername: str, isattr: bool, parent) -> bool:
        if isinstance(parent, autodoc.ClassDocumenter):
            if isinstance(member, lb.paramattr.value.Value):
                return True
        return super().can_document_member(member, membername, isattr, parent)

    def add_directive_header(self, sig: str) -> None:
        if isinstance(self.object, lb.paramattr.value.Value):
            # if self.object.only:
            #     type_ = Union[*self.object.only, *list()]
            # else:
            type_ = self.object._type
            if self.object.allow_none:
                type_ = Union[type_, None]

            self.parent.__annotations__[self.object.name] = type_
            self.options.no_value = True
            sig = ''

        super().add_directive_header(sig)

        if not isinstance(self.object, lb.paramattr.value.Value):
            return

        sourcename = self.get_sourcename()
        if self.object.default is not lb.Undefined:
            defaultrepr = autodoc.object_description(self.object.default)
            self.add_line('   :value: ' + defaultrepr, sourcename)

    def get_doc(self):
        if isinstance(self.object, lb.paramattr.value.Value):
            self.config.autodoc_inherit_docstrings = False
            tab_width = self.directive.state.document.settings.tab_width
            docstring = self.object.doc() + '\n'
            return [autodoc.prepare_docstring(docstring, tab_width)]
        else:
            return super().get_doc()


class PropertyDocumenter(autodoc.PropertyDocumenter):
    """Document lb.property traits in the style of python properties"""

    @classmethod
    def can_document_member(cls, member, membername: str, isattr: bool, parent) -> bool:
        if isinstance(parent, autodoc.ClassDocumenter):
            if isinstance(member, lb.paramattr.property.Property):
                return True
        return super().can_document_member(member, membername, isattr, parent)

    def import_object(self, raiseerror: bool = False) -> bool:
        """Check the exisitence of uninitialized instance attribute when failed to import
        the attribute."""
        autodoc.ClassLevelDocumenter.import_object(self, raiseerror)
        if isinstance(self.object, lb.paramattr.property.Property):
            self.isclassmethod = False
            return True
        else:
            return super().import_object(raiseerror)

    def add_directive_header(self, sig: str) -> None:
        start_directives = set(self.directive.result)
        if isinstance(self.object, lb.paramattr.property.Property):
            type_ = self.object._type
            if self.object.allow_none:
                type_ = Union[type_, None]
            self.parent.__annotations__[self.object.name] = type_
            self.options.no_value = True
            sig = ''

        super().add_directive_header(sig)

        sourcename = self.get_sourcename()

        # if signature.return_annotation is not Parameter.empty:
        new_directives = set(self.directive.result) - start_directives
        if not any(':type:' in line for line in new_directives):
            # if signature.return_annotation is not Parameter.empty:
            if self.config.autodoc_typehints_format == 'short':
                typerepr = autodoc.stringify_annotation(self.object._type, 'smart')
            else:
                typerepr = autodoc.stringify_annotation(
                    self.object._type, 'fully-qualified-except-typing'
                )
            self.add_line('   :type: ' + typerepr, sourcename)

    def format_args(self, **kwargs) -> str:
        if isinstance(self.object, lb.paramattr.property.Property):
            return super().format_args(**kwargs)
        else:
            self.env.app.emit('autodoc-before-process-signature', self.object, False)
            return super().format_args(**kwargs)

    def get_doc(self):
        if isinstance(self.object, lb.paramattr.property.Property):
            self.config.autodoc_inherit_docstrings = False
            tab_width = self.directive.state.document.settings.tab_width
            docstring = self.object.doc() + '\n'
            return [autodoc.prepare_docstring(docstring, tab_width)]
        else:
            return super().get_doc()


class ClassDocumenter(autodoc.ClassDocumenter):
    def get_object_members(self, want_all: bool):
        _, members = super().get_object_members(True)
        members = self.filter_members(members, want_all)

        return super().get_object_members(True)


def setup(app):
    app.add_domain(PatchedPythonDomain, override=True)
    app.add_autodocumenter(PropertyDocumenter, override=True)
    app.add_autodocumenter(AttributeDocumenter, override=True)
    app.add_autodocumenter(ClassDocumenter, override=True)
