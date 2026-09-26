@echo off
echo Staging and committing changes...
git add .
set /p msg="Enter commit message (or press ENTER for default): "
if "%msg%"=="" set msg=Update video generator code

git commit -m "%msg%"
echo Pushing changes to GitHub...
git push origin main

echo.
echo Sync Complete! Your repository and live app will auto-update.
pause
