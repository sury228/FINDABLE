@echo off
cd /d "C:\Users\HP\Desktop\ml comp"
echo ====================================================
echo Pushing Findable to https://github.com/sury228/FINDABLE.git
echo ====================================================

REM Initialize Git with main branch if not present
if not exist .git (
    echo Initializing git repository...
    git init -b main
)

REM Add files according to .gitignore
echo Staging files...
git add .

REM Commit changes
echo Committing files...
git commit -m "Initial commit: Findable - AI Shade Data & Cryptographic Passports via PayPal"

REM Configure remote origin
git remote remove origin >nul 2>&1
git remote add origin https://github.com/sury228/FINDABLE.git
git branch -M main

REM Push to GitHub
echo Pushing to GitHub...
git push -u origin main

echo.
echo ====================================================
echo Push complete! Check https://github.com/sury228/FINDABLE
echo ====================================================
pause

