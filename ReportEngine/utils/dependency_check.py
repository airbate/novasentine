"""
检测系统依赖工具
用于检测 PDF 生成所需的系统依赖
"""
import sys
import platform
from loguru import logger


def _get_platform_specific_instructions():
    """
    获取针对当前平台的安装说明

    Returns:
        str: 平台特定的安装说明
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        return (
            "║  🍎 macOS 系统解决方案：                                       ║\n"
            "║                                                                ║\n"
            "║  1. 安装系统依赖：                                             ║\n"
            "║     brew install pango gdk-pixbuf libffi                       ║\n"
            "║                                                                ║\n"
            "║  2. 设置环境变量（重要！）：                                   ║\n"
            "║     export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH ║\n"
            "║                                                                ║\n"
            "║  3. 永久生效（推荐）：                                         ║\n"
            "║     echo 'export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH' >> ~/.zshrc ║\n"
            "║     source ~/.zshrc                                            ║\n"
        )
    elif system == "Linux":
        return (
            "║  🐧 Linux 系统解决方案：                                       ║\n"
            "║                                                                ║\n"
            "║  Ubuntu/Debian:                                                ║\n"
            "║    sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 \\    ║\n"
            "║                         libgdk-pixbuf2.0-0 libffi-dev libcairo2 ║\n"
            "║                                                                ║\n"
            "║  CentOS/RHEL:                                                  ║\n"
            "║    sudo yum install pango gdk-pixbuf2 libffi-devel cairo       ║\n"
        )
    elif system == "Windows":
        return (
            "║  🪟 Windows 系统解决方案：                                     ║\n"
            "║                                                                ║\n"
            "║  下载并安装 GTK3 Runtime：                                     ║\n"
            "║  https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases ║\n"
        )
    else:
        return (
            "║  请查看 README.md 了解您系统的安装方法                        ║\n"
        )


def check_pango_available():
    """
    检测 Pango 库是否可用

    Returns:
        tuple: (is_available: bool, message: str)
    """
    try:
        # 尝试导入 weasyprint 并初始化 Pango
        from weasyprint import HTML
        from weasyprint.text.ffi import ffi, pango

        # 尝试调用 Pango 函数来确认库可用
        pango.pango_version()

        return True, "✓ Pango 依赖检测通过，PDF 导出功能可用"
    except OSError as e:
        # Pango 库未安装或无法加载
        error_msg = str(e)
        platform_instructions = _get_platform_specific_instructions()

        if 'gobject' in error_msg.lower() or 'pango' in error_msg.lower() or 'gdk' in error_msg.lower():
            return False, (
                "╔════════════════════════════════════════════════════════════════╗\n"
                "║  ⚠️  PDF 导出依赖缺失                                          ║\n"
                "║                                                                ║\n"
                "║  📄 PDF 导出功能将不可用（其他功能不受影响）                  ║\n"
                "║                                                                ║\n"
                f"{platform_instructions}"
                "║                                                                ║\n"
                "║  📖 完整文档：根目录 README.md 第393行「PDF 导出依赖」        ║\n"
                "╚════════════════════════════════════════════════════════════════╝"
            )
        return False, f"⚠ PDF 依赖加载失败: {error_msg}"
    except ImportError as e:
        # weasyprint 未安装
        return False, (
            "⚠ WeasyPrint 未安装\n"
            "解决方法: pip install weasyprint"
        )
    except Exception as e:
        # 其他未知错误
        return False, f"⚠ PDF 依赖检测失败: {e}"


def log_dependency_status():
    """
    记录系统依赖状态到日志
    """
    is_available, message = check_pango_available()

    if is_available:
        logger.success(message)
    else:
        logger.warning(message)
        logger.info("💡 提示：PDF 导出功能需要 Pango 库支持，但不影响系统其他功能的正常使用")
        logger.info("📚 安装说明请参考：根目录下的 README.md 文件")

    return is_available


if __name__ == "__main__":
    # 用于独立测试
    is_available, message = check_pango_available()
    print(message)
    sys.exit(0 if is_available else 1)
