from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from ReportEngine.utils.chart_review_service import get_chart_review_service


class MarkdownRenderer:
    """
    将 Document IR 转为 Markdown。

    - 图表与词云统一降级为数据表格，避免丢失关键信息；
    - 尽量保留通用特性（标题、列表、代码、表格、引用等）；
    - 对不常见特性（callout/kpiGrid/engineQuote等）使用近似替换。
    """

    def __init__(self) -> None:
        self.document: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}

    def render(
        self,
        document_ir: Dict[str, Any],
        ir_file_path: str | None = None
    ) -> str:
        """
        入口：将IR转换为Markdown字符串。

        参数:
            document_ir: Document IR 数据
            ir_file_path: 可选，IR 文件路径，提供时修复后会自动保存

        返回:
            str: Markdown 字符串
        """
        self.document = document_ir or {}

        # 使用统一的 ChartReviewService 进行图表审查与修复
        # 虽然 Markdown 渲染时图表会降级为表格，但仍需确保数据有效
        chart_service = get_chart_review_service()
        chart_service.review_document(
            self.document,
            ir_file_path=ir_file_path,
            reset_stats=True,
            save_on_repair=bool(ir_file_path)
        )

        self.metadata = self.document.get("metadata", {}) or {}

        parts: List[str] = []
        title = self.metadata.get("title") or self.metadata.get("query") or "报告"
        if title:
            parts.append(f"# {self._escape_text(title)}")
            parts.append("")

        for chapter in self.document.get("chapters", []) or []:
            chapter_md = self._render_chapter(chapter)
            if chapter_md:
                parts.append(chapter_md)

        return "\n".join(part for part in parts if part is not None).strip()

    # ===== 章节与块级渲染 =====

    def _render_chapter(self, chapter: Dict[str, Any]) -> str:
        lines: List[str] = []
        title = chapter.get("title") or chapter.get("chapterId")
        blocks = chapter.get("blocks", []) if isinstance(chapter.get("blocks"), list) else []

        # 章节标题使用一级标题格式，并避免与首个heading重复
        if title:
            lines.append(f"# {self._escape_text(title)}")
            lines.append("")

        if blocks and self._is_heading_duplicate(blocks[0], title):
            blocks = blocks[1:]

        body = self._render_blocks(blocks)
        if body:
            lines.append(body)
        return "\n".join(lines).strip()

    def _render_blocks(self, blocks: List[Dict[str, Any]] | None, join_with_blank: bool = True) -> str:
        rendered: List[str] = []
        for block in blocks or []:
            md = self._render_block(block)
            if md is None:
                continue
            md = md.strip()
            if md:
                rendered.append(md)
        if not rendered:
            return ""
        separator = "\n\n" if join_with_blank else "\n"
        return separator.join(rendered)

    def _render_block(self, block: Any) -> str:
        if block is None:
            return ""
        if isinstance(block, str):
            return self._escape_text(block)
        if not isinstance(block, dict):
            return ""

        block_type = block.get("type") or ("paragraph" if block.get("inlines") else None)
        handlers = {
            "heading": self._render_heading,
            "paragraph": self._render_paragraph,
            "list": self._render_list,
            "table": self._render_table,
            "swotTable": self._render_swot_table,
            "pestTable": self._render_pest_table,
            "blockquote": self._render_blockquote,
            "engineQuote": self._render_engine_quote,
            "hr": lambda b: "---",
            "code": self._render_code,
            "math": self._render_math,
            "figure": self._render_figure,
            "callout": self._render_callout,
            "kpiGrid": self._render_kpi_grid,
            "widget": self._render_widget,
            "toc": lambda b: "",
        }
        if block_type in handlers:
            return handlers[block_type](block)

        if isinstance(block.get("blocks"), list):
            return self._render_blocks(block["blocks"])

        return self._fallback_unknown(block)

    def _render_heading(self, block: Dict[str, Any]) -> str:
        level = block.get("level", 2)
        level = max(1, min(6, level))
        hashes = "#" * level
        text = block.get("text") or ""
        subtitle = block.get("subtitle")
        subtitle_text = f" _{self._escape_text(subtitle)}_" if subtitle else ""
        heading_line = f"{hashes} {self._escape_text(text)}{subtitle_text}"
        # 章节内的一级标题前额外插入一个空行（不影响文档题目）
        if level == 1:
            return f"\n\n\n\n\n{heading_line}"
        return heading_line

    def _render_paragraph(self, block: Dict[str, Any]) -> str:
        return self._render_inlines(block.get("inlines", []))

    def _render_list(self, block: Dict[str, Any]) -> str:
        list_type = block.get("listType", "bullet")
        items = block.get("items") or []
        lines: List[str] = []
        for idx, item_blocks in enumerate(items):
            prefix = "-"
            if list_type == "ordered":
                prefix = f"{idx + 1}."
            elif list_type == "task":
                prefix = "- [ ]"
            content = self._render_blocks(item_blocks, join_with_blank=False)
            if not content:
                continue
            content_lines = content.splitlines() or [""]
            first = content_lines[0]
            lines.append(f"{prefix} {first}")
            for cont in content_lines[1:]:
                lines.append(f"  {cont}")
        return "\n".join(lines)

    def _render_table(self, block: Dict[str, Any]) -> str:
        rows = block.get("rows") or []
        if not rows:
            return ""

        header_cells: List[str] = []
        body_rows: List[List[str]] = []

        # 检测首行是否声明为表头
        first_row_cells = rows[0].get("cells") if isinstance(rows[0], dict) else None
        has_header = bool(first_row_cells and any(cell.get("header") or cell.get("isHeader") for cell in first_row_cells))

        # 计算最大列数，忽略rowspan
        col_count = 0
        for row in rows:
            cells = row.get("cells") if isinstance(row, dict) else None
            span = 0
            for cell in cells or []:
                span += int(cell.get("colspan") or 1)
            col_count = max(col_count, span)

        if has_header and first_row_cells:
            header_cells = [self._render_cell_content(cell) for cell in first_row_cells]
            rows = rows[1:]
        else:
            header_cells = [f"列{idx + 1}" for idx in range(col_count or (len(first_row_cells or []) or 1))]

        for row in rows:
            if not isinstance(row, dict):
                continue
            cells = row.get("cells") or []
            row_cells: List[str] = []
            for cell in cells:
                text = self._render_cell_content(cell)
                span = int(cell.get("colspan") or 1)
                row_cells.append(text)
                if span > 1:
                    row_cells.extend([""] * (span - 1))
            while len(row_cells) < len(header_cells):
                row_cells.append("")
            body_rows.append(row_cells[: len(header_cells)])

        lines = [
            self._markdown_row(header_cells),
            self._markdown_separator(len(header_cells)),
        ]
        for row in body_rows:
            lines.append(self._markdown_row(row))
        return "\n".join(lines)

    def _render_swot_table(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or "SWOT 分析"
        summary = block.get("summary")
        quadrants = [
            ("strengths", "S 优势"),
            ("weaknesses", "W 劣势"),
            ("opportunities", "O 机会"),
            ("threats", "T 威胁"),
        ]

        lines = [f"### {self._escape_text(title)}"]
        if summary:
            lines.append(self._escape_text(summary))

        for key, label in quadrants:
            items = self._normalize_swot_items(block.get(key))
            lines.append(f"#### {label}")
            if not items:
                lines.append("> 暂无数据")
                continue
            table_lines = [
                self._markdown_row(["序号", "要点", "详情", "标签"]),
                self._markdown_separator(4),
            ]
            for idx, item in enumerate(items, start=1):
                tags = [val for val in (item.get("impact"), item.get("priority")) if val]
                tag_text = " / ".join(self._escape_text(t) for t in tags) or ""
                detail = item.get("detail") or item.get("description") or item.get("evidence") or ""
                table_lines.append(
                    self._markdown_row([
                        str(idx),
                        self._escape_text(item.get("title") or "未命名要点", for_table=True),
                        self._escape_text(detail, for_table=True),
                        self._escape_text(tag_text, for_table=True),
                    ])
                )
            lines.append("\n".join(table_lines))
        return "\n\n".join(lines)

    def _render_pest_table(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or "PEST 分析"
        summary = block.get("summary")
        dimensions = [
            ("political", "P 政治"),
            ("economic", "E 经济"),
            ("social", "S 社会"),
            ("technological", "T 技术"),
        ]

        lines = [f"### {self._escape_text(title)}"]
        if summary:
            lines.append(self._escape_text(summary))

        for key, label in dimensions:
            items = self._normalize_pest_items(block.get(key))
            lines.append(f"#### {label}")
            if not items:
                lines.append("> 暂无数据")
                continue
            table_lines = [
                self._markdown_row(["序号", "要点", "详情", "标签"]),
                self._markdown_separator(4),
            ]
            for idx, item in enumerate(items, start=1):
                tags = [val for val in (item.get("impact"), item.get("weight"), item.get("priority")) if val]
                tag_text = " / ".join(self._escape_text(t) for t in tags) or ""
                detail = item.get("detail") or item.get("description") or ""
                table_lines.append(
                    self._markdown_row([
                        str(idx),
                        self._escape_text(item.get("title") or "未命名要点", for_table=True),
                        self._escape_text(detail, for_table=True),
                        self._escape_text(tag_text, for_table=True),
                    ])
                )
            lines.append("\n".join(table_lines))
        return "\n\n".join(lines)

    def _render_blockquote(self, block: Dict[str, Any]) -> str:
        inner = self._render_blocks(block.get("blocks", []))
        return self._quote_lines(inner)

    def _render_engine_quote(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or block.get("engine") or "引用"
        inner = self._render_blocks(block.get("blocks", []))
        header = f"**{self._escape_text(title)}**"
        return self._quote_lines(f"{header}\n{inner}" if inner else header)

    def _render_code(self, block: Dict[str, Any]) -> str:
        lang = block.get("lang") or ""
        content = block.get("content") or ""
        return f"```{lang}\n{content}\n```"

    def _render_math(self, block: Dict[str, Any]) -> str:
        latex = self._normalize_math(block.get("latex", ""))
        if not latex:
            return ""
        return f"$$\n{latex}\n$$"

    def _render_figure(self, block: Dict[str, Any]) -> str:
        caption = block.get("caption") or "图像内容占位"
        return f"> ![图示占位]({''}) {self._escape_text(caption)}"

    def _render_callout(self, block: Dict[str, Any]) -> str:
        tone = block.get("tone") or "info"
        title = block.get("title")
        inner = self._render_blocks(block.get("blocks", []))
        header = f"**{self._escape_text(title)}** [{tone}]" if title else f"[{tone}]"
        content = header if not inner else f"{header}\n{inner}"
        return self._quote_lines(content)

    def _render_kpi_grid(self, block: Dict[str, Any]) -> str:
        items = block.get("items") or []
        if not items:
            return ""
        header = ["指标", "数值", "变化"]
        lines = [self._markdown_row(header), self._markdown_separator(len(header))]
        for item in items:
            label = item.get("label") or ""
            value = f"{item.get('value', '')}{item.get('unit') or ''}"
            delta = self._format_delta(item.get("delta"), item.get("deltaTone"))
            lines.append(self._markdown_row([
                self._escape_text(label, for_table=True),
                self._escape_text(value, for_table=True),
                self._escape_text(delta, for_table=True),
            ]))
        return "\n".join(lines)

    def _render_widget(self, block: Dict[str, Any]) -> str:
        widget_type = (block.get("widgetType") or "").lower()
        title = block.get("title") or (block.get("props", {}) or {}).get("title")
        title_prefix = f"**{self._escape_text(title)}**\n\n" if title else ""

        if widget_type.startswith("chart.js"):
            chart_table = self._render_chart_as_table(block)
            return f"{title_prefix}{chart_table}".strip()
        if "wordcloud" in widget_type:
            cloud_table = self._render_wordcloud_as_table(block)
            return f"{title_prefix}{cloud_table}".strip()

        data_preview = ""
        try:
            data_preview = json.dumps(block.get("data") or {}, ensure_ascii=False)[:200]
        except Exception:
            data_preview = ""
        note = "> 数据组件暂不支持Markdown渲染"
        return f"{title_prefix}{note}" + (f"\n\n```\n{data_preview}\n```" if data_preview else "")

    # ===== 工具方法 =====

    def _render_chart_as_table(self, block: Dict[str, Any]) -> str:
        data = self._coerce_chart_data(block.get("data") or {})
        labels = data.get("labels") or []
        datasets = data.get("datasets") or []
        if not labels or not datasets:
            return "> 图表数据缺失，无法转为表格"

        headers = ["类别"] + [
            ds.get("label") or f"系列{idx + 1}"
            for idx, ds in enumerate(datasets)
        ]
        lines = [self._markdown_row(headers), self._markdown_separator(len(headers))]
        for idx, label in enumerate(labels):
            row_cells = [self._escape_text(self._stringify_value(label), for_table=True)]
            for ds in datasets:
                series = ds.get("data") or []
                value = series[idx] if idx < len(series) else ""
                row_cells.append(self._escape_text(self._stringify_value(value), for_table=True))
            lines.append(self._markdown_row(row_cells))
        return "\n".join(lines)

    def _render_wordcloud_as_table(self, block: Dict[str, Any]) -> str:
        items = self._collect_wordcloud_items(block)
        if not items:
            return "> 词云数据缺失，无法转为表格"

        lines = [
            self._markdown_row(["关键词", "权重", "类别"]),
            self._markdown_separator(3),
        ]
        for item in items:
            lines.append(
                self._markdown_row([
                    self._escape_text(item.get("word", ""), for_table=True),
                    self._escape_text(self._stringify_value(item.get("weight")), for_table=True),
                    self._escape_text(item.get("category", "") or "-", for_table=True),
                ])
            )
        return "\n".join(lines)

    def _render_cell_content(self, cell: Dict[str, Any]) -> str:
        blocks = cell.get("blocks") if isinstance(cell, dict) else None
        return self._render_blocks_as_text(blocks)

    def _render_blocks_as_text(self, blocks: List[Dict[str, Any]] | None) -> str:
        texts: List[str] = []
        for block in blocks or []:
            texts.append(self._render_block_as_text(block))
        return " ".join(filter(None, texts))

    def _render_block_as_text(self, block: Any) -> str:
        if isinstance(block, str):
            return self._escape_text(block, for_table=True)
        if not isinstance(block, dict):
            return ""
        block_type = block.get("type")
        if block_type == "paragraph":
            return self._render_inlines(block.get("inlines", []), for_table=True)
        if block_type == "heading":
            return self._escape_text(block.get("text") or "", for_table=True)
        if block_type == "list":
            items = []
            for sub in block.get("items") or []:
                items.append(self._render_blocks_as_text(sub))
            return "; ".join(filter(None, items))
        if block_type == "math":
            return f"${self._normalize_math(block.get('latex', ''))}$"
        if block_type == "code":
            return block.get("content", "") or ""
        if block_type == "widget":
            return self._escape_text(block.get("title") or "图表", for_table=True)
        if isinstance(block.get("blocks"), list):
            return self._render_blocks_as_text(block.get("blocks"))
        return self._escape_text(str(block), for_table=True)

    def _markdown_row(self, cells: List[str]) -> str:
        return "| " + " | ".join(cells) + " |"

    def _markdown_separator(self, count: int) -> str:
        return "| " + " | ".join(["---"] * max(1, count)) + " |"

    def _render_inlines(self, inlines: List[Any], for_table: bool = False) -> str:
        parts: List[str] = []
        for run in inlines or []:
            parts.append(self._render_inline_run(run, for_table=for_table))
        return "".join(parts)

    def _render_inline_run(self, run: Any, for_table: bool = False) -> str:
        if isinstance(run, dict):
            text = run.get("text", "")
            marks = run.get("marks") or []
        else:
            text = run if isinstance(run, str) else ""
            marks = []
        result = self._escape_text(text, for_table=for_table)
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            mtype = mark.get("type")
            if mtype == "bold":
                result = f"**{result}**"
            elif mtype == "italic":
                result = f"*{result}*"
            elif mtype == "underline":
                result = f"__{result}__"
            elif mtype == "strike":
                result = f"~~{result}~~"
            elif mtype == "code":
                result = f"`{result}`"
            elif mtype == "link":
                href = mark.get("href") or mark.get("value")
                href = str(href) if href else ""
                result = f"[{result}]({href})" if href else result
            elif mtype == "highlight":
                result = f"=={result}=="
            elif mtype == "subscript":
                result = f"~{result}~"
            elif mtype == "superscript":
                result = f"^{result}^"
            elif mtype == "math":
                latex = self._normalize_math(mark.get("value") or text)
                result = f"${latex}$" if latex else result
            # 颜色/字体等非通用标记直接降级为纯文本
        return result

    def _is_heading_duplicate(self, block: Dict[str, Any], chapter_title: str | None) -> bool:
        """判断首个heading是否与章节标题重复"""
        if not isinstance(block, dict) or block.get("type") != "heading":
            return False
        if not chapter_title:
            return False
        heading_text = block.get("text") or ""
        return self._normalize_heading_text(heading_text) == self._normalize_heading_text(chapter_title)

    def _normalize_heading_text(self, text: Any) -> str:
        """去除序号前缀并统一空白"""
        if not isinstance(text, str):
            return ""
        stripped = text.strip()
        # 去掉类似“1.”、“1.1”、“一、”
        for sep in (" ", "、"):
            if sep in stripped:
                maybe_prefix, rest = stripped.split(sep, 1)
                if self._looks_like_prefix(maybe_prefix):
                    stripped = rest.strip()
                    break
        else:
            parts = stripped.split(".", 1)
            if len(parts) == 2 and self._looks_like_prefix(parts[0]):
                stripped = parts[1].strip()
        return stripped

    @staticmethod
    def _looks_like_prefix(token: str) -> bool:
        """判断token是否像序号前缀"""
        if not token:
            return False
        if token.isdigit():
            return True
        chinese_numerals = set("一二三四五六七八九十零〇壹贰叁肆伍陆柒捌玖拾")
        return all(ch in chinese_numerals or ch == "." for ch in token)

    def _quote_lines(self, text: str) -> str:
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            prefix = "> " if line else ">"
            lines.append(f"{prefix}{line}")
        return "\n".join(lines)

    def _normalize_swot_items(self, raw: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not raw:
            return items
        for entry in raw:
            if isinstance(entry, str):
                items.append({"title": entry})
            elif isinstance(entry, dict):
                title = entry.get("title") or entry.get("label") or entry.get("text")
                detail = entry.get("detail") or entry.get("description")
                impact = entry.get("impact")
                priority = entry.get("priority")
                evidence = entry.get("evidence")
                items.append({
                    "title": title or "未命名要点",
                    "detail": detail,
                    "impact": impact,
                    "priority": priority,
                    "evidence": evidence,
                })
        return items

    def _normalize_pest_items(self, raw: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not raw:
            return items
        for entry in raw:
            if isinstance(entry, str):
                items.append({"title": entry})
            elif isinstance(entry, dict):
                title = entry.get("title") or entry.get("label") or entry.get("text")
                detail = entry.get("detail") or entry.get("description")
                items.append({
                    "title": title or "未命名要点",
                    "detail": detail,
                    "impact": entry.get("impact"),
                    "priority": entry.get("priority"),
                    "weight": entry.get("weight"),
                })
        return items

    def _coerce_chart_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        if "labels" in data or "datasets" in data:
            return data
        for key in ("data", "chartData", "payload"):
            nested = data.get(key)
            if isinstance(nested, dict) and ("labels" in nested or "datasets" in nested):
                return nested
        return data

    def _collect_wordcloud_items(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        props = block.get("props") or {}
        candidates: List[Any] = []
        for key in ("data", "words", "items"):
            value = props.get(key)
            if isinstance(value, list):
                candidates.append(value)
        data_field = block.get("data")
        if isinstance(data_field, list):
            candidates.append(data_field)
        elif isinstance(data_field, dict):
            if isinstance(data_field.get("items"), list):
                candidates.append(data_field.get("items"))
            if isinstance(data_field.get("words"), list):
                candidates.append(data_field.get("words"))

        items: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def push(word: str, weight: Any, category: str) -> None:
            key = f"{word}::{category}"
            if key in seen:
                return
            seen.add(key)
            items.append({"word": word, "weight": weight, "category": category})

        for candidate in candidates:
            for entry in candidate or []:
                if isinstance(entry, dict):
                    word = entry.get("word") or entry.get("text") or entry.get("label")
                    if not word:
                        continue
                    weight = entry.get("weight") or entry.get("value")
                    category = entry.get("category") or ""
                    push(str(word), weight, str(category))
                elif isinstance(entry, (list, tuple)) and entry:
                    word = entry[0]
                    weight = entry[1] if len(entry) > 1 else ""
                    category = entry[2] if len(entry) > 2 else ""
                    push(str(word), weight, str(category))
                elif isinstance(entry, str):
                    push(entry, "", "")
        return items

    def _escape_text(self, text: Any, for_table: bool = False) -> str:
        if text is None:
            return ""
        value = str(text)
        if for_table:
            value = value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")
        return value.strip()

    def _stringify_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, dict):
            # 优先取常见数值字段
            for key in ("y", "value"):
                if key in value:
                    return str(value[key])
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        if isinstance(value, list):
            return ", ".join(self._stringify_value(v) for v in value)
        return str(value)

    def _normalize_math(self, raw: Any) -> str:
        if not isinstance(raw, str):
            return ""
        text = raw.strip()
        patterns = [
            ("$$", "$$"),
            ("\\[", "\\]"),
            ("\\(", "\\)"),
        ]
        for start, end in patterns:
            if text.startswith(start) and text.endswith(end):
                return text[len(start) : -len(end)].strip()
        return text

    def _format_delta(self, delta: Any, tone: Any) -> str:
        if delta is None:
            return ""
        prefix = ""
        tone_val = (tone or "").lower()
        if tone_val in ("up", "increase", "positive"):
            prefix = "▲ "
        elif tone_val in ("down", "decrease", "negative"):
            prefix = "▼ "
        return f"{prefix}{delta}"

    def _fallback_unknown(self, block: Dict[str, Any]) -> str:
        try:
            payload = json.dumps(block, ensure_ascii=False, indent=2)
        except Exception:
            payload = str(block)
        logger.debug(f"未识别的区块类型，使用JSON兜底: {block}")
        return f"```json\n{payload}\n```"


__all__ = ["MarkdownRenderer"]
