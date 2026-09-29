import importlib
import os

from .module import EnduranceTest, EnvironmentUtils, Metric

__all__ = ["EnduranceTest", "EnvironmentUtils", "Metric"]


def filename_to_classname(filename: str):
    """Convert filename to corresponding classname."""
    parts = filename.split("_")[1:]
    classname = "".join([part.capitalize() for part in parts])
    return classname


# List all the .py files in the current directory that start with 'test_'. `test_main` holds the
# pytest tests of this loader and imports from this package, so it must not be loaded here.
module_files = sorted(
    f.removesuffix(".py")
    for f in os.listdir(os.path.dirname(os.path.abspath(__file__)))
    if f.startswith("test_") and f.endswith(".py") and f != "test_main.py"
)

# Import the corresponding class from each module
for module_file in module_files:
    module = importlib.import_module(f".{module_file}", package=__name__)
    class_name = filename_to_classname(module_file)
    executor = getattr(module, class_name, None)
    if executor is None:
        continue

    globals()[class_name] = executor
    __all__.append(class_name)
