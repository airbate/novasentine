"""
PDF布局优化器

自动分析和优化PDF布局，确保内容不溢出、排版美观。
支持：
- 自动调整字号
- 优化行间距
- 调整色块大小
- 智能排列信息块
- 保存和加载优化方案
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
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

        # 遍历章节
        sections = document_ir.get('sections', [])
        for section in sections:
            self._analyze_section(section, stats)

        logger.info(f"文档分析完成: {stats}")
        return stats

    def _analyze_section(self, section: Dict[str, Any], stats: Dict[str, Any]):
        """递归分析章节"""
        children = section.get('children', [])

        for child in children:
            node_type = child.get('type')

            if node_type == 'kpi_grid':
                kpis = child.get('kpis', [])
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
                headers = child.get('headers', [])
                rows = child.get('rows', [])
                stats['max_table_columns'] = max(
                    stats['max_table_columns'],
                    len(headers)
                )
                stats['max_table_rows'] = max(
                    stats['max_table_rows'],
                    len(rows)
                )

            elif node_type == 'chart':
                stats['chart_count'] += 1

            elif node_type == 'callout':
                stats['callout_count'] += 1
                content = child.get('content', '')
                if len(content) > 200:
                    stats['has_long_text'] = True

            elif node_type == 'paragraph':
                text = child.get('text', '')
                stats['total_content_length'] += len(text)
                if len(text) > 500:
                    stats['has_long_text'] = True

            # 递归处理子章节
            if node_type == 'section':
                self._analyze_section(child, stats)

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

        # 根据KPI数值长度调整字号
        if stats['max_kpi_value_length'] > 10:
            config.kpi_card.font_size_value = 28
            self.optimization_log.append(
                f"KPI数值过长({stats['max_kpi_value_length']}字符)，"
                f"字号从32调整为28"
            )
        elif stats['max_kpi_value_length'] > 15:
            config.kpi_card.font_size_value = 24
            self.optimization_log.append(
                f"KPI数值很长({stats['max_kpi_value_length']}字符)，"
                f"字号从32调整为24"
            )

        # 根据KPI数量调整网格列数
        if stats['kpi_count'] > 6:
            config.grid.columns = 3
            config.kpi_card.min_height = 100
            self.optimization_log.append(
                f"KPI卡片较多({stats['kpi_count']}个)，"
                f"每行列数从2调整为3"
            )
        elif stats['kpi_count'] <= 2:
            config.grid.columns = 1
            self.optimization_log.append(
                f"KPI卡片较少({stats['kpi_count']}个)，"
                f"每行列数从2调整为1"
            )

        # 根据表格列数调整字号
        if stats['max_table_columns'] > 6:
            config.table.font_size_header = 11
            config.table.font_size_body = 10
            config.table.cell_padding = 8
            self.optimization_log.append(
                f"表格列数较多({stats['max_table_columns']}列)，"
                f"缩小字号和内边距"
            )

        # 如果有长文本，增加行高
        if stats['has_long_text']:
            config.page.line_height = 1.8
            config.callout.line_height = 1.8
            self.optimization_log.append(
                "检测到长文本，增加行高至1.8提高可读性"
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

/* KPI卡片优化 */
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
}}

.kpi-card .value {{
    font-size: {cfg.kpi_card.font_size_value}px !important;
    line-height: 1.2;
    word-break: break-word;
}}

.kpi-card .label {{
    font-size: {cfg.kpi_card.font_size_label}px !important;
}}

.kpi-card .change {{
    font-size: {cfg.kpi_card.font_size_change}px !important;
}}

/* 提示框优化 */
.callout {{
    padding: {cfg.callout.padding}px !important;
    margin: 20px 0;
    line-height: {cfg.callout.line_height};
    break-inside: avoid;
    page-break-inside: avoid;
}}

.callout-title {{
    font-size: {cfg.callout.font_size_title}px !important;
    margin-bottom: 10px;
}}

.callout-content {{
    font-size: {cfg.callout.font_size_content}px !important;
}}

/* 表格优化 */
table {{
    width: 100%;
    break-inside: avoid;
    page-break-inside: avoid;
}}

th {{
    font-size: {cfg.table.font_size_header}px !important;
    padding: {cfg.table.cell_padding}px !important;
}}

td {{
    font-size: {cfg.table.font_size_body}px !important;
    padding: {cfg.table.cell_padding}px !important;
    max-width: {cfg.table.max_cell_width}px;
    word-wrap: break-word;
    overflow-wrap: break-word;
}}

/* 图表优化 */
.chart-card {{
    min-height: {cfg.chart.min_height}px;
    max-height: {cfg.chart.max_height}px;
    padding: {cfg.chart.padding}px;
    break-inside: avoid;
    page-break-inside: avoid;
}}

.chart-title {{
    font-size: {cfg.chart.font_size_title}px !important;
}}

/* 防止标题孤行 */
h1, h2, h3, h4, h5, h6 {{
    break-after: avoid;
    page-break-after: avoid;
}}

/* 确保内容块不被分页 */
.content-block {{
    break-inside: avoid;
    page-break-inside: avoid;
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
