#!/bin/bash
# MIRA - Mac .app 번들 빌드 스크립트
# 실행: bash build_mac.sh
# 결과: packaging/dist/MIRA.app
#
# 사전 준비:
#   pip install -r requirements.txt

set -e  # 오류 발생 시 즉시 중단

echo "=== MIRA Mac 빌드 시작 ==="

# 이전 빌드 결과물 정리 (스펙 파일은 유지)
rm -rf packaging/build packaging/dist

# packaging/ 폴더 생성
mkdir -p packaging

# PyInstaller로 .app 번들 생성
pyinstaller \
    --windowed \
    --name "MIRA" \
    --icon "$(pwd)/assets/AppIcon.icns" \
    --add-data "$(pwd)/viewer:viewer" \
    --add-data "$(pwd)/assets:assets" \
    --add-data "$(pwd)/USER_MANUAL_ENG.md:." \
    --hidden-import "pyimzml" \
    --hidden-import "pyqtgraph" \
    --hidden-import "skimage" \
    --hidden-import "PIL" \
    --hidden-import "tifffile" \
    --collect-submodules "pyimzml" \
    --collect-submodules "pyqtgraph" \
    --specpath "packaging" \
    --distpath "packaging/dist" \
    --workpath "packaging/build" \
    --noconfirm \
    main.py

echo ""
echo "=== 빌드 완료 ==="
echo "생성된 앱: packaging/dist/MIRA.app"
echo ""
echo "설치 방법:"
echo "  cp -r packaging/dist/MIRA.app /Applications/"
echo "  또는 Finder에서 packaging/dist/MIRA.app을 Applications 폴더로 드래그"
