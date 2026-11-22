"""Detect existing Android SDKs and run this project's current local APK script."""
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
candidates=[os.getenv('ANDROID_HOME',''),os.getenv('ANDROID_SDK_ROOT',''),str(Path(os.getenv('LOCALAPPDATA',''))/'Android'/'Sdk'),r'E:\Android\Sdk',r'E:\AndroidSDK',r'C:\Android\Sdk',r'D:\Android\Sdk']
properties=[root/'android'/'local.properties',Path(r'E:\Projects\NEETApp\android\local.properties'),Path(r'E:\StudentStore_Phase1_Reviewed\mobile\android\local.properties')]
for prop in properties:
    if prop.is_file():
        for line in prop.read_text(encoding='utf-8-sig').splitlines():
            if line.strip().startswith('sdk.dir='):
                candidates.append(line.split('=',1)[1].strip().replace('\\:',':').replace('\\\\','\\'))
sdk=next((p for p in candidates if p and (Path(p)/'platforms').is_dir() and (Path(p)/'build-tools').is_dir()),None)
if not sdk:
    print('Android SDK not found. Checked:\n'+'\n'.join(dict.fromkeys(p for p in candidates if p)))
    print('Install the SDK with Android Studio, or set ANDROID_HOME to its location.')
    sys.exit(1)
env=os.environ.copy();env.update(ANDROID_HOME=sdk,ANDROID_SDK_ROOT=sdk)
print('Using Android SDK:',sdk,flush=True)
sys.exit(subprocess.call(['cmd.exe','/d','/c','BUILD_LOCAL_APK.cmd'],cwd=root,env=env))
