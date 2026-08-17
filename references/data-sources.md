# 数据源与检索方法参考

本文件汇总导师分析所需的全部数据来源与检索技巧，供执行时参考。按"论文检索 → 期刊分区 → 毕业论文检索"三个环节组织。

---

## 1. 论文检索（近五年论文）

### 1.1 OpenAlex API（首选，免费、无需 key、支持中文作者搜索）

OpenAlex 是开放学术图谱，覆盖期刊论文、会议论文，支持按作者名检索并返回作者完整列表、期刊、年份。

- 作者搜索（先定位作者 ID）：
  ```
  https://api.openalex.org/authors?search=Wei%20Zhang&filter=last_known_institutions.id:I12345
  ```
  `last_known_institutions` 过滤可缩小同名范围（需先查到单位 ID）。若不知道单位 ID，直接 search 后在结果中人工筛选。
- 按作者 ID 拉取论文（每页 25 条，`per-page` 可调）：
  ```
  https://api.openalex.org/works?filter=author.id:A1234567890&sort=publication_date:desc&per-page=100
  ```
  返回字段：`title`、`publication_year`、`primary_location.source.display_name`（期刊名）、`authorships[].author.display_name`（作者列表，顺序即署名顺序）、`authorships[].is_corresponding`（是否为通讯作者）、`type`（article/review 等）。
- 中文检索技巧：很多中文期刊论文在 OpenAlex 里没有，但可尝试 `https://api.openalex.org/works?filter=title.search:关键词` 找该组的中文代表作。
- 使用方式：WebFetch 直接访问 API URL 即可（返回 JSON）；或用 Bash + curl/python 拉取。建议用 Python 脚本一次性拉取并整理，见下方"整理为 JSON"。
- 限流：无 key 时约 10 req/s，够用。若遇 403，加 `mailto` 参数（OpenAlex 官方建议）：`&mailto=your@email.com`。

### 1.2 Semantic Scholar API（备用，免费）

- 作者搜索：`https://api.semanticscholar.org/graph/v1/author/search?query=Wei+Zhang&fields=name,affiliations,paperCount`
- 作者论文：`https://api.semanticscholar.org/graph/v1/author/{authorId}/papers?fields=title,year,venue,authors,publicationTypes&limit=100`
- 特点：英文论文覆盖好，中文覆盖差；有 rate limit（无 key 时 100 req/5min）。

### 1.3 Google Scholar / 百度学术（WebSearch 兜底）

- 用 WebSearch 搜：`导师姓名 + 单位 + 论文`、`"Wei Zhang" "Fudan" chemistry`。
- 搜索结果里提取：期刊名、年份、作者顺序。Google Scholar 个人主页（`scholar.google.com/citations?user=...`）是最理想来源——有完整论文列表和年份。
- 百度学术（xueshu.baidu.com）对中文论文友好，WebFetch 可抓取。

### 1.4 导师主页 / 学院官网

- 学院官网"师资队伍"页面通常列出导师论文列表（含期刊、年份、作者）。
- WebFetch 导师个人主页（实验室主页 Lab Homepage）→ 提取 Publications 部分。
- 这是最可靠的来源，优先使用；API 检索结果可与主页列表交叉比对，避免遗漏。

### 1.5 人工核实清单

- 剔除：非本人成果（同名他人）、仅挂名非通讯非一作的论文（可计入总量但标注）、已撤稿论文。
- 标注：综述（review）单独计数，不参与一作/分区主导判断。
- 中文名拼音多写法：Wei Zhang / W. Zhang / Zhang, Wei 均算同一人。

---

## 2. 期刊分区查询

### 2.1 中科院分区（用户语境默认口径）

- 官方：**中科院文献情报中心分区表** `https://www.fenqubiao.com`（需注册，部分查询免费；2025 年后为"期刊分区表"）。
- 免费替代：
  - **LetPub** `https://www.letpub.com.cn/index.php?page=journalapp` —— 输入期刊名可查中科院分区（大类分区，含升级版）。
  - **EasyScholar**（浏览器插件/网站）—— 直接显示中科院分区。
- 查询方式：WebSearch"《期刊名》 中科院分区 2024"或 WebFetch LetPub 期刊页面。
- 口径说明：中科院分区有"基础版"和"升级版"，升级版不再分小类、大类按期刊整体水平划区；报告里注明用的是哪个版本。旧分区（基础版）1 区多为顶级期刊，升级版略宽松，解读时注意。

### 2.2 JCR 分区（Q1–Q4）

- 官方：Web of Science JCR（需订阅）。
- 免费替代：WebSearch"期刊名 JCR 分区 Q"；或 LetPub 页面同时给出 JCR 分区。
- 当只查到 JCR 分区时，报告注明"JCR Q1 ≈ 中科院一区（不完全等价）"。

### 2.3 无分区的处理

- 会议论文（如 CVPR/ICML/NeurIPS，计算机学科）：不适用期刊分区。计算机学科需单独统计"顶会（A 类）占比"——用 CCF 推荐目录 A 类/B 类判断。
- 中文核心期刊（北大核心/CSCD）：分区体系不同，标注"中文核心"即可，不并入中科院分区统计。
- 查不到 → `zone: null`。

### 2.4 学科差异警示

- 数学/理论物理/计算机（顶会主导）等学科，用中科院分区衡量科研实力会失真，报告中改用学科内认可度（如顶会 A 类占比）。
- 生医/化学/材料等期刊主导学科，中科院分区是主要口径。

---

## 3. 知网硕博毕业论文检索（延毕率）

### 3.1 知网（CNKI）检索

- 地址：`https://www.cnki.net`（需要校园网/机构账号；部分学校图书馆可校外访问）。
- 检索策略：高级检索 → 学位论文库 → 检索条件"作者 = 学生姓名 OR 导师 = 导师姓名" + "单位 = 学校"；或直接搜"学校 + 导师 + 学位论文"。
- 打开论文详情页：显示题名、作者、导师、学位授予单位、学位年度、论文类型（硕士/博士）。
- **关键信息提取**（在 PDF 全文的第一页封面/题名页）：
  1. 左上角论文编号：形如 `2019XXXX`（前 4 位 = 入学年份）。
  2. 落款时间：封面或题名页底部，形如 `2022年6月`（答辩/学位授予时间）。
  3. 论文密级与分类号不影响判断。
- 知网详情页的"学位年度"字段也可作为授予年份交叉验证。

### 3.2 降级方案（无知网权限时）

1. **万方数据** `https://www.wanfangdata.com.cn`（学位论文库，部分免费）。
2. **维普** `https://www.cqvip.com`。
3. **WebSearch 检索**：`"学校" "导师姓名" 博士论文 2023` —— 学位论文题目常出现在学校研究生院公示、新闻、教师主页中，可推断"谁、哪年毕业"。
4. **学校研究生院官网**：公示的"博士学位论文答辩信息"、优秀学位论文名单、就业新闻（"XX 同学 2023 年博士毕业"）。

### 3.3 检索记录模板

对每篇论文记录：

```json
{
  "student": "李四",
  "degree": "博士",
  "enroll_year": 2019,
  "grant_year": 2024,
  "grant_month": 6,
  "thesis_no": "2019XXXX",
  "title": "基于XX的研究",
  "source": "知网"
}
```

详见 `graduation-method.md` 的完整推断方法论。
