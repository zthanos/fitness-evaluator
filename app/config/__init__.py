# Configuration package
# Re-export Settings and get_settings from the top-level config module
# to avoid shadowing by this package directory.
import importlib.util
import os

_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")
_spec = importlib.util.spec_from_file_location("app._config_module", _config_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

Settings = _module.Settings
get_settings = _module.get_settings
