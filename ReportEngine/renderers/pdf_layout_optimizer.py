"""
PDF布局优化器

自动分析和优化PDF布局，确保内容不溢出、排版美观。
支持：
- 自动调整字号
- 优化行间距
- 调整色块大小
- 智能排列信息块
- 保存和加载优化方案
- 文本宽度检测和溢出预防
- 色块边界检测和自动调整
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger


@dataclass
class KPICardLayout:
    """KPI卡片布局配置"""
    font_size_value: int = 32  # 数值字号
    font_size_label: int = 14  # 标签字号
    font_size_change: int = 13  # 变化值字号
    padding: int = 20  # 内边距
    min_height: int = 120  # 最小高度
    value_max_length: int = 10  # 数值最大字符数（超过则缩小字号）


@dataclass
class CalloutLayout:
    """提示框布局配置"""
    font_size_title: int = 16  # 标题字号
    font_size_content: int = 14  # 内容字号
    padding: int = 20  # 内边距
    line_height: float = 1.6  # 行高倍数
    max_width: str = "100%"  # 最大宽度


@dataclass
class TableLayout:
    """表格布局配置"""
    font_size_header: int = 13  # 表头字号
    font_size_body: int = 12  # 表体字号
    cell_padding: int = 12  # 单元格内边距
    max_cell_width: int = 200  # 最大单元格宽度（像素）
    overflow_strategy: str = "wrap"  # 溢出策略：wrap(换行) / ellipsis(省略号)


@dataclass
class ChartLayout:
    """图表布局配置"""
    font_size_title: int = 16  # 图表标题字号
    font_size_label: int = 12  # 标签字号
    min_height: int = 300  # 最小高度
    max_height: int = 600  # 最大高度
    padding: int = 20  # 内边距


@dataclass
class GridLayout:
    """网格布局配置"""
    columns: int = 2  # 每行列数
    gap: int = 20  # 间距
    responsive_breakpoint: int = 768  # 响应式断点（宽度）


@dataclass
class PageLayout:
    """页面整体布局配置"""
    font_size_base: int = 14  # 基础字号
    font_size_h1: int = 28  # 一级标题
    font_size_h2: int = 24  # 二级标题
    font_size_h3: int = 20  # 三级标题
    font_size_h4: int = 16  # 四级标题
    line_height: float = 1.6  # 行高倍数
    paragraph_spacing: int = 16  # 段落间距
    section_spacing: int = 32  # 章节间距
    page_padding: int = 40  # 页面边距
    max_content_width: int = 800  # 最大内容宽度


@dataclass
class PDFLayoutConfig:
    """完整的PDF布局配置"""
    page: PageLayout
    kpi_card: KPICardLayout
    callout: CalloutLayout
    table: TableLayout
    chart: ChartLayout
    grid: GridLayout

    # 优化策略配置
    auto_adjust_font_size: bool = True  # 自动调整字号
    auto_adjust_grid_columns: bool = True  # 自动调整网格列数
    prevent_orphan_headers: bool = True  # 防止标题孤行
    optimize_for_print: bool = True  # 打印优化

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'page': asdict(self.page),
            'kpi_card': asdict(self.kpi_card),
            'callout': asdict(self.callout),
            'table': asdict(self.table),
            'chart': asdict(self.chart),
            'grid': asdict(self.grid),
            'auto_adjust_font_size': self.auto_adjust_font_size,
            'auto_adjust_grid_columns': self.auto_adjust_grid_columns,
            'prevent_orphan_headers': self.prevent_orphan_headers,
            'optimize_for_print': self.optimize_for_print,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PDFLayoutConfig:
        """从字典创建配置"""
        return cls(
            page=PageLayout(**data['page']),
            kpi_card=KPICardLayout(**data['kpi_card']),
            callout=CalloutLayout(**data['callout']),
            table=TableLayout(**data['table']),
            chart=ChartLayout(**data['chart']),
            grid=GridLayout(**data['grid']),
            auto_adjust_font_size=data.get('auto_adjust_font_size', True),
            auto_adjust_grid_columns=data.get('auto_adjust_grid_columns', True),
            prevent_orphan_headers=data.get('prevent_orphan_headers', True),
            optimize_for_print=data.get('optimize_for_print', True),
        )


class PDFLayoutOptimizer:
    """
    PDF布局优化器

    根据内容特征自动优化PDF布局，防止溢出和排版问题。
    """

    # 字符宽度估算系数（基于常见中文字体）
    # 中文字符通常是等宽的，约等于字号的像素值
    # 英文和数字约为字号的0.5-0.6倍
    CHAR_WIDTH_FACTOR = {
        'chinese': 1.0,      # 中文字符
        'english': 0.55,     # 英文字母
        'number': 0.6,       # 数字
        'symbol': 0.4,       # 符号
    }

    def __init__(self, config: Optional[PDFLayoutConfig] = None):
        """
        初始化优化器

        参数:
            config: 布局配置，如果为None则使用默认配置
        """
        self.config = config or self._create_default_config()
        self.optimization_log = []

    @staticmethod
    def _create_default_config() -> PDFLayoutConfig:
        """创建默认配置"""
        return PDFLayoutConfig(
            page=PageLayout(),
            kpi_card=KPICardLayout(),
            callout=CalloutLayout(),
            table=TableLayout(),
            chart=ChartLayout(),
            grid=GridLayout(),
        )

    def optimize_for_document(self, document_ir: Dict[str, Any]) -> PDFLayoutConfig:
        """
        根据文档IR内容优化布局配置

        参数:
            document_ir: Document IR数据

        返回:
            PDFLayoutConfig: 优化后的布局配置
        """
        logger.info("开始分析文档并优化布局...")

        # 分析文档结构
        stats = self._analyze_document(document_ir)

        # 根据分析结果调整配置
        optimized_config = self._adjust_config_based_on_stats(stats)

        # 记录优化日志
        self._log_optimization(stats, optimized_config)

        return optimized_config

    def _analyze_document(self, document_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析文档内容特征

        返回统计信息：
        - kpi_count: KPI卡片数量
        - table_count: 表格数量
        - chart_count: 图表数量
        - max_kpi_value_length: 最长KPI数值长度
        - max_table_columns: 最多表格列数
        - total_content_length: 总内容长度
        """
        stats = {
            'kpi_count': 0,
            'table_count': 0,
            'chart_count': 0,
            'callout_count': 0,
            'max_kpi_value_length': 0,
            'max_table_columns': 0,
            'max_table_rows': 0,
            'total_content_length': 0,
            'has_long_text': False,
        }

        # 优先使用chapters，fallback到sections
        chapters = document_ir.get('chapters', [])
        if not chapters:
            chapters = document_ir.get('sections', [])

        # 遍历章节
        for chapter in chapters:
            self._analyze_chapter(chapter, stats)

        logger.info(f"文档分析完成: {stats}")
        return stats

    def _analyze_chapter(self, chapter: Dict[str, Any], stats: Dict[str, Any]):
        """分析单个章节"""
        # 分析章节中的blocks
        blocks = chapter.get('blocks', [])
        for block in blocks:
            self._analyze_block(block, stats)

        # 递归处理子章节（如果有）
        children = chapter.get('children', [])
        for child in children:
            if isinstance(child, dict):
                self._analyze_chapter(child, stats)

    def _analyze_block(self, block: Dict[str, Any], stats: Dict[str, Any]):
        """分析单个block节点"""
        if not isinstance(block, dict):
            return

        node_type = block.get('type')

        if node_type == 'kpiGrid':
            kpis = block.get('items', [])
            stats['kpi_count'] += len(kpis)

            # 检查KPI数值长度
            for kpi in kpis:
                value = str(kpi.get('value', ''))
                stats['max_kpi_value_length'] = max(
                    stats['max_kpi_value_length'],
                    len(value)
                )

        elif node_type == 'table':
            stats['table_count'] += 1

            # 分析表格结构
            headers = block.get('headers', [])
            rows = block.get('rows', [])
            if rows and isinstance(rows[0], dict):
                # 从第一行的cells计算列数
                cells = rows[0].get('cells', [])
                stats['max_table_columns'] = max(
                    stats['max_table_columns'],
                    len(cells)
                )
            else:
                stats['max_table_columns'] = max(
                    stats['max_table_columns'],
                    len(headers)
                )
            stats['max_table_rows'] = max(
                stats['max_table_rows'],
                len(rows)
            )

        elif node_type == 'chart' or node_type == 'widget':
            stats['chart_count'] += 1

        elif node_type == 'callout':
            stats['callout_count'] += 1
            # 检查callout中的blocks
            callout_blocks = block.get('blocks', [])
            for cb in callout_blocks:
                if isinstance(cb, dict) and cb.get('type') == 'paragraph':
                    text = self._extract_text_from_paragraph(cb)
                    if len(text) > 200:
                        stats['has_long_text'] = True

        elif node_type == 'paragraph':
            text = self._extract_text_from_paragraph(block)
            stats['total_content_length'] += len(text)
            if len(text) > 500:
                stats['has_long_text'] = True

        # 递归处理嵌套的blocks
        nested_blocks = block.get('blocks', [])
        if nested_blocks:
            for nested in nested_blocks:
                self._analyze_block(nested, stats)

    def _extract_text_from_paragraph(self, paragraph: Dict[str, Any]) -> str:
        """从paragraph block中提取纯文本"""
        text_parts = []
        inlines = paragraph.get('inlines', [])
        for inline in inlines:
            if isinstance(inline, dict):
                text = inline.get('text', '')
                if text:
                    text_parts.append(str(text))
            elif isinstance(inline, str):
                text_parts.append(inline)
        return ''.join(text_parts)

    def _analyze_section(self, section: Dict[str, Any], stats: Dict[str, Any]):
        """递归分析章节（保留用于向后兼容）"""
        # 这个方法保留用于向后兼容，实际上调用_analyze_chapter
        self._analyze_chapter(section, stats)

    def _estimate_text_width(self, text: str, font_size: int) -> float:
        """
        估算文本的像素宽度

        参数:
            text: 要测量的文本
            font_size: 字号（像素）

        返回:
            float: 估算的宽度（像素）
        """
        if not text:
            return 0.0

        width = 0.0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符范围
                width += font_size * self.CHAR_WIDTH_FACTOR['chinese']
            elif char.isalpha():
                width += font_size * self.CHAR_WIDTH_FACTOR['english']
            elif char.isdigit():
                width += font_size * self.CHAR_WIDTH_FACTOR['number']
            else:
                width += font_size * self.CHAR_WIDTH_FACTOR['symbol']

        return width

    def _check_text_overflow(self, text: str, font_size: int, max_width: int) -> bool:
        """
        检查文本是否会溢出

        参数:
            text: 要检查的文本
            font_size: 字号（像素）
            max_width: 最大宽度（像素）

        返回:
            bool: True表示会溢出
        """
        estimated_width = self._estimate_text_width(text, font_size)
        return estimated_width > max_width

    def _calculate_safe_font_size(
        self,
        text: str,
        max_width: int,
        min_font_size: int = 10,
        max_font_size: int = 32
    ) -> Tuple[int, bool]:
        """
        计算安全的字号以避免溢出

        参数:
            text: 要显示的文本
            max_width: 最大宽度（像素）
            min_font_size: 最小字号
            max_font_size: 最大字号

        返回:
            Tuple[int, bool]: (建议字号, 是否需要调整)
        """
        if not text:
            return max_font_size, False

        # 从最大字号开始尝试
        for font_size in range(max_font_size, min_font_size - 1, -1):
            if not self._check_text_overflow(text, font_size, max_width):
                # 如果需要缩小字号
                needs_adjustment = font_size < max_font_size
                return font_size, needs_adjustment

        # 如果连最小字号都溢出，返回最小字号并标记需要调整
        return min_font_size, True

    def _detect_kpi_overflow_issues(self, stats: Dict[str, Any]) -> List[str]:
        """
        检测KPI卡片可能的溢出问题

        参数:
            stats: 文档统计信息

        返回:
            List[str]: 检测到的问题列表
        """
        issues = []

        # KPI卡片的典型宽度（像素）
        # 基于2列布局，容器宽度800px，间距20px
        kpi_card_width = (800 - 20) // 2 - 40  # 减去padding

        # 检查最长KPI数值
        max_kpi_length = stats.get('max_kpi_value_length', 0)
        if max_kpi_length > 0:
            # 假设一个很长的数值
            sample_text = '1' * max_kpi_length + '亿元'
            current_font_size = self.config.kpi_card.font_size_value

            if self._check_text_overflow(sample_text, current_font_size, kpi_card_width):
                issues.append(
                    f"KPI数值过长({max_kpi_length}字符)，"
                    f"字号{current_font_size}px可能导致溢出"
                )

        return issues

    def _adjust_config_based_on_stats(
        self,
        stats: Dict[str, Any]
    ) -> PDFLayoutConfig:
        """根据统计信息调整配置"""
        config = PDFLayoutConfig(
            page=PageLayout(**asdict(self.config.page)),
            kpi_card=KPICardLayout(**asdict(self.config.kpi_card)),
            callout=CalloutLayout(**asdict(self.config.callout)),
            table=TableLayout(**asdict(self.config.table)),
            chart=ChartLayout(**asdict(self.config.chart)),
            grid=GridLayout(**asdict(self.config.grid)),
            auto_adjust_font_size=self.config.auto_adjust_font_size,
            auto_adjust_grid_columns=self.config.auto_adjust_grid_columns,
            prevent_orphan_headers=self.config.prevent_orphan_headers,
            optimize_for_print=self.config.optimize_for_print,
        )

        # 检测KPI溢出问题
        overflow_issues = self._detect_kpi_overflow_issues(stats)
        if overflow_issues:
            for issue in overflow_issues:
                logger.warning(f"检测到布局问题: {issue}")

        # KPI卡片宽度（像素）
        kpi_card_width = (800 - 20) // 2 - 40  # 2列布局

        # 根据KPI数值长度智能调整字号
        if stats['max_kpi_value_length'] > 0:
            # 创建示例文本进行测试
            sample_text = '9' * stats['max_kpi_value_length']
            safe_font_size, needs_adjustment = self._calculate_safe_font_size(
                sample_text,
                kpi_card_width,
                min_font_size=18,
                max_font_size=32
            )

            if needs_adjustment:
                config.kpi_card.font_size_value = safe_font_size
                self.optimization_log.append(
                    f"KPI数值过长({stats['max_kpi_value_length']}字符)，"
                    f"字号自动调整为{safe_font_size}px以防止溢出"
                )
            elif stats['max_kpi_value_length'] > 10:
                # 即使不溢出，也适当缩小以留出更多空间
                config.kpi_card.font_size_value = min(28, safe_font_size)
                self.optimization_log.append(
                    f"KPI数值较长({stats['max_kpi_value_length']}字符)，"
                    f"预防性调整字号为{config.kpi_card.font_size_value}px"
                )

        # 根据KPI数量调整网格布局
        if stats['kpi_count'] > 6:
            config.grid.columns = 3
            config.kpi_card.min_height = 100
            config.kpi_card.padding = 16  # 缩小padding以节省空间
            self.optimization_log.append(
                f"KPI卡片较多({stats['kpi_count']}个)，"
                f"调整为3列布局并缩小内边距"
            )
        elif stats['kpi_count'] > 4:
            config.grid.columns = 2
            config.kpi_card.padding = 18
            self.optimization_log.append(
                f"KPI卡片适中({stats['kpi_count']}个)，使用2列布局"
            )
        elif stats['kpi_count'] <= 2:
            config.grid.columns = 1
            config.kpi_card.padding = 24  # 较少卡片时增加padding
            self.optimization_log.append(
                f"KPI卡片较少({stats['kpi_count']}个)，"
                f"使用1列布局并增加内边距"
            )

        # 根据表格列数调整字号和间距
        if stats['max_table_columns'] > 8:
            config.table.font_size_header = 10
            config.table.font_size_body = 9
            config.table.cell_padding = 6
            self.optimization_log.append(
                f"表格列数很多({stats['max_table_columns']}列)，"
                f"大幅缩小字号和内边距"
            )
        elif stats['max_table_columns'] > 6:
            config.table.font_size_header = 11
            config.table.font_size_body = 10
            config.table.cell_padding = 8
            self.optimization_log.append(
                f"表格列数较多({stats['max_table_columns']}列)，"
                f"缩小字号和内边距"
            )
        elif stats['max_table_columns'] > 4:
            config.table.font_size_header = 12
            config.table.font_size_body = 11
            config.table.cell_padding = 10
            self.optimization_log.append(
                f"表格列数适中({stats['max_table_columns']}列)，"
                f"适度调整字号"
            )

        # 如果有长文本，增加行高和段落间距
        if stats['has_long_text']:
            config.page.line_height = 1.8
            config.callout.line_height = 1.8
            config.page.paragraph_spacing = 18
            self.optimization_log.append(
                "检测到长文本，增加行高至1.8和段落间距以提高可读性"
            )

        # 如果内容较多，减小整体字号
        total_blocks = (stats['kpi_count'] + stats['table_count'] +
                       stats['chart_count'] + stats['callout_count'])
        if total_blocks > 20:
            config.page.font_size_base = 13
            config.page.font_size_h2 = 22
            config.page.font_size_h3 = 18
            self.optimization_log.append(
                f"内容块较多({total_blocks}个)，"
                f"适度缩小整体字号以优化排版"
            )

        return config

    def _log_optimization(
        self,
        stats: Dict[str, Any],
        config: PDFLayoutConfig
    ):
        """记录优化过程"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'document_stats': stats,
            'optimizations': self.optimization_log.copy(),
            'final_config': config.to_dict(),
        }

        logger.info(f"布局优化完成，应用了{len(self.optimization_log)}项优化")
        for opt in self.optimization_log:
            logger.info(f"  - {opt}")

        # 清空日志供下次使用
        self.optimization_log.clear()

        return log_entry

    def save_config(self, path: str | Path, log_entry: Optional[Dict] = None):
        """
        保存配置到文件

        参数:
            path: 保存路径
            log_entry: 优化日志条目（可选）
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'config': self.config.to_dict(),
        }

        if log_entry:
            data['optimization_log'] = log_entry

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"布局配置已保存: {path}")

    @classmethod
    def load_config(cls, path: str | Path) -> PDFLayoutOptimizer:
        """
        从文件加载配置

        参数:
            path: 配置文件路径

        返回:
            PDFLayoutOptimizer: 加载了配置的优化器实例
        """
        path = Path(path)

        if not path.exists():
            logger.warning(f"配置文件不存在: {path}，使用默认配置")
            return cls()

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = PDFLayoutConfig.from_dict(data['config'])
        optimizer = cls(config)

        logger.info(f"布局配置已加载: {path}")
        return optimizer

    def generate_pdf_css(self) -> str:
        """
        根据当前配置生成PDF专用CSS

        返回:
            str: CSS样式字符串
        """
        cfg = self.config

        css = f"""
/* PDF布局优化样式 - 由PDFLayoutOptimizer自动生成 */

/* 页面基础样式 */
body {{
    font-size: {cfg.page.font_size_base}px;
    line-height: {cfg.page.line_height};
}}

main {{
    padding: {cfg.page.page_padding}px !important;
    max-width: {cfg.page.max_content_width}px;
    margin: 0 auto;
}}

/* 标题样式 */
h1 {{ font-size: {cfg.page.font_size_h1}px !important; }}
h2 {{ font-size: {cfg.page.font_size_h2}px !important; }}
h3 {{ font-size: {cfg.page.font_size_h3}px !important; }}
h4 {{ font-size: {cfg.page.font_size_h4}px !important; }}

/* 段落间距 */
p {{
    margin-bottom: {cfg.page.paragraph_spacing}px;
}}

.chapter {{
    margin-bottom: {cfg.page.section_spacing}px;
}}

/* KPI卡片优化 - 防止溢出 */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat({cfg.grid.columns}, 1fr);
    gap: {cfg.grid.gap}px;
    margin: 20px 0;
}}

.kpi-card {{
    padding: {cfg.kpi_card.padding}px !important;
    min-height: {cfg.kpi_card.min_height}px;
    break-inside: avoid;
    page-break-inside: avoid;
    /* 防止溢出的关键设置 */
    overflow: hidden;
    box-sizing: border-box;
    max-width: 100%;
}}

.kpi-card .value {{
    font-size: {cfg.kpi_card.font_size_value}px !important;
    line-height: 1.2;
    /* 强制换行和溢出控制 */
    word-break: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.kpi-card .label {{
    font-size: {cfg.kpi_card.font_size_label}px !important;
    /* 防止标签溢出 */
    word-break: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
}}

.kpi-card .change {{
    font-size: {cfg.kpi_card.font_size_change}px !important;
    word-break: break-word;
}}

/* 提示框优化 - 防止溢出 */
.callout {{
    padding: {cfg.callout.padding}px !important;
    margin: 20px 0;
    line-height: {cfg.callout.line_height};
    break-inside: avoid;
    page-break-inside: avoid;
    /* 防止溢出 */
    overflow: hidden;
    box-sizing: border-box;
    max-width: 100%;
}}

.callout-title {{
    font-size: {cfg.callout.font_size_title}px !important;
    margin-bottom: 10px;
    word-break: break-word;
}}

.callout-content {{
    font-size: {cfg.callout.font_size_content}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
}}

/* 表格优化 - 严格防止溢出 */
table {{
    width: 100%;
    break-inside: avoid;
    page-break-inside: avoid;
    /* 表格布局固定 */
    table-layout: fixed;
    max-width: 100%;
    overflow: hidden;
}}

th {{
    font-size: {cfg.table.font_size_header}px !important;
    padding: {cfg.table.cell_padding}px !important;
    /* 表头文字控制 */
    word-break: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    max-width: 100%;
}}

td {{
    font-size: {cfg.table.font_size_body}px !important;
    padding: {cfg.table.cell_padding}px !important;
    max-width: {cfg.table.max_cell_width}px;
    /* 强制换行，防止溢出 */
    word-wrap: break-word;
    overflow-wrap: break-word;
    word-break: break-word;
    hyphens: auto;
    white-space: normal;
}}

/* 图表优化 */
.chart-card {{
    min-height: {cfg.chart.min_height}px;
    max-height: {cfg.chart.max_height}px;
    padding: {cfg.chart.padding}px;
    break-inside: avoid;
    page-break-inside: avoid;
    /* 防止图表溢出 */
    overflow: hidden;
    max-width: 100%;
    box-sizing: border-box;
}}

.chart-title {{
    font-size: {cfg.chart.font_size_title}px !important;
    word-break: break-word;
}}

/* Hero区域的KPI卡片 */
.hero-kpi {{
    padding: {cfg.kpi_card.padding}px !important;
    overflow: hidden;
    box-sizing: border-box;
}}

.hero-kpi .label {{
    font-size: {cfg.kpi_card.font_size_label}px !important;
    word-break: break-word;
    max-width: 100%;
}}

.hero-kpi .value {{
    font-size: {cfg.kpi_card.font_size_value}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
}}

/* 防止标题孤行 */
h1, h2, h3, h4, h5, h6 {{
    break-after: avoid;
    page-break-after: avoid;
    word-break: break-word;
    overflow-wrap: break-word;
}}

/* 确保内容块不被分页且不溢出 */
.content-block {{
    break-inside: avoid;
    page-break-inside: avoid;
    overflow: hidden;
    max-width: 100%;
}}

/* 全局溢出防护 */
* {{
    box-sizing: border-box;
    max-width: 100%;
}}

/* 特别控制数字和长单词 */
.kpi-value, .value, .delta {{
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;  /* 稍微紧缩间距以节省空间 */
}}

/* 色块（badge）样式控制 */
.badge, .callout {{
    display: inline-block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: normal;
}}

/* 响应式调整 */
@media print {{
    /* 打印时更严格的控制 */
    * {{
        overflow: visible !important;
        max-width: 100% !important;
    }}

    .kpi-card, .callout, .chart-card {{
        overflow: hidden !important;
    }}
}}
"""

        return css


__all__ = [
    'PDFLayoutOptimizer',
    'PDFLayoutConfig',
    'PageLayout',
    'KPICardLayout',
    'CalloutLayout',
    'TableLayout',
    'ChartLayout',
    'GridLayout',
]
