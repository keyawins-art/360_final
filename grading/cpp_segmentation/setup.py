from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext
import os

ext_modules = [
    Pybind11Extension(
        "cashew_segmentation_core",
        ["bindings.cpp", "cashew_segmentation.cpp"],
        cxx_std=17,
        extra_compile_args=["/O2"] if os.name == "nt" else ["-O3"],
    ),
]

setup(
    name="cashew_segmentation_core",
    version="1.0.0",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
