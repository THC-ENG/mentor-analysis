#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_metrics.py — 保研导师分析五维指标计算脚本

输入两份 JSON 数据（论文 + 毕业论文），输出 5 个维度的统计指标与判定标签，
供 AI 生成最终分析报告使用。脚本离线运行，不依赖网络。

用法：
    python compute_metrics.py papers.json theses.json \
        --mentor "张三" \
        --ms-std 3 --phd-std 5 \
        --recent-years 5 \
        --senior --group-size 8 \
        --output metrics.json

参数说明：
    papers.json   论文数据（见下方 SCHEMA）
    theses.json   毕业论文数据（见下方 SCHEMA）
    --mentor      导师姓名（用于一作归属判断，支持中英文别名，逗号分隔）
    --ms-std      硕士标准学制（默认 3 年）
    --phd-std     博士标准学制（默认 5 年）
    --recent-years 只统计最近 N 年发表的论文（默认 5；传 0 或负数表示不过滤）
    --senior      导师为资深教授（正高职称/组内学生多），维度2 抢一作判定更严格
    --group-size  课题组在读学生人数估算（默认 5），用于维度2 判定校准
    --output      输出 JSON 路径（默认 metrics.json）
    --no-judge    只出统计量，不出判定标签

输出指标（对应 SKILL.md 五个维度）：
    1. zone_ratio       一二区占比（科研实力）
    2. mentor_first     导师一作占比（是否抢学生一作）
    3. first_concen     一作集中度（top1/top3 占比、HHI，排查关系户）
    4. zone34_ratio     三四区占比（是否压成果）
    5. delay_ratio      延毕率（毕业保障）

======================= JSON SCHEMA =======================

papers.json:
{
  "papers": [
    {
      "title": "论文标题",
      "year": 2023,                    // 发表年份
      "journal": "期刊名",              // 期刊/会议名
      "zone": "一区",                   // 分区: 一区/二区/三区/四区/Q1/Q2/Q3/Q4/中文核心，或 null
      "authors": ["张三", "李四", "王五"],  // 作者完整列表（按署名顺序）
      "first_author": "李四",            // 一作姓名（可与 authors[0] 不同，用于共一场景）
      "co_first": ["李四", "王五"],      // 可选：共一作列表
      "corresponding": ["张三"],         // 可选：通讯作者列表
      "type": "article"                 // article / review，可选
    }
  ]
}

theses.json:
{
  "theses": [
    {
      "student": "李四",
      "degree": "博士",                 // 硕士/博士/直博/硕博连读
      "enroll_year": 2019,              // 论文编号前 4 位（入学年份）
      "grant_year": 2024,               // 落款时间年份（学位授予年份）
      "grant_month": 6,                 // 可选：落款月份
      "note": "疑似硕博连读"             // 可选：校准说明，原样输出
    }
  ]
}

======================= 判定阈值（经验值） =======================

维度1 一二区占比:  >=0.60 强 | 0.40-0.60 中等 | <0.40 一般
维度2 导师一作占比: >=0.40 风险高 | 0.20-0.40 需观察 | <0.20 健康
维度3 一作集中度:   top1>=0.50 或 HHI>=0.40 高度集中 | top1 0.25-0.50 轻度 | top1<0.25 均匀
维度4 三四区占比:   >=0.40 压成果/灌水 | 0.15-0.40 正常 | <0.15 严进严出警示
维度5 延毕率:       >=0.40 差 | 0.20-0.40 有风险 | <0.20 良好
"""

import argparse
import json
import math
import sys
from collections import Counter

# ---------- 输出编码兜底 ----------
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ---------- 分区解析 ----------
ZONE_MAP = {
    "一区": 1, "1区": 1, "1": 1, "Q1": 1, "q1": 1,
    "二区": 2, "2区": 2, "2": 2, "Q2": 2, "q2": 2,
    "三区": 3, "3区": 3, "3": 3, "Q3": 3, "q3": 3,
    "四区": 4, "4区": 4, "4": 4, "Q4": 4, "q4": 4,
}


def parse_zone(zone):
    """把分区字符串转成 1-4 的整数；无法识别返回 None。"""
    if zone is None:
        return None
    s = str(zone).strip()
    if s in ZONE_MAP:
        return ZONE_MAP[s]
    return None


# ---------- 导师姓名匹配 ----------
def build_mentor_names(mentor_arg):
    """导师姓名别名集合：逗号/顿号分隔，全小写去空白。"""
    names = set()
    for chunk in mentor_arg.split(","):
        chunk = chunk.strip()
        if chunk:
            names.add(chunk.lower())
    return names


def is_mentor(name, mentor_names):
    if not name:
        return False
    return str(name).strip().lower() in mentor_names


# ---------- 维度1 & 4：分区占比 ----------
def zone_stat(papers):
    zoned = [p for p in papers if parse_zone(p.get("zone")) is not None]
    total = len(zoned)
    if total == 0:
        return {
            "zoned_total": 0,
            "zone1": 0, "zone2": 0, "zone3": 0, "zone4": 0,
            "zone12_ratio": None, "zone34_ratio": None,
            "zone12_count": 0, "zone34_count": 0,
        }
    counts = Counter(parse_zone(p.get("zone")) for p in zoned)
    z1 = counts.get(1, 0)
    z2 = counts.get(2, 0)
    z3 = counts.get(3, 0)
    z4 = counts.get(4, 0)
    return {
        "zoned_total": total,
        "zone1": z1, "zone2": z2, "zone3": z3, "zone4": z4,
        "zone12_count": z1 + z2,
        "zone34_count": z3 + z4,
        "zone12_ratio": round((z1 + z2) / total, 3),
        "zone34_ratio": round((z3 + z4) / total, 3),
    }


def judge_zone12(ratio):
    if ratio is None:
        return "无分区数据"
    if ratio >= 0.60:
        return "科研实力强（一二区占比高）"
    if ratio >= 0.40:
        return "中等偏上"
    return "实力一般或期刊选择保守"


def judge_zone34(ratio, paper_count):
    if ratio is None:
        return "无分区数据"
    if ratio >= 0.40:
        return "压成果/灌水风险高"
    if ratio >= 0.15:
        return "正常区间"
    # 低占比 + 低总量 → 严进严出警示
    if paper_count < 10:
        return "占比极低且总量少：疑似严进严出，毕业难度需警惕"
    return "占比低：可能只发好刊，注意毕业要求"


# ---------- 维度2：导师一作占比 ----------
def mentor_first_stat(papers, mentor_names):
    total = len(papers)
    if total == 0:
        return {"total": 0, "mentor_first_count": 0, "mentor_first_ratio": None,
                "mentor_first_list": [], "student_second_list": []}

    mentor_first_list = []
    student_second_list = []
    for p in papers:
        authors = p.get("authors") or []
        first = p.get("first_author")
        if first and is_mentor(first, mentor_names):
            mentor_first_list.append(p.get("title", "?"))
            # 检查学生是否为第二作者（共一列表排除导师后）
            second = authors[1] if len(authors) >= 2 else None
            if second and not is_mentor(second, mentor_names):
                student_second_list.append(p.get("title", "?"))
            continue
        # 共一作场景：共一列表里有导师
        co_first = p.get("co_first") or []
        if any(is_mentor(n, mentor_names) for n in co_first):
            mentor_first_list.append(p.get("title", "?"))

    count = len(mentor_first_list)
    return {
        "total": total,
        "mentor_first_count": count,
        "mentor_first_ratio": round(count / total, 3),
        "mentor_first_list": mentor_first_list,
        "student_second_list": student_second_list,
    }


def judge_mentor_first(stat, mentor_is_senior=True, group_size=5):
    ratio = stat["mentor_first_ratio"]
    if ratio is None:
        return "无论文数据"
    if ratio >= 0.40:
        if mentor_is_senior and group_size >= 5:
            return "抢一作风险高（资深导师+组内人多仍高比例一作）"
        return "导师一作比例较高，需结合导师资历与组规模判断"
    if ratio >= 0.20:
        return "需结合具体情况（新导师早期自己写论文属正常）"
    return "健康：一作充分让渡给学生"


# ---------- 维度3：一作集中度 ----------
def first_author_concentration(papers, mentor_names):
    """统计学生一作分布：排除导师本人一作后，其余一作的集中度。"""
    counter = Counter()
    for p in papers:
        first = p.get("first_author")
        co_first = p.get("co_first") or []
        # 一作名单：一作 + 共一（都算作"一作产出"）
        names = []
        if first:
            names.append(first)
        for n in co_first:
            if n not in names:
                names.append(n)
        for n in names:
            if not is_mentor(n, mentor_names):
                counter[n] += 1

    total = sum(counter.values())
    if total == 0:
        return {
            "student_first_total": 0, "unique_first_authors": 0,
            "top1_name": None, "top1_count": 0, "top1_ratio": None,
            "top3_ratio": None, "hhi": None, "distribution": {},
        }

    dist = dict(counter.most_common())
    top1_name, top1_count = counter.most_common(1)[0]
    top1_ratio = top1_count / total
    top3_count = sum(c for _, c in counter.most_common(3))
    top3_ratio = top3_count / total
    hhi = sum((c / total) ** 2 for c in counter.values())

    return {
        "student_first_total": total,
        "unique_first_authors": len(counter),
        "top1_name": top1_name,
        "top1_count": top1_count,
        "top1_ratio": round(top1_ratio, 3),
        "top3_ratio": round(top3_ratio, 3),
        "hhi": round(hhi, 3),
        "distribution": dist,
    }


def judge_concentration(conc):
    if conc["top1_ratio"] is None:
        return "无学生一作数据"
    if conc["top1_ratio"] >= 0.50 or (conc["hhi"] and conc["hhi"] >= 0.40):
        return "一作高度集中：存在嫡系/关系户垄断一作嫌疑（也可能该生能力极强，需结合身份判断）"
    if conc["top1_ratio"] > 0.25:
        return "轻度集中：需结合最高产者身份（博士/博后 vs 硕士）判断"
    return "分布均匀，健康"


# ---------- 维度5：延毕率 ----------
def delay_stat(theses, ms_std=3, phd_std=5):
    """按学位层次计算延毕率。硕博连读/直博按各自标准判断。"""
    if not theses:
        return {
            "total": 0, "detail": [], "overall_delay_ratio": None,
            "ms": None, "phd": None, "average_duration": None,
        }

    detail = []
    for t in theses:
        degree = str(t.get("degree", "")).lower()
        enroll = t.get("enroll_year")
        grant = t.get("grant_year")
        if enroll is None or grant is None:
            duration = None
            delayed = None
        else:
            duration = grant - enroll
            if "硕博连读" in degree or "直博" in degree:
                std = max(ms_std + phd_std - 1, 6)  # 硕博连读约 5-6 年
                delayed = duration > std
            elif "博士" in degree:
                delayed = duration > phd_std
            else:  # 硕士
                delayed = duration > ms_std
        detail.append({
            "student": t.get("student", "?"),
            "degree": t.get("degree", "?"),
            "enroll_year": enroll,
            "grant_year": grant,
            "grant_month": t.get("grant_month"),
            "duration": duration,
            "delayed": delayed,
            "note": t.get("note", ""),
        })

    valid = [d for d in detail if d["duration"] is not None]
    total = len(valid)
    if total == 0:
        return {"total": 0, "detail": detail, "overall_delay_ratio": None,
                "ms": None, "phd": None, "average_duration": None}

    delay_n = sum(1 for d in valid if d["delayed"])
    durations = [d["duration"] for d in valid]

    ms_list = [d for d in valid if "硕士" in d["degree"] and "博" not in d["degree"]]
    phd_list = [d for d in valid if "博士" in d["degree"] or "直博" in d["degree"] or "硕博连读" in d["degree"]]

    def sub_stat(lst):
        if not lst:
            return None
        n = len(lst)
        nd = sum(1 for d in lst if d["delayed"])
        return {
            "count": n,
            "delay_count": nd,
            "delay_ratio": round(nd / n, 3),
            "avg_duration": round(sum(d["duration"] for d in lst) / n, 2),
        }

    return {
        "total": total,
        "detail": detail,
        "overall_delay_ratio": round(delay_n / total, 3),
        "average_duration": round(sum(durations) / total, 2),
        "ms": sub_stat(ms_list),
        "phd": sub_stat(phd_list),
    }


def judge_delay(ds):
    if ds is None or ds["overall_delay_ratio"] is None:
        return "样本不足/无数据，无法评估"
    ratio = ds["overall_delay_ratio"]
    if ds["total"] < 3:
        return f"样本仅 {ds['total']} 篇，延毕率仅供参考"
    if ratio >= 0.40:
        return "毕业保障差，强烈警示"
    if ratio >= 0.20:
        return "存在一定延毕风险"
    return "毕业保障良好"


# ---------- 主流程 ----------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _to_year(value):
    """把 year 字段转成 int；None/非数字/非法值返回 None。"""
    if value is None:
        return None
    try:
        y = int(value)
        return y if 1900 <= y <= 2100 else None
    except (TypeError, ValueError):
        return None


def filter_recent_papers(papers, years=5):
    """按年份过滤：保留最近 N 年发表的论文（含当年）。

    以数据中最新年份为基准向前推 N 年。years<=0 时不过滤。
    自动丢弃 year 缺失/非法的论文；字符串年份（如 "2023"）会转成 int。
    """
    if not papers:
        return []
    valid = []
    for p in papers:
        y = _to_year(p.get("year"))
        if y is not None:
            valid.append((y, p))
    if not valid:
        return []
    papers_sorted = [p for _, p in sorted(valid, key=lambda x: x[0])]
    recent_year = max(y for y, _ in valid)
    if years and years > 0:
        cutoff = recent_year - years + 1
        return [p for p in papers_sorted if _to_year(p.get("year")) >= cutoff]
    return papers_sorted


def main():
    ap = argparse.ArgumentParser(description="保研导师分析五维指标计算")
    ap.add_argument("papers_json", help="论文数据 JSON")
    ap.add_argument("theses_json", help="毕业论文数据 JSON")
    ap.add_argument("--mentor", required=True, help="导师姓名（别名用逗号分隔）")
    ap.add_argument("--ms-std", type=int, default=3, help="硕士标准学制（默认3）")
    ap.add_argument("--phd-std", type=int, default=5, help="博士标准学制（默认5）")
    ap.add_argument("--recent-years", type=int, default=5,
                    help="只统计最近 N 年发表的论文（按论文年份过滤，默认5）")
    ap.add_argument("--senior", action="store_true",
                    help="导师为资深教授（正高/组内学生>=5人），用于维度2抢一作判定校准")
    ap.add_argument("--group-size", type=int, default=5,
                    help="课题组在读学生人数估算（默认5），用于维度2抢一作判定校准")
    ap.add_argument("--output", default="metrics.json", help="输出 JSON 路径")
    ap.add_argument("--no-judge", action="store_true", help="只出统计量，不出判定标签")
    args = ap.parse_args()

    papers = load_json(args.papers_json).get("papers", [])
    theses = load_json(args.theses_json).get("theses", [])
    mentor_names = build_mentor_names(args.mentor)

    recent_papers = filter_recent_papers(papers, args.recent_years)

    zs = zone_stat(recent_papers)
    mf = mentor_first_stat(recent_papers, mentor_names)
    fc = first_author_concentration(recent_papers, mentor_names)
    dl = delay_stat(theses, args.ms_std, args.phd_std)

    metrics = {
        "mentor": args.mentor,
        "paper_total": len(recent_papers),
        "review_count": sum(1 for p in recent_papers if str(p.get("type", "")).lower() == "review"),
        "year_range": [min((p.get("year", 0) for p in recent_papers), default=0),
                       max((p.get("year", 0) for p in recent_papers), default=0)],
        "dim1_zone12": {
            "stat": zs,
            "judge": None if args.no_judge else judge_zone12(zs["zone12_ratio"]),
        },
        "dim2_mentor_first": {
            "stat": mf,
            "judge": None if args.no_judge else judge_mentor_first(mf, args.senior, args.group_size),
        },
        "dim3_concentration": {
            "stat": fc,
            "judge": None if args.no_judge else judge_concentration(fc),
        },
        "dim4_zone34": {
            "stat": zs,
            "judge": None if args.no_judge else judge_zone34(zs["zone34_ratio"], zs["zoned_total"]),
        },
        "dim5_delay": {
            "stat": dl,
            "judge": None if args.no_judge else judge_delay(dl),
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # 控制台摘要
    print("=" * 56)
    print(f"导师: {args.mentor} | 论文 {metrics['paper_total']} 篇 "
          f"({metrics['year_range'][0]}-{metrics['year_range'][1]}) | 毕业论文 {dl['total']} 篇")
    print("=" * 56)
    print(f"[1] 一二区占比: {zs['zone12_ratio']}  ({zs['zone12_count']}/{zs['zoned_total']})")
    print(f"    -> {metrics['dim1_zone12']['judge']}")
    print(f"[2] 导师一作占比: {mf['mentor_first_ratio']}  ({mf['mentor_first_count']}/{mf['total']})")
    print(f"    -> {metrics['dim2_mentor_first']['judge']}")
    if fc["top1_name"]:
        print(f"[3] 一作集中度: top1={fc['top1_name']}({fc['top1_count']}篇/{fc['top1_ratio']}) "
              f"top3={fc['top3_ratio']} HHI={fc['hhi']}")
    else:
        print(f"[3] 一作集中度: 无学生一作数据")
    print(f"    -> {metrics['dim3_concentration']['judge']}")
    print(f"[4] 三四区占比: {zs['zone34_ratio']}  ({zs['zone34_count']}/{zs['zoned_total']})")
    print(f"    -> {metrics['dim4_zone34']['judge']}")
    print(f"[5] 延毕率: {dl['overall_delay_ratio']}  (均值 {dl['average_duration']} 年)")
    if dl["ms"]:
        print(f"    硕士: 延毕 {dl['ms']['delay_ratio']} 平均 {dl['ms']['avg_duration']} 年 (n={dl['ms']['count']})")
    if dl["phd"]:
        print(f"    博士: 延毕 {dl['phd']['delay_ratio']} 平均 {dl['phd']['avg_duration']} 年 (n={dl['phd']['count']})")
    print(f"    -> {metrics['dim5_delay']['judge']}")
    print(f"\n完整 JSON 已写入: {args.output}")


if __name__ == "__main__":
    main()
