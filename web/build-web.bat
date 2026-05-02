@echo off
REM Builds the static web bundle into build\web\
REM Output can be uploaded to itch.io, GitHub Pages, Netlify Drop, etc.

set VENV_PY=C:\Users\kakrishna\.babelsglyph-web-venv\Scripts\python.exe

if not exist "%VENV_PY%" (
    echo Creating venv at C:\Users\kakrishna\.babelsglyph-web-venv ...
    python -m venv C:\Users\kakrishna\.babelsglyph-web-venv
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install pygame-ce pygbag
)

if exist build\web rmdir /s /q build\web
"%VENV_PY%" -m pygbag --build .

echo.
echo === Build complete ===
echo Output: build\web\
echo To test locally:
echo    "%VENV_PY%" -m pygbag .
echo Then open http://localhost:8000
echo.
echo To share, upload the entire build\web\ folder (or zip it) to:
echo   - itch.io  (drag-and-drop, has built-in fullscreen)
echo   - GitHub Pages
echo   - Netlify Drop  (https://app.netlify.com/drop)
