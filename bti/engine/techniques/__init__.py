"""Technique renderers, one module per family. Every module in this package is imported automatically
(a new file needs no edit here or anywhere else); importing the package registers every renderer."""
import importlib
import pkgutil

for _m in sorted(m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_")):
    importlib.import_module(__name__ + "." + _m)
