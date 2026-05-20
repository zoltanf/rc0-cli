"""PyInstaller hook for the rc0 package.

Subcommand modules under ``rc0.commands`` are imported lazily by
``rc0.app.LazyTyperGroup`` to keep cold startup under 200ms. Static analysis
cannot follow ``importlib.import_module`` strings, so we tell PyInstaller to
bundle every submodule of ``rc0.commands`` explicitly.
"""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("rc0.commands")
