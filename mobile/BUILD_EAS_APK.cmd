@echo off
setlocal
cd /d "%~dp0"
call npm install || exit /b 1
call npx expo install --check || exit /b 1
call npm run check || exit /b 1
call npm test || exit /b 1
call npx eas-cli build --platform android --profile preview
endlocal
