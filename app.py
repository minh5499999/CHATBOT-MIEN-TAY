"""Always serve the editable frontend, even with a staged backend on sys.path."""
from pathlib import Path
import importlib.util
import runpy
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
sys.path.insert(0, str(PROJECT_ROOT))

# A staging launcher may already have imported the archived frontend package.
# Replace only modules outside this frontend; keep the validated backend intact.
for name, module in list(sys.modules.items()):
    if name == "frontend" or name.startswith("frontend."):
        location = getattr(module, "__file__", None)
        if location and not Path(location).resolve().is_relative_to(FRONTEND_ROOT):
            del sys.modules[name]
if "frontend" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "frontend", FRONTEND_ROOT / "__init__.py",
        submodule_search_locations=[str(FRONTEND_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load frontend package from {FRONTEND_ROOT}")
    package = importlib.util.module_from_spec(spec)
    sys.modules["frontend"] = package
    spec.loader.exec_module(package)
else:
    sys.modules["frontend"].__path__ = [str(FRONTEND_ROOT)]

# The editable admin UI needs this helper, which older staged backends lack.
# Load only this module from the project; keep all other backend imports staged.
helper_name = "backend.chatbot.cau_hoi_cho_hoc"
if helper_name not in sys.modules:
    import backend.chatbot

    spec = importlib.util.spec_from_file_location(
        helper_name, PROJECT_ROOT / "backend/chatbot/cau_hoi_cho_hoc.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {helper_name} from {PROJECT_ROOT}")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    sys.modules[helper_name] = helper
    setattr(backend.chatbot, "cau_hoi_cho_hoc", helper)

runpy.run_path(str(FRONTEND_ROOT / "app.py"), run_name="__main__")
