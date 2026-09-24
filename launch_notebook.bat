@echo off
REM One-click launcher for LidarChangeNotebook.ipynb
REM Replaces the repeated per-session steps:
REM   conda activate lidarchange312 / cd CloudComPy312 / envCloudComPy.bat / jupyter notebook
REM One-time setup (env creation, ipykernel registration, ctest) is NOT redone here -
REM see the Windows section of README.md if you haven't done that yet.

setlocal EnableDelayedExpansion
set "PROJECT_ROOT=%~dp0"
set "ENV_NAME=lidarchange312"

REM ---------------------------------------------------------------------------
REM Find the conda installation. Checked in this order:
REM   1. CONDA_ROOT, if you've set it yourself (to force a specific install)
REM   2. CONDA_EXE, which conda sets in shells where it's initialized
REM   3. the usual install folders for Miniforge / Miniconda / Anaconda
REM   4. a conda.exe found on PATH
REM ---------------------------------------------------------------------------
if defined CONDA_ROOT (
    if exist "%CONDA_ROOT%\Scripts\activate.bat" goto :found_conda
    echo CONDA_ROOT is set to "%CONDA_ROOT%", but no conda installation was found there - searching elsewhere.
)

set "CONDA_ROOT="

if defined CONDA_EXE (
    for %%I in ("%CONDA_EXE%\..\..") do set "CONDA_ROOT=%%~fI"
    if exist "!CONDA_ROOT!\Scripts\activate.bat" goto :found_conda
)

for %%D in (
    "%USERPROFILE%\miniforge3"
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\anaconda3"
    "%LOCALAPPDATA%\miniforge3"
    "%LOCALAPPDATA%\miniconda3"
    "%LOCALAPPDATA%\anaconda3"
    "%ProgramData%\miniforge3"
    "%ProgramData%\miniconda3"
    "%ProgramData%\anaconda3"
    "C:\miniforge3"
    "C:\miniconda3"
    "C:\anaconda3"
) do (
    if exist "%%~D\Scripts\activate.bat" (
        set "CONDA_ROOT=%%~D"
        goto :found_conda
    )
)

for /f "delims=" %%C in ('where conda.exe 2^>nul') do (
    for %%I in ("%%C\..\..") do set "CONDA_ROOT=%%~fI"
    if exist "!CONDA_ROOT!\Scripts\activate.bat" goto :found_conda
)

echo Could not find a conda installation (Miniforge, Miniconda or Anaconda).
echo If conda is installed somewhere unusual, set CONDA_ROOT to its folder first, e.g.:
echo     set CONDA_ROOT=D:\tools\miniforge3
echo and run this file again from that same command prompt.
pause
exit /b 1

:found_conda
echo Using conda at: %CONDA_ROOT%

if not exist "%PROJECT_ROOT%CloudComPy312\envCloudComPy.bat" (
    echo CloudComPy was not found at "%PROJECT_ROOT%CloudComPy312".
    echo Unzip the CloudComPy release into this project folder as CloudComPy312 - see the Windows section of README.md.
    pause
    exit /b 1
)

call "%CONDA_ROOT%\Scripts\activate.bat" %ENV_NAME%
if errorlevel 1 (
    echo Failed to activate conda environment "%ENV_NAME%" using the conda at %CONDA_ROOT%.
    echo Has it been created yet? See the one-time setup in the Windows section of README.md.
    pause
    exit /b 1
)

REM Called by full path, not "cd + call envCloudComPy.bat": Windows can be set
REM (NoDefaultCurrentDirectoryInExePath) to not look in the current folder.
REM "skip" arg bypasses checkenv.py's redundant "import cloudComPy" -
REM Jupyter's own kernel imports it again anyway once the notebook opens.
call "%PROJECT_ROOT%CloudComPy312\envCloudComPy.bat" skip

cd /d "%PROJECT_ROOT%"
jupyter notebook "LidarChangeNotebook.ipynb"

endlocal
