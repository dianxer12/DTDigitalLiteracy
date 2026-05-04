# 架构设计 — 学术研究分析平台

## 设计原则

- **研究为中心**：顶层组织单元是「研究」，每个研究独立管理数据和分析
- **零技术门槛**：护理学研究生无需接触 R/Python 代码，全流程 GUI
- **预设驱动**：预设量表配置 + 预设分析模型，减少配置负担
- **中文友好**：所有界面、报告、图表均为中文

## 信息架构

```
研究工作台 (app.py)
│
├── 📊 数据管理 (pages/1_数据管理.py)
│   ├── [Tab] 上传数据
│   └── [Tab] 构建维度
│
├── ⚙️ fsQCA 分析 (pages/2_fsQCA分析.py)
│   └── 模型选择 → 变量配置 → 校准 → 运行
│
└── 📋 分析结果 (pages/3_分析结果.py)
    ├── [Tab] 分析报告
    ├── [Tab] 图表
    ├── [Tab] 数据表
    └── [Tab] 配置与日志
```

每个页面顶部统一放置**研究选择器**。

## 文件存储结构

```
workspace/
  studies/
    study_001/                    ← 一个研究
      study.json                  ← 研究元数据
      datasets/
        dataset_xxx/
          dataset.json
          original/               ← 原始上传文件
          prepared/data.csv       ← 清洗后数据
      analyses/
        run_xxx/                  ← 一次 fsQCA 分析
          config.json
          run.json
          status.json
          input/
          output/
            tables/
            figures/
            files/
            report/
            logs/
```

## study.json 格式

```json
{
  "study_id": "study_20260504_120000_abc12345",
  "name": "双师型护理教师数字素养研究",
  "description": "本研究旨在探讨...",
  "created_at": "2026-05-04T12:00:00"
}
```

## 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| 存储层 | utils/file_store.py | 研究/数据集/分析记录的 CRUD，文件路径管理 |
| 数据工具 | utils/dataset_utils.py | 数据加载、元数据、分位数计算 |
| 计分引擎 | utils/scoring.py | 维度定义、反向计分、聚合计算 |
| 预设定义 | utils/presets.py | OS/WE/DC/DL 量表预设，变量名→中文标签映射 |
| fsQCA 引擎 | utils/fsqca_runner.py | 创建 run、调用 R 脚本、生成图表 |
| R 脚本 | scripts/run_fsqca.R | QCA 计算本体（校准、真值表、最小化） |
| 展示工具 | utils/display_utils.py | Streamlit 通用展示组件 |

## 技术栈

- **前端**: Streamlit（Python）
- **后端/计算**: R（QCA 包）
- **图表**: matplotlib（Python）+ ggplot2（R 备选）
- **存储**: 文件系统（JSON + CSV + XLSX）
