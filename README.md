# mentor-analysis · 保研导师深度分析

> 分析某位导师之前，先看数据：**科研实力 · 一作让渡 · 一作集中度 · 成果压制 · 延毕率**，五维量化，不靠猜。

![CI](https://github.com/THC-ENG/mentor-analysis/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)

## 这个项目有两种用法

**① 作为 AI 助手的 Skill（推荐给使用 AI 助手的同学）**
`SKILL.md` 是一份可直接加载给 AI 助手（如 WorkBuddy）执行的方法论：当你说"分析一下 XX 老师"，AI 会自动完成论文检索 → 分区标注 → 知网延毕率推断 → 五维报告的全流程。无需自己动手收集数据。

**② 作为独立 Python 工具（不依赖 AI）**
`scripts/` 下的脚本纯标准库、零依赖，任何人都可以手动收集数据（OpenAlex 自动抓取 + 手工补填分区 + 知网查询）后离线计算五维指标。

两种用法共享同一套数据格式与判定标准，下文"快速开始"按独立工具方式说明，AI 用法见 [`SKILL.md`](./SKILL.md)。

## 如何作为 Skill 安装（用法 ①）

把项目给 AI 助手用时，先让 AI 拿到本仓库的全部文件（SKILL.md + scripts/ + references/），再让它加载 `SKILL.md`：

```bash
# 方式 A：git clone（推荐，保持更新）
git clone https://github.com/THC-ENG/mentor-analysis.git

# 方式 B：下载 zip 解压
#   https://github.com/THC-ENG/mentor-analysis/archive/refs/tags/v1.0.0.zip
```

然后对你的 AI 助手说："**读取 mentor-analysis/SKILL.md，按其中的方法分析 XX 老师**" 即可。

- **WorkBuddy 用户**：把 `mentor-analysis` 目录放进 `~/.workbuddy/skills/`（用户级技能目录）后重启会话，之后直接说"分析 XX 老师"即可自动触发。
- **其他 AI 助手（Claude/ChatGPT 等）**：把 `SKILL.md` 内容粘贴进对话或作为 system prompt 的一部分，并确保它能访问本目录下的 `scripts/` 与 `references/` 文件。

## 为什么要用它

在读研/保研/申博之前，用公开数据回答这些关键问题：

- 这个组**整体科研实力**怎么样？—— 一二区论文占比
- 导师**会不会抢学生一作**？—— 导师本人一作占比
- 组里一作是否被**"嫡系/关系户"垄断**？—— 一作集中度（top1 / HHI）
- 导师**压不压成果**？—— 三四区论文占比
- 学生**能不能按时毕业**？—— 从知网毕业论文编号推断的延毕率

## 五维指标

| # | 维度 | 指标 | 回答的问题 |
|---|------|------|-----------|
| 1 | 科研实力 | 一二区论文占比 | 组内成果质量如何？ |
| 2 | 一作让渡 | 导师一作占比 | 导师是否把一作留给学生？ |
| 3 | 一作集中度 | top1/top3 占比、HHI | 一作是否被少数人垄断？ |
| 4 | 成果压制 | 三四区论文占比 | 是否压成果 / 毕业要求是否过高？ |
| 5 | 毕业保障 | 硕博延毕率 | 学生能否按时毕业？ |

**延毕率推断原理**：知网毕业论文封面左上角的论文编号前 4 位 = 入学年份（学号年份），落款时间 = 学位授予时间，两者相减即毕业用时（如 `2019XXXX` + `2022年6月` = 3 年毕业）。

## 快速开始

需要 **Python 3.9+**，无第三方依赖（纯标准库）。

### 方式一：自动抓取（OpenAlex）

```bash
# 1. 从 OpenAlex 自动抓取导师近五年论文 → papers.json
python scripts/fetch_openalex.py "Wei Zhang" \
    --institution "Harbin Institute of Technology" \
    --years 5 --output papers.json

# 2. 手工补填 papers.json 中的 zone 字段（期刊分区，见 references/data-sources.md）
#    —— OpenAlex 不提供分区信息

# 3. 准备 theses.json（知网毕业论文，结构见下方）
# 4. 计算五维指标
python scripts/compute_metrics.py papers.json theses.json \
    --mentor "Wei Zhang" \
    --recent-years 5 --senior --group-size 8 \
    --output metrics.json
```

### 方式二：直接跑示例

```bash
python scripts/compute_metrics.py examples/papers.json examples/theses.json \
    --mentor "Zhang Wei" --output examples/metrics_example.json
# 示例报告见 examples/report-example.md
```

### 运行测试

```bash
python -m unittest discover -s tests -v     # 无 pytest 依赖
# 或
pytest tests/ -v
```

## JSON 数据格式

**papers.json**（每篇论文一条）：

```json
{
  "papers": [
    {
      "title": "论文标题",
      "year": 2023,
      "journal": "期刊名",
      "zone": "一区",
      "authors": ["Zhang Wei", "Li Ming"],
      "first_author": "Li Ming",
      "co_first": [],
      "corresponding": ["Zhang Wei"],
      "type": "article"
    }
  ]
}
```

`zone` 取值：`一区/二区/三区/四区` 或 `Q1–Q4`，查不到填 `null`。

**theses.json**（每篇毕业论文一条，来自知网封面）：

```json
{
  "theses": [
    {
      "student": "Li Ming",
      "degree": "博士",
      "enroll_year": 2018,
      "grant_year": 2023,
      "grant_month": 6,
      "note": ""
    }
  ]
}
```

- `enroll_year`：论文编号前 4 位（入学年份）
- `grant_year`：落款时间年份（学位授予年份）
- `degree`：`硕士 / 博士 / 硕博连读 / 直博`

## 参数说明

`compute_metrics.py`：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--mentor` | 必填 | 导师姓名（别名逗号分隔，如 `"Zhang Wei,Wei Zhang"`） |
| `--recent-years` | 5 | 只统计最近 N 年论文（传 0 不过滤） |
| `--ms-std` / `--phd-std` | 3 / 5 | 硕博标准学制（2 年制专硕传 `--ms-std 2`） |
| `--senior` | 关 | 导师为资深教授，维度 2 判定更严格 |
| `--group-size` | 5 | 组内在读人数估算，维度 2 判定校准 |
| `--output` | metrics.json | 输出路径 |
| `--no-judge` | 关 | 只出统计量，不出判定标签 |

## 目录结构

```
mentor-analysis/
├── SKILL.md                    # 完整方法论（供 AI 助手加载执行）
├── scripts/
│   ├── compute_metrics.py      # 五维指标计算（纯标准库）
│   └── fetch_openalex.py       # OpenAlex 自动抓取论文 → papers.json
├── references/
│   ├── data-sources.md         # 数据源：论文检索 / 期刊分区 / 知网
│   └── graduation-method.md    # 延毕率推断方法论（学号年份 vs 授予时间）
├── assets/
│   └── report-template.md      # 分析报告模板
├── examples/                   # 示例数据 + 示例报告（匿名化）
├── tests/                      # 单元测试（20 项）
├── .github/workflows/ci.yml    # GitHub Actions CI（多版本 Python 跑测试）
└── LICENSE                     # MIT
```

## 常见问题

**Q: 分区怎么查？**
A: 用 WebSearch 查"《期刊名》 中科院分区"，或 LetPub / EasyScholar。详见 `references/data-sources.md`。计算机学科看顶会（CCF A 类），不适用期刊分区。

**Q: 没有知网权限怎么办？**
A: 用万方 / 维普 / 学校研究生院公示 / WebSearch"学校 导师 博士论文 年份"降级获取，详见 `references/graduation-method.md`。

**Q: 论文数据不全怎么办？**
A: OpenAlex 中文覆盖有限，建议与导师主页、Google Scholar 交叉补充；报告会标注数据局限。

## 合规与免责声明

- **数据来源合规**：OpenAlex 为开放许可（CC0，详见其 API 条款）；知网检索必须遵守 CNKI 使用条款，本项目仅提供方法论，**不绕过任何付费墙**，请在有合法访问权限的前提下使用。
- **个人使用**：本项目面向个人升学决策参考，示例数据均已匿名化。请勿用于商业用途或对导师、学生进行公开评价。
- **判定阈值是经验值**：五维判定阈值为经验设定，不同学科（计算机顶会 vs 生医期刊 vs 化学材料）差异显著，请结合学科背景解读。本工具输出的是**统计数据**，不是对任何人的评价。

## License

[MIT](./LICENSE)
