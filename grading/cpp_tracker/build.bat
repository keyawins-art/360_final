@echo off
echo ============================================
echo  Building cashew_tracker_core C++ module
echo ============================================
echo.

pip install pybind11>=2.11 setuptools>=68 wheel
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

echo.
echo Building C++ extension...
python setup.py build_ext --inplace
if errorlevel 1 (
    echo [ERROR] C++ build failed. Make sure Visual Studio Build Tools are installed.
    echo         Install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)

echo.
echo Copying .pyd to grading directory...
copy /Y cashew_tracker_core*.pyd ..\ >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Could not copy .pyd file. You may need to copy it manually.
)

echo.
echo ============================================
echo  Build complete! Running smoke test...
echo ============================================
python -c "import cashew_tracker_core; t=cashew_tracker_core.CashewTracker(); print('[OK] cashew_tracker_core loaded successfully')"

echo.
pause
