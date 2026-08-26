@echo off
REM Setup script to initialize git repo and push to GitHub
REM Run this from S:\pcb-designs directory

set REPO_URL=https://github.com/mr-sanjai-offl/PCB-Designs.git
set BRANCH=main

echo === PCB Designs Repository Setup ===
echo Repository: %REPO_URL%
echo.

REM Check if already a git repo
if exist ".git" (
    echo Already a git repository. Checking remote...
    git remote get-url origin 2>nul | findstr /C:"mr-sanjai-offl/PCB-Designs" >nul
    if %errorlevel% equ 0 (
        echo Remote already configured correctly.
    ) else (
        echo Updating remote URL...
        git remote set-url origin %REPO_URL%
    )
) else (
    echo Initializing git repository...
    git init
    git branch -M %BRANCH%
    git remote add origin %REPO_URL%
)

REM Add all files
echo Adding files...
git add -A

REM Check status
echo.
echo Git status:
git status

REM Commit if there are changes
git diff --staged --quiet
if %errorlevel% equ 1 (
    echo.
    echo Committing changes...
    git commit -m "Initial commit: PCB Designs repository with automation workflow

- Added AC_to_DC_Converter project
- Added GitHub Actions workflow for automatic README generation
- Added .gitignore for KiCad files
- Automation includes:
  * KiCad file parsing for component tables
  * PCB dimension extraction
  * kicad-render integration for 3D renders and GIFs
  * Main README with project table
  * Execution logging to automation-log.json"
) else (
    echo No changes to commit.
)

REM Push to GitHub
echo.
echo Pushing to GitHub...
echo Note: You may need to authenticate with GitHub (token or SSH key)
git push -u origin %BRANCH%

echo.
echo === Setup Complete ===
echo Repository pushed to: %REPO_URL%
echo.
echo Next steps:
echo 1. Go to https://github.com/mr-sanjai-offl/PCB-Designs/actions
echo 2. Enable Actions if prompted
echo 3. The workflow will run automatically and generate:
echo    - Project READMEs with component tables
echo    - 3D renders (top.png, bottom.png, rotating.gif)
echo    - Main README with project table
echo    - automation-log.json for audit trail

pause