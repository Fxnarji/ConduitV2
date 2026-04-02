@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   Conduit ^| PyInstaller Build
echo ========================================
echo.

REM ------------------------------------------------------------------
REM Activate virtual environment
REM ------------------------------------------------------------------
if exist "venv\Scripts\activate.bat" (
    echo [1/3] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [WARN] No venv\ found — using system Python.
    echo        Run: python -m venv venv ^&^& venv\Scripts\pip install -e .[dev]
    echo.
)

REM ------------------------------------------------------------------
REM Clean previous build artefacts
REM ------------------------------------------------------------------
echo [2/3] Cleaning previous build...
if exist "dist\Conduit.exe" del /q "dist\Conduit.exe"
if exist "build\Conduit"    rmdir /s /q "build\Conduit"

REM ------------------------------------------------------------------
REM Build
REM
REM  --onefile        single .exe, extracts to %TEMP%\_%MEI... at runtime
REM  --windowed       no console window
REM  --add-data       bundle data files (src;dest inside the extraction dir)
REM
REM  Data paths use semicolons on Windows: "source;dest_in_bundle"
REM  The dest paths must match what the code expects inside sys._MEIPASS:
REM    resources\templates  -> resources/templates    (main_window._get_templates_dir)
REM    conduit\ui\icons     -> conduit/ui/icons       (file_item._ICON_DIR)
REM    conduit\ui           -> conduit/ui             (theme_loader._STYLESHEET_PATH)
REM ------------------------------------------------------------------
echo [3/3] Running PyInstaller...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "Conduit" ^
    --add-data "resources\templates;resources\templates" ^
    --add-data "src\conduit\ui\icons;conduit\ui\icons" ^
    --add-data "src\conduit\ui\stylesheet.qss;conduit\ui" ^
    src\conduit\__main__.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================
    echo   Build successful!
    echo   Output: dist\Conduit.exe
    echo ========================================
) else (
    echo ========================================
    echo   Build FAILED  ^(exit code %ERRORLEVEL%^)
    echo ========================================
)

endlocal
pause
