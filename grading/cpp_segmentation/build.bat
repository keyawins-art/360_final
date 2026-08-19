@echo off
echo Building C++ Cashew Segmentation Core Extension...
python -m pip install pybind11 setuptools
python setup.py build_ext --inplace
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo SUCCESS: C++ Segmentation Extension compiled!
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo ERROR: Compilation failed. Please install Visual Studio C++ Build Tools.
    echo ========================================================
)
pause
