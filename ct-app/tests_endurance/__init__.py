import importlib
import os

from .endurance_test import EnduranceTest
from .metric import Metric

__all__ = ["EnduranceTest", "Metric"]


def filename_to_classname(filename: str):
    """Convert filename to corresponding classname."""
    parts = filename.split("_")[1:]
    classname = "".join([part.capitalize() for part in parts])
    return classname


# List all the .py files in the current directory that start with 'test_'
module_files = [
    f.strip(".py")
    for f in os.listdir(os.path.dirname(os.path.abspath(__file__)))
    if f.startswith("test_") and f.endswith(".py")
]

# Import the corresponding class from each module
for module_file in module_files:
    module = importlib.import_module(f".{module_file}", package=__name__)
    class_name = filename_to_classname(module_file)

    # Import the class to the current module's namespace
    globals()[class_name] = getattr(module, class_name)

    __all__.append(class_name)
