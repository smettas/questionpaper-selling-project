@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul || (echo Install Node.js first. & exit /b 1)
where java >nul 2>nul || (echo Install/select JDK 17 first. & exit /b 1)
if not defined ANDROID_HOME if exist "%LOCALAPPDATA%\Android\Sdk" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
if not defined ANDROID_HOME (echo Set ANDROID_HOME to your Android SDK folder first. & exit /b 1)
call npm install || exit /b 1
call npx expo install --check || exit /b 1
call npm run check || exit /b 1
call npm test || exit /b 1
if not exist android\gradlew.bat (
 call npx expo prebuild --platform android --no-install || exit /b 1
)
cd android
call gradlew.bat assembleRelease || exit /b 1
echo.
echo APK: %CD%\app\build\outputs\apk\release\app-release.apk
echo Local generated release uses the Expo-generated signing configuration. For store publication use a private release key or EAS production credentials.
endlocal
