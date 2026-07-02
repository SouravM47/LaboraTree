"""Laboratree Labs — each Lab is an isolated plug-in/plug-out module.

Sub-packages register their components with the global registry at import time; the
`core.registry.discover()` walker imports them all on startup.
"""
