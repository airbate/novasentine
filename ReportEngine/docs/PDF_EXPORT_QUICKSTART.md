# PDF导出功能快速启动

## 立即开始

### 1. 启动系统

```bash
# 设置环境变量（macOS必需）
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

# 启动Flask应用
python app.py
```

### 2. 生成报告

1. 在浏览器中打开 `http://localhost:5000`
2. 启动 Insight、Media、Query Engine
3. 输入搜索主题，点击搜索
4. 切换到 Report Engine 标签
5. 点击"生成最终报告"

### 3. 导出PDF

报告生成完成后：
1. 点击"**下载PDF**"按钮
2. 系统自动：
   - 分析报告内容
   - 优化布局参数
   - 生成高质量PDF
   - 自动下载文件

## 快速测试

想立即看到效果？运行测试脚本：

```bash
# 设置环境变量
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH

# 运行测试（生成示例PDF）
python test_pdf_optimized.py

# 查看结果
open test_pdf_optimized.pdf
```

测试会生成：
- ✅ 包含10个KPI卡片的报告
- ✅ 复杂的8列表格
- ✅ 多个图表和色块
- ✅ 自动优化的布局

## 优化效果对比

系统会自动：

| 问题 | 优化前 | 优化后 |
|------|--------|--------|
| KPI数值溢出 | ⚠️ 字号固定32px，长数值溢出 | ✅ 自动缩小到28px或24px |
| KPI布局拥挤 | ⚠️ 固定2列，10个卡片显得拥挤 | ✅ 自动调整为3列 |
| 表格字体过大 | ⚠️ 8列表格字体过大 | ✅ 字号从13/12px缩小到11/10px |
| 长文本难读 | ⚠️ 行高固定1.6 | ✅ 自动增加到1.8 |

## 查看优化日志

想了解系统做了哪些优化？

```bash
# 查看最新的优化日志
cat logs/pdf_layouts/layout_*.json

# 或打开保存的配置文件
cat test_layout_config.json
```

日志示例：
```json
{
  "optimizations": [
    "KPI数值过长(14字符)，字号从32调整为28",
    "KPI卡片较多(10个)，每行列数从2调整为3",
    "表格列数较多(8列)，缩小字号和内边距"
  ]
}
```

## 常见问题

### Q: 为什么PDF生成需要几秒钟？
A: 首次生成需要加载字体文件和分析文档，后续会更快。

### Q: 可以禁用自动优化吗？
A: 可以，在API中设置 `optimize=false`：
```bash
curl "http://localhost:5000/api/report/export/pdf/TASK_ID?optimize=false"
```

### Q: 如何自定义布局参数？
A: 参考 [PDF_EXPORT_GUIDE.md](PDF_EXPORT_GUIDE.md) 中的"配置选项"章节。

## 技术亮点

✨ **智能布局分析**
- 自动检测KPI数量、表格复杂度、文本长度
- 根据内容特征动态调整参数

✨ **无损质量**
- 使用WeasyPrint专业PDF引擎
- 完整保留CSS样式
- 完美支持中文字体

✨ **开箱即用**
- 前端一键导出
- 无需额外配置
- 自动应用最佳实践

## 下一步

- 📖 阅读完整文档：[PDF_EXPORT_GUIDE.md](PDF_EXPORT_GUIDE.md)
- 🧪 运行测试：`python test_pdf_optimized.py`
- 🎨 自定义布局：修改配置参数
- 🚀 集成到生产：通过API批量导出

## 问题反馈

遇到问题？
1. 查看 [PDF_EXPORT_GUIDE.md](PDF_EXPORT_GUIDE.md) 的"故障排除"章节
2. 检查 `logs/pdf_layouts/` 目录的优化日志
3. 提交Issue到项目仓库

---

享受全新的PDF导出体验！ 🎉
