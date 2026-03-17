import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if 'pythonjsonlogger' not in sys.modules:
    jsonlogger_module = types.ModuleType('pythonjsonlogger')
    jsonlogger_submodule = types.ModuleType('pythonjsonlogger.jsonlogger')

    class JsonFormatter:  # pragma: no cover - test bootstrap shim
        def __init__(self, *args, **kwargs) -> None:
            pass

        def format(self, record):  # noqa: ANN001 - logging interface
            return record.getMessage()

    jsonlogger_submodule.JsonFormatter = JsonFormatter
    jsonlogger_module.jsonlogger = jsonlogger_submodule
    sys.modules['pythonjsonlogger'] = jsonlogger_module
    sys.modules['pythonjsonlogger.jsonlogger'] = jsonlogger_submodule
