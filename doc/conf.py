# This software was developed by employees of the National Institute of
# Standards and Technology (NIST), an agency of the Federal Government.
# Pursuant to title 17 United States Code Section 105, works of NIST employees
# are not subject to copyright protection in the United States and are
# considered to be in the public domain. Permission to freely use, copy,
# modify, and distribute this software and its documentation without fee is
# hereby granted, provided that this notice and disclaimer of warranty appears
# in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
# EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
# THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
# INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
# SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE. IN NO EVENT
# SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
# INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM,
# OR IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON
# WARRANTY, CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED
# BY PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import builtins

import numpy as np
import toml
from sphinx.domains.python import PythonDomain
from sphinx.ext import autodoc
from pathlib import Path

import labbench as lb

# load and validate the project definition from pyproject.toml
project_info = toml.load("../pyproject.toml")
missing_fields = {'name', 'version'} - set(project_info["project"].keys())
if len(missing_fields) > 0:
    raise ValueError(f'fields {missing_fields} missing from [project] in pyproject.toml')

# Location of the API source code
autoapi_dirs = [f'../{project_info["project"]["name"]}']
if not Path(autoapi_dirs[0]).exists():
    raise IOError(f'did not find source directory at expected path "{autoapi_dirs[0]}"')

# -------- General information about the project ------------------
project = project_info["project"]["name"]

if 'authors' in project_info["project"]:
    authors = [author["name"] for author in project_info["project"]["authors"]]
    author_groups = [
        ", ".join(a) for a in np.array_split(authors, np.ceil(len(authors) / 3))
    ]
else:
    author_groups = []

copyright = (
    "United States government work, not subject to copyright in the United States"
)
version = release = project_info["project"]["version"]
language = "en"

# ------------- base sphinx setup -------------------------------
extensions = [
    #
    # base sphinx capabilities
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    #
    # handles notebooks
    "myst_nb",
    #
    # numpy- and google-style docstrings
    "sphinx.ext.napoleon",
    #
    # for code that will be hosted on github pages (or NIST pages)
    "sphinx.ext.githubpages",
]

exclude_patterns = [
    "_build",
    "jupyter_execute",
    f"{project}/_version.py",
    "**.ipynb_checkpoints",
    "setup*",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# Force handlers
source_suffix = {
    ".rst": "restructuredtext",
    ".ipynb": "myst-nb",
    ".md": "myst-nb",
}

autodoc_mock_imports = []

# The master toctree document.
master_doc = "index"


# ------------------ myst_nb ---------------------------------------
# For debug: uncomment this
# nb_execution_mode = "off"

# merge consecutive notebook logger outputs into shared text box
nb_merge_streams = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "default"
todo_include_todos = False

# ------------- HTML output ----------------------------------------
html_theme = "pyramid"
html_title = f"{project}"
html_static_path = ["_static"]
html_use_index = False
html_show_sphinx = False
htmlhelp_basename = project + "doc"

# ------ LaTeX output ---------------------------------------------
latex_elements = {
    "papersize": "letterpaper",
    "pointsize": "10pt",
    "preamble": r"\setcounter{tocdepth}{5}",
}

latex_documents = [
    (
        master_doc,
        "{}-api.tex".format(project),
        r"API reference for {}".format(project),
        r", \\".join(author_groups),
        "manual",
    ),
]
latex_show_urls = "False"
latex_domain_indices = False

# ------------- misc ---------------------------------------------
mathjax_config = {
    "TeX": {"equationNumbers": {"autoNumber": "AMS", "useLabelIds": True}},
}


# -- Dynamic processing to get the library introspection right ----
class PatchedPythonDomain(PythonDomain):
    """avoid clobbering references to builtins"""

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        # ref: https://github.com/sphinx-doc/sphinx/issues/3866#issuecomment-311181219
        exclude_targets = set(dir(builtins))

        if "refspecific" in node:
            if not node["refspecific"] and node["reftarget"] in exclude_targets:
                del node["refspecific"]

        return super(PatchedPythonDomain, self).resolve_xref(
            env, fromdocname, builder, typ, target, node, contnode
        )


def process_docstring(app, what, name, obj, options, lines):
    if isinstance(obj, lb._traits.Trait):
        lines.append(obj.doc(as_argument=True, anonymous=True))


class AttributeDocumenter(autodoc.AttributeDocumenter):
    """Document lb.value trait class attributes in the style of python class attributes"""

    @staticmethod
    def _is_lb_value(obj):
        return (
            isinstance(obj, lb._traits.Trait)
            and obj.role == lb._traits.Trait.ROLE_VALUE
        )

    @classmethod
    def can_document_member(cls, member, membername: str, isattr: bool, parent) -> bool:
        if isinstance(parent, autodoc.ClassDocumenter):
            if cls._is_lb_value(member):
                return True

        return super().can_document_member(member, membername, isattr, parent)

    def add_directive_header(self, sig: str) -> None:
        if not self._is_lb_value(self.object):
            return super().add_directive_header(sig)

        super().add_directive_header(sig)
        sourcename = self.get_sourcename()

        # if signature.return_annotation is not Parameter.empty:
        if self.config.autodoc_typehints_format == "short":
            objrepr = autodoc.stringify_annotation(self.object.type, "smart")
        else:
            objrepr = autodoc.stringify_annotation(
                self.object.type, "fully-qualified-except-typing"
            )

        self.add_line("   :type: " + objrepr, sourcename)


class PropertyDocumenter(autodoc.PropertyDocumenter):
    """Document lb.property traits in the style of python properties"""

    @staticmethod
    def _is_lb_property(obj):
        return (
            isinstance(obj, lb._traits.Trait)
            and obj.role == lb._traits.Trait.ROLE_PROPERTY
        )

    @classmethod
    def can_document_member(cls, member, membername: str, isattr: bool, parent) -> bool:
        if isinstance(parent, autodoc.ClassDocumenter):
            if cls._is_lb_property(member):
                return True
        return super().can_document_member(member, membername, isattr, parent)

    def import_object(self, raiseerror: bool = False) -> bool:
        """Check the exisitence of uninitialized instance attribute when failed to import
        the attribute."""
        autodoc.ClassLevelDocumenter.import_object(self, raiseerror)
        if self._is_lb_property(self.object):
            self.isclassmethod = False
            return True
        else:
            return super().import_object(raiseerror)

    def add_directive_header(self, sig: str) -> None:
        if not self._is_lb_property(self.object):
            return super().add_directive_header(sig)

        super().add_directive_header(sig)
        sourcename = self.get_sourcename()

        # if signature.return_annotation is not Parameter.empty:
        if self.config.autodoc_typehints_format == "short":
            objrepr = autodoc.stringify_annotation(self.object.type, "smart")
        else:
            objrepr = autodoc.stringify_annotation(
                self.object.type, "fully-qualified-except-typing"
            )

        self.add_line("   :type: " + objrepr, sourcename)

    def format_args(self, **kwargs) -> str:
        if not self._is_lb_property(self.object):
            return super().format_args(**kwargs)
        else:
            self.env.app.emit("autodoc-before-process-signature", self.object, False)
            return super().format_args(**kwargs)


def setup(app):
    app.add_domain(PatchedPythonDomain, override=True)
    app.add_autodocumenter(PropertyDocumenter, override=True)
    app.add_autodocumenter(AttributeDocumenter)
    app.connect("autodoc-process-docstring", process_docstring)
