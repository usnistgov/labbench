---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.15.1
kernelspec:
  display_name: base
  language: python
  name: python3
---

# Orientation
There are two basic use cases for `labbench`: packaging low-level code into re-usable python automation objects (writing modules), and using these packaged objects to implement an experimental procedure (writing scripts). The main goal of this section is to build a basic familiarity the recommended workflows for these processes. Further, to help make these accessible to beginning python developers, workflows demonstrate the simplified subset of advanced python concepts. 

Typical workflow for packaging low-level automation centers on:
* For each specific hardware or software:
  Writing subclasses of {py:class}`labbench.Device` (starting from backends like {py:class}`labbench.VISABackend` or {py:class}`labbench.ShellBackend`) using descriptor shortcuts
* To coordinate multiple snippets of experimental procedures:
  Writing subclasses of {py:class}`labbench.Rack` that coordinate devices and racks 

The result of these can be accumulated in a re-usable code library.

To implement experimental procedures through python scripts, a typical workflow involves:
* Usage of the {py:class}`labbench.Device` and {py:class}`labbench.Rack` objects that have already been written
* Looping across experimental conditions
* Automated data logging of measurement data and test conditions with objects like {py:class}`labbench.CSVLogger` or {py:class}`labbench.SQLiteLogger`
* A handful of utility functions, such as {py:func}`labbench.concurrently`, {py:func}`labbench.show_messages`

When re-usable components of the procedure can be identified, they can be encapsulated back into {py:class}`labbench.Rack` in a library for future use. Otherwise, this process can be mainly procedural, and less focused on writing classes.