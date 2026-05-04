# 科研数据分析平台

基于 Python + Streamlit + R 的本地科研数据分析平台，面向 fsQCA（模糊集定性比较分析）全流程，支持从原始问卷到发表级输出的完整研究管道。

## 功能概览

- **研究管理** — 多研究创建/切换/删除，数据完全隔离
- **数据集管理** — 上传 Excel/CSV 问卷数据，自动元数据与描述统计
- **维度计分** — 反向计分、维度聚合（均值/总和），内置「双师型护理教师数字素养」四大量表预设（OS/WE/DC/DL），支持自定义编辑维度配置
- **fsQCA 分析方案** — 可视化配置结果变量、条件变量、校准锚点，一键运行或保存为可复用方案
- **发表级输出** — 真值表、必要条件分析、复杂解/精简解/中间解、组态路径表（核心/边缘区分）、SVG 图表、Markdown 报告、Excel 汇总
- **AI 解读** — 支持 DeepSeek / OpenAI / Kimi / Qwen / Zhipu / 自定义 OpenAI-compatible 接口，针对图表和表格生成论文写作可直接使用的中文解读

## 目录结构

```text
research_analysis_app/
  app.py                          # 首页 — 研究总览 + 仪表盘
  pages/
    1_数据集管理.py                # 上传数据、查看元数据、构建维度得分
    2_新建fsQCA分析.py             # 创建分析方案、配置变量与校准、运行分析
    3_分析结果.py                  # 查看表格/图表、生成 AI 解读
  utils/
    ai_interpreter.py             # 多平台 AI 解读（OpenAI-compatible）
    dataset_utils.py              # 文件导入、列元数据、分位数阈值
    display_utils.py              # DataFrame 渲染、下载按钮
    file_store.py                 # 研究/数据集/方案/运行的 CRUD
    fsqca_runner.py               # R 脚本调度、Python 图表生成、报告构建
    presets.py                    # 四大量表预设定义（OS/WE/DC/DL）
    scoring.py                    # 反向计分 + 维度得分计算
    study_selector.py             # 侧边栏研究选择器
    style.py                      # 全局 CSS + 侧边栏导航
  scripts/run_fsqca.R             # fsQCA 分析核心（校准 → 必要条件 → 真值表 → 三个解 → 稳健性）
  sample_data/sample_fsqca_data.csv
  tests/
  workspace/studies/              # 所有研究数据存储（文件系统，无需数据库）
  requirements.txt
```

## 安装 Python 依赖

```bash
cd research_analysis_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 安装 R 依赖

需要先安装 R，并确保命令行可以运行 `Rscript`。

```r
install.packages(c("QCA", "jsonlite", "readr", "dplyr", "writexl"))
```

## 启动 Streamlit

```bash
cd research_analysis_app
source .venv/bin/activate
streamlit run app.py
```

## 使用流程

1. **创建研究** — 在首页输入研究名称，系统创建独立工作空间
2. **上传数据** — 进入「数据集管理」页，上传 Excel 或 CSV 问卷数据。系统自动生成列元数据、缺失统计、描述统计
3. **构建维度** — 选择内置量表预设或自定义维度配置，将原始题项转换为可用于 fsQCA 的维度得分。支持反向计分、修改题项归属、调整聚合方式
4. **创建分析方案** — 进入「新建fsQCA分析」页，选择维度数据集，配置结果变量、条件变量和校准锚点（分位数自动计算或手动输入），保存方案
5. **运行分析** — 点击运行，系统创建独立 run 目录并调用 R 脚本执行分析
6. **查看结果** — 进入「分析结果」页查看真值表、必要条件分析、三条解路径（复杂/精简/中间）、组态配置表、柱状图、Markdown 报告
7. **AI 解读** — 配置 API Token，对关键图表或数据表生成中文论文写作解读

## fsQCA 输出

每次运行在 `analyses/run_xxx/` 下生成：

```text
run_xxx/
  run.json                        # 运行元数据
  config.json                     # 分析参数与变量标签
  status.json                     # 运行状态（created/running/completed/failed）
  input/selected_data.csv         # 参与分析的校准前数据
  output/
    tables/
      calibration_thresholds.csv  # 各变量校准锚点
      calibrated_data.csv         # 校准后数据
      necessity_high.csv          # 必要条件分析（高结果）
      necessity_low.csv           # 必要条件分析（低结果）
      truth_table_high.csv        # 真值表
      config_table_high.csv       # 组态路径配置表（核心/边缘区分）
      solution_metrics_high.csv   # 三条解路径指标（一致性、覆盖率）
      solution_overall_high.csv   # 总体解指标
    figures/
      solution_bars.svg           # 组态路径柱状图（一致性 + 覆盖率）
      config_table.svg            # 组态配置表可视化
    files/
      qca_results.xlsx            # 所有结果表汇总 Excel
      qca_solutions.txt           # 解路径文本
    report/
      report.md                   # 结构化分析报告（中文）
    ai_interpretations/
      interpretations.json        # AI 解读缓存
    logs/
      stdout.log / stderr.log     # R 脚本运行日志
```

## 内置量表预设

适用于「双师型护理教师数字素养」研究的四大量表：

| 量表 | 简称 | 题项数 | 维度数 |
|------|------|--------|--------|
| 组织支持 | OS | 23 | 3 + 总量表（含反向题） |
| 工作投入 | WE | 17 | 3 + 总量表 |
| 数字胜任力 | DC | 22 | 6 + 总量表 |
| 数字素养 | DL | 33 | 5 + 总量表 |

维度配置可在数据集页面自定义编辑，也可通过 `utils/presets.py` 扩展更多量表。

## AI 解读配置

支持 OpenAI-compatible API，内置以下平台预设：

| 平台 | 模型 | 说明 |
|------|------|------|
| DeepSeek | deepseek-chat | 推荐，性价比高 |
| OpenAI | gpt-4o-mini | OpenAI 官方 |
| Kimi | kimi-k2-0711-preview | Moonshot |
| Qwen | qwen-plus | 阿里云百炼/通义千问 |
| Zhipu | glm-4.5-flash | 智谱 GLM |
| Custom | 自定义 | 任意 OpenAI-compatible 服务 |

需要在分析结果页配置 API Token 后使用。
