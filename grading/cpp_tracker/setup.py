from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext
import platform

extra_args = []
if platform.system() == "Windows":
    extra_args = ["/O2"]
else:
    extra_args = ["-O2"]

ext_modules = [
    Pybind11Extension(
        "cashew_tracker_core",
        ["bindings.cpp", "cashew_tracker.cpp"],
        cxx_std=17,
        extra_compile_args=extra_args,
    ),
]

setup(
    name="cashew_tracker_core",
    version="1.1.0",
    description="High-speed C++ cashew tracker with Kalman prediction",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
