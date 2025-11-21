"""
检测系统依赖工具
用于检测 PDF 生成所需的系统依赖
"""
import os
import sys
import platform
from pathlib import Path
from loguru import logger
from ctypes import util as ctypes_util


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
            "║     Apple Silicon: export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH ║\n"
            "║     Intel Mac:   export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH     ║\n"
            "║                                                                ║\n"
            "║  3. 永久生效（推荐）：                                         ║\n"
            "║     echo 'export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH' >> ~/.zshrc ║\n"
            "║     或 echo 'export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH' >> ~/.zshrc ║\n"
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
            "║                                                                ║\n"
            "║  若仍提示缺库：export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH ║\n"
            "║                 sudo ldconfig                                  ║\n"
        )
    elif system == "Windows":
        return (
            "║  🪟 Windows 系统解决方案：                                     ║\n"
            "║                                                                ║\n"
            "║  1. 安装 GTK3 Runtime：                                        ║\n"
            "║     https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases ║\n"
            "║                                                                ║\n"
            "║  2. 将 GTK 安装目录下的 bin 加入 PATH（需新开终端）：         ║\n"
            "║     set PATH=C:\\Program Files\\GTK3-Runtime Win64\\bin;%PATH%  ║\n"
            "║     （若自定义路径，请替换为实际安装路径）                     ║\n"
            "║                                                                ║\n"
            "║  3. 验证：在新终端运行                                         ║\n"
            "║     python -m ReportEngine.utils.dependency_check              ║\n"
            "║     看到 ✓ 提示即表示 PDF 导出可用                             ║\n"
        )
    else:
        return (
            "║  请查看 README.md 了解您系统的安装方法                        ║\n"
        )


def _ensure_windows_gtk_paths():
    """
    为 Windows 自动补充 GTK/Pango 运行时搜索路径，解决 DLL 未找到问题。

    Returns:
        str | None: 成功添加的路径（没有命中则为 None）
    """
    if platform.system() != "Windows":
        return None

    candidates = []
    seen = set()

    def _add_candidate(path_like):
        if not path_like:
            return
        p = Path(path_like)
        # 如果传入的是安装根目录，尝试拼接 bin
        if p.is_dir() and p.name.lower() == "bin":
            key = str(p.resolve()).lower()
            if key not in seen:
                seen.add(key)
                candidates.append(p)
        else:
            for maybe in (p, p / "bin"):
                key = str(maybe.resolve()).lower()
                if maybe.exists() and key not in seen:
                    seen.add(key)
                    candidates.append(maybe)

    # 用户自定义提示优先
    for env_var in ("GTK3_RUNTIME_PATH", "GTK_RUNTIME_PATH", "GTK_BIN_PATH", "GTK_BIN_DIR", "GTK_PATH"):
        _add_candidate(os.environ.get(env_var))

    program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
    default_dirs = [
        Path(program_files) / "GTK3-Runtime Win64",
        Path(program_files_x86) / "GTK3-Runtime Win64",
        Path(program_files) / "GTK3-Runtime Win32",
        Path(program_files_x86) / "GTK3-Runtime Win32",
        Path(program_files) / "GTK3-Runtime",
        Path(program_files_x86) / "GTK3-Runtime",
    ]

    # 常见自定义安装位置（其他盘符 / DevelopSoftware 目录）
    common_drives = ["C", "D", "E", "F"]
    common_names = ["GTK3-Runtime Win64", "GTK3-Runtime Win32", "GTK3-Runtime"]
    for drive in common_drives:
        root = Path(f"{drive}:/")
        for name in common_names:
            default_dirs.append(root / name)
            default_dirs.append(root / "DevelopSoftware" / name)

    # 扫描 Program Files 下所有以 GTK 开头的目录，适配自定义安装目录名
    for root in (program_files, program_files_x86):
        root_path = Path(root)
        if root_path.exists():
            for child in root_path.glob("GTK*"):
                default_dirs.append(child)

    for d in default_dirs:
        _add_candidate(d)

    # 如果用户已把自定义路径加入 PATH，也尝试识别
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    for entry in path_entries:
        if not entry:
            continue
        # 粗筛包含 gtk 或 pango 的目录
        if "gtk" in entry.lower() or "pango" in entry.lower():
            _add_candidate(entry)

    for path in candidates:
        if not path or not path.exists():
            continue
        if not any(path.glob("pango*-1.0-*.dll")) and not (path / "pango-1.0-0.dll").exists():
            continue

        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(path))
        except Exception:
            # 如果添加失败，继续尝试 PATH 方式
            pass

        current_path = os.environ.get("PATH", "")
        if str(path) not in current_path.split(";"):
            os.environ["PATH"] = f"{path};{current_path}"

        return str(path)

    return None


def prepare_pango_environment():
    """
    初始化运行所需的本地依赖搜索路径（当前主要针对 Windows 和 macOS）。

    Returns:
        str | None: 成功添加的路径（没有命中则为 None）
    """
    system = platform.system()
    if system == "Windows":
        return _ensure_windows_gtk_paths()
    if system == "Darwin":
        # 自动补全 DYLD_LIBRARY_PATH，兼容 Apple Silicon 与 Intel
        candidates = [Path("/opt/homebrew/lib"), Path("/usr/local/lib")]
        current = os.environ.get("DYLD_LIBRARY_PATH", "")
        added = []
        for c in candidates:
            if c.exists() and str(c) not in current.split(":"):
                added.append(str(c))
        if added:
            os.environ["DYLD_LIBRARY_PATH"] = ":".join(added + ([current] if current else []))
            return os.environ["DYLD_LIBRARY_PATH"]
    return None


def _probe_native_libs():
    """
    使用 ctypes 查找关键原生库，帮助定位缺失组件。

    Returns:
        list[str]: 未找到的库标识
    """
    system = platform.system()
    targets = []

    if system == "Windows":
        targets = [
            ("pango", ["pango-1.0-0"]),
            ("gobject", ["gobject-2.0-0"]),
            ("gdk-pixbuf", ["gdk_pixbuf-2.0-0"]),
            ("cairo", ["cairo-2"]),
        ]
    else:
        targets = [
            ("pango", ["pango-1.0"]),
            ("gobject", ["gobject-2.0"]),
            ("gdk-pixbuf", ["gdk_pixbuf-2.0"]),
            ("cairo", ["cairo", "cairo-2"]),
        ]

    missing = []
    for key, variants in targets:
        found = any(ctypes_util.find_library(v) for v in variants)
        if not found:
            missing.append(key)
    return missing


def check_pango_available():
    """
    检测 Pango 库是否可用

    Returns:
        tuple: (is_available: bool, message: str)
    """
    added_path = prepare_pango_environment()
    missing_native = _probe_native_libs()

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
        windows_hint = ""
        if platform.system() == "Windows":
            path_display = added_path or "未找到默认路径"
            # 控制长度，避免破坏提示框宽度
            if len(path_display) > 38:
                path_display = path_display[:35] + "..."
            windows_hint = f"║  已尝试自动添加 GTK 路径: {path_display:<38}║\n"
            arch_note = "║  🔍 若已安装仍报错：确认 Python/GTK 位数一致，重开终端        ║\n"
        else:
            arch_note = ""

        missing_note = ""
        if missing_native:
            missing_str = ", ".join(missing_native)
            missing_note = f"║  未识别到的依赖: {missing_str:<46}║\n"

        if 'gobject' in error_msg.lower() or 'pango' in error_msg.lower() or 'gdk' in error_msg.lower():
            return False, (
                "╔════════════════════════════════════════════════════════════════╗\n"
                "║  ⚠️  PDF 导出依赖缺失                                          ║\n"
                "║                                                                ║\n"
                "║  📄 PDF 导出功能将不可用（其他功能不受影响）                  ║\n"
                "║                                                                ║\n"
                f"{windows_hint}"
                f"{arch_note}"
                f"{missing_note}"
                f"{platform_instructions}"
                "║                                                                ║\n"
                "║  📖 完整文档：根目录 README.md ‘源码启动’的第二步            ║\n"
                "╚════════════════════════════════════════════════════════════════╝"
            )
        return False, f"⚠ PDF 依赖加载失败: {error_msg}；缺失/未识别: {', '.join(missing_native) if missing_native else '未知'}"
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
