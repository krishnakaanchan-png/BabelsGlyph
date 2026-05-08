@echo off
REM Build a Windows distributable folder: dist\BabelsGlyph\BabelsGlyph.exe
REM (--onedir avoids the runtime self-extraction step that some
REM  antivirus tools mis-flag, which can cause "Bad Image / 0xc0e90002"
REM  errors on the extracted python3xx.dll.)
REM Run from the project root. Optionally activate the venv first.

setlocal
if exist .venv\Scripts\pyinstaller.exe (
    set "PYI=.venv\Scripts\pyinstaller.exe"
) else (
    set "PYI=pyinstaller"
)

REM Clean previous artifacts so a stale --onefile build doesn't linger.
if exist dist\BabelsGlyph.exe del /q dist\BabelsGlyph.exe
if exist dist\BabelsGlyph rmdir /s /q dist\BabelsGlyph
if exist build\BabelsGlyph rmdir /s /q build\BabelsGlyph
if exist BabelsGlyph.spec del /q BabelsGlyph.spec

%PYI% --noconfirm --onedir --windowed --name BabelsGlyph ^
      --add-data "assets;assets" ^
      main.py
if errorlevel 1 (
    echo.
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete.
echo Run:    dist\BabelsGlyph\BabelsGlyph.exe
echo Share:  zip the entire dist\BabelsGlyph folder.
endlocal
