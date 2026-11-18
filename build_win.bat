@echo off
REM MIRA - Windows .exe 빌드 스크립트
REM 실행: CMD 프롬프트에서 build_win.bat (또는 더블클릭)
REM 결과: packaging\dist\MIRA.exe
REM
REM 사전 준비:
REM   1. Python 설치 (https://python.org) — "Add Python to PATH" 반드시 체크
REM   2. pip install -r requirements.txt pyinstaller
REM   3. assets\AppIcon.ico 파일 준비 (tools\convert_icon.py 참고)

echo === MIRA Windows 빌드 시작 ===

REM 이전 빌드 결과물 정리
if exist "packaging\build" (
    echo 이전 build 폴더 삭제 중...
    rmdir /s /q "packaging\build"
)
if exist "packaging\dist" (
    echo 이전 dist 폴더 삭제 중...
    rmdir /s /q "packaging\dist"
)

REM packaging 폴더 생성
if not exist "packaging" mkdir "packaging"

REM PyInstaller로 .exe 빌드
REM  - %~dp0 : 이 배치 파일이 있는 디렉토리 (절대 경로)
REM  - Windows --add-data 구분자는 세미콜론(;)
REM  - --onefile : 실행에 필요한 파일을 MIRA.exe 하나로 묶음
pyinstaller ^
    --windowed ^
    --onefile ^
    --name "MIRA" ^
    --icon "%~dp0assets\AppIcon.ico" ^
    --add-data "%~dp0viewer;viewer" ^
    --add-data "%~dp0assets;assets" ^
    --add-data "%~dp0USER_MANUAL_ENG.md;." ^
    --hidden-import "pyimzml" ^
    --hidden-import "pyqtgraph" ^
    --hidden-import "skimage" ^
    --hidden-import "PIL" ^
    --hidden-import "tifffile" ^
    --collect-submodules "pyimzml" ^
    --collect-submodules "pyqtgraph" ^
    --specpath "packaging" ^
    --distpath "packaging\dist" ^
    --workpath "packaging\build" ^
    --noconfirm ^
    main.py

echo.
echo === 빌드 완료 ===
echo 생성된 실행 파일: packaging\dist\MIRA.exe
echo.
echo 배포 방법:
echo   packaging\dist\MIRA.exe 를 복사해서 실행하세요.
echo   (단일 .exe 또는 packaging\dist\ 폴더 전체를 배포)
echo.

pause
