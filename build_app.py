"""
Build script an toàn cho Han Translate (Req 11.7).

Quy trình:
1. Pre-build secret scan - CHẶN build nếu phát hiện credential
2. Build .exe bằng PyInstaller
3. Loại các file nhạy cảm khỏi bản phân phối

Chạy:
    .\\venv\\Scripts\\python.exe build_app.py

Yêu cầu: pip install pyinstaller
"""

import os
import sys
import subprocess

# Đảm bảo import được package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_interpreter import packaging_security as ps  # noqa: E402
from loguru import logger  # noqa: E402


def main():
    logger.info("=" * 60)
    logger.info("Han Translate - Secure Build")
    logger.info("=" * 60)

    # --- Bước 1: Pre-build secret scan (Req 11.7) ---
    logger.info("Bước 1/3: Quét secret trong source code...")
    try:
        ps.assert_no_secrets("ai_interpreter")
    except RuntimeError as e:
        logger.error(str(e))
        logger.error("BUILD BỊ CHẶN. Sửa các secret trên rồi build lại.")
        sys.exit(1)

    # --- Bước 2: Build bằng PyInstaller ---
    logger.info("Bước 2/3: Build .exe bằng PyInstaller...")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        logger.error("Chưa cài PyInstaller. Chạy: .\\venv\\Scripts\\pip.exe install pyinstaller")
        sys.exit(1)

    icon_path = os.path.join("ai_interpreter", "assets", "logo.ico")
    icon_arg = ["--icon", icon_path] if os.path.exists(icon_path) else []

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "HanTranslate",
        "--windowed",            # không hiện console
        "--noconfirm",
        "--clean",
        # Bao gồm assets
        "--add-data", f"ai_interpreter{os.pathsep}ai_interpreter",
        *icon_arg,
        "run_interpreter.py",
    ]

    logger.info(f"Lệnh: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        logger.error("PyInstaller build thất bại.")
        sys.exit(1)

    # --- Bước 3: Xác minh không có file nhạy cảm trong dist ---
    logger.info("Bước 3/3: Kiểm tra bản phân phối...")
    dist_dir = os.path.join("dist", "HanTranslate")
    sensitive_found = []
    if os.path.isdir(dist_dir):
        for dp, _, files in os.walk(dist_dir):
            for f in files:
                for pattern in ps.get_distribution_excludes():
                    clean = pattern.replace("*", "")
                    if clean and clean in f:
                        sensitive_found.append(os.path.join(dp, f))

    if sensitive_found:
        logger.warning("Phát hiện file nhạy cảm trong bản build:")
        for f in sensitive_found:
            logger.warning(f"  {f}")
            try:
                os.remove(f)
                logger.info(f"  -> Đã xóa")
            except Exception as e:
                logger.error(f"  -> Không xóa được: {e}")
    else:
        logger.info("Bản phân phối sạch, không có file nhạy cảm.")

    logger.info("=" * 60)
    logger.info(f"BUILD THÀNH CÔNG: {dist_dir}\\HanTranslate.exe")
    logger.info("Mỗi máy cài về sẽ tự sinh API key riêng (first-run setup).")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
