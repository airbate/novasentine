"""
检测系统依赖工具
用于检测 PDF 生成所需的系统依赖
"""
import sys
from loguru import logger


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
        if 'pango' in error_msg.lower():
            return False, (
                "⚠ Pango 依赖未安装或无法加载，PDF 导出功能将不可用（其他功能不受影响）\n"
                "  请查看 requirements.txt 文件中的 PDF 生成部分，了解如何安装 Pango 依赖"
            )
        return False, f"⚠ PDF 依赖加载失败: {error_msg}"
    except ImportError as e:
        # weasyprint 未安装
        return False, f"⚠ WeasyPrint 未安装: {e}"
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
        logger.info("提示：PDF 导出功能需要 Pango 库支持，但不影响系统其他功能的正常使用")
        logger.info("安装说明请参考：requirements.txt 文件中的 '===== PDF生成 =====' 部分")

    return is_available


if __name__ == "__main__":
    # 用于独立测试
    is_available, message = check_pango_available()
    print(message)
    sys.exit(0 if is_available else 1)
