#!/bin/bash
# Setup script to initialize git repo and push to GitHub
# Run this from S:\pcb-designs directory

set -e

REPO_URL="https://github.com/mr-sanjai-offl/PCB-Designs.git"
BRANCH="main"

echo "=== PCB Designs Repository Setup ==="
echo "Repository: $REPO_URL"
echo ""

# Check if already a git repo
if [ -d ".git" ]; then
    echo "Already a git repository. Checking remote..."
    if git remote get-url origin 2>/dev/null | grep -q "mr-sanjai-offl/PCB-Designs"; then
        echo "Remote already configured correctly."
    else
        echo "Updating remote URL..."
        git remote set-url origin "$REPO_URL"
    fi
else
    echo "Initializing git repository..."
    git init
    git branch -M "$BRANCH"
    git remote add origin "$REPO_URL"
fi

# Add all files
echo "Adding files..."
git add -A

# Check status
echo ""
echo "Git status:"
git status

# Commit if there are changes
if git diff --staged --quiet; then
    echo "No changes to commit."
else
    echo ""
    echo "Committing changes..."
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
fi

# Push to GitHub
echo ""
echo "Pushing to GitHub..."
echo "Note: You may need to authenticate with GitHub (token or SSH key)"
git push -u origin "$BRANCH"

echo ""
echo "=== Setup Complete ==="
echo "Repository pushed to: $REPO_URL"
echo ""
echo "Next steps:"
echo "1. Go to https://github.com/mr-sanjai-offl/PCB-Designs/actions"
echo "2. Enable Actions if prompted"
echo "3. The workflow will run automatically and generate:"
echo "   - Project READMEs with component tables"
echo "   - 3D renders (top.png, bottom.png, rotating.gif)"
echo "   - Main README with project table"
echo "   - automation-log.json for audit trail"