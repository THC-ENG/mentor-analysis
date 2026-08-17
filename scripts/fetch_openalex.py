#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_openalex.py — 从 OpenAlex 自动抓取导师近五年论文，生成 compute_metrics.py 可用的 papers.json

OpenAlex（https://openalex.org）是免费、无需 API key 的开放学术图谱。
本脚本自动完成：
    1. 按姓名 + 单位关键词定位作者（处理同名）
    2. 拉取该作者近 N 年论文
    3. 提取标题/年份/期刊/作者列表/通讯作者
    4. 输出 papers.json（供 compute_metrics.py 计算）

用法：
    python fetch_openalex.py "Wei Zhang" \
        --institution "Harbin Institute of Technology" \
        --years 5 \
        --output papers.json

参数说明：
    姓名            导师英文名（如 "Wei Zhang"）；中文名也可传，但 OpenAlex 中文覆盖有限
    --institution   单位关键词（过滤同名作者，可选但强烈建议）
    --years         抓取最近 N 年论文（默认 5）
    --output        输出 JSON 路径（默认 papers.json）
    --limit         每页条数（默认 100）
    --mailto        可选的邮箱（OpenAlex 建议附上，提高限流额度）

输出 papers.json 结构：
    {
      "papers": [
        {
          "title": "...",
          "year": 2023,
          "journal": "期刊名",
          "zone": null,               // 分区需人工补填（本脚本不查分区）
          "authors": ["A", "B"],      // 按署名顺序
          "first_author": "A",
          "corresponding": ["B"],     // 通讯作者（OpenAlex 标记）
          "type": "article"
        }
      ]
    }

说明：
    - OpenAlex 不提供期刊分区信息，zone 字段留空，需要按 data-sources.md 的方法
      人工补填后再运行 compute_metrics.py。
    - 中文期刊/中文论文 OpenAlex 覆盖不全，建议与导师主页、Google Scholar 交叉补充。
    - 本脚本依赖 urllib（标准库），无第三方依赖。
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

BASE = "https://api.openalex.org"


def http_get(url, mailto=None):
    """GET 请求，返回解析后的 JSON。带基础重试。"""
    if mailto:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}mailto={urllib.parse.quote(mailto)}"
    req = urllib.request.Request(url, headers={"User-Agent": "mentor-analysis/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


def search_author(name, institution):
    """按姓名搜作者，返回候选列表 [{id, display_name, institutions}]。"""
    query = urllib.parse.quote(name)
    url = f"{BASE}/authors?search={query}&per-page=25"
    data = http_get(url)
    results = data.get("results", [])
    # 用单位关键词过滤
    if institution:
        kw = institution.lower()
        filtered = []
        for r in results:
            insts = r.get("last_known_institutions") or []
            names = [ (i.get("display_name") or "") for i in insts ]
            if any(kw in n.lower() for n in names):
                filtered.append(r)
        if filtered:
            return filtered
        # 单位过滤为空时回退到全部候选（提示用户）
        return results
    return results


def fetch_works(author_id, years, per_page=100, mailto=None):
    """拉取作者论文列表。"""
    cursor = "*"
    works = []
    while cursor:
        url = (f"{BASE}/works?filter=author.id:{author_id}&sort=publication_date:desc"
               f"&per-page={per_page}&cursor={cursor}")
        data = http_get(url, mailto)
        batch = data.get("results", [])
        works.extend(batch)
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.2)  # 礼貌限流
    # 按年份过滤
    if years and years > 0:
        cutoff = date.today().year - years  # 以当前年份为基准
        works = [w for w in works if (w.get("publication_year") or 0) >= cutoff]
    return works


def works_to_papers(works):
    """把 OpenAlex works 转成 compute_metrics.py 的 papers 结构。"""
    papers = []
    for w in works:
        src = (w.get("primary_location") or {}).get("source") or {}
        journal = src.get("display_name") or ""
        authorships = w.get("authorships") or []
        authors = [a.get("author", {}).get("display_name", "") for a in authorships]
        authors = [a for a in authors if a]
        corresponding = [
            a.get("author", {}).get("display_name", "")
            for a in authorships if a.get("is_corresponding")
        ]
        wtype = w.get("type") or "article"
        papers.append({
            "title": w.get("title") or "(无标题)",
            "year": w.get("publication_year"),
            "journal": journal,
            "zone": None,  # OpenAlex 不提供分区，人工补填
            "authors": authors,
            "first_author": authors[0] if authors else None,
            "corresponding": corresponding,
            "type": wtype,
        })
    return papers


def main():
    ap = argparse.ArgumentParser(description="从 OpenAlex 抓取导师论文生成 papers.json")
    ap.add_argument("name", help="导师英文名，如 'Wei Zhang'")
    ap.add_argument("--institution", default="", help="单位关键词（过滤同名）")
    ap.add_argument("--years", type=int, default=5, help="最近 N 年（默认5）")
    ap.add_argument("--output", default="papers.json", help="输出路径")
    ap.add_argument("--limit", type=int, default=100, help="每页条数")
    ap.add_argument("--mailto", default="", help="邮箱（可选，提高限流额度）")
    args = ap.parse_args()

    print(f"[1/3] 搜索作者: {args.name} @ {args.institution or '(未指定单位)'}")
    candidates = search_author(args.name, args.institution)
    if not candidates:
        print("❌ 未找到匹配作者。尝试去掉 --institution 或改用其他英文名写法。")
        sys.exit(1)

    if len(candidates) > 1:
        print(f"⚠️  找到 {len(candidates)} 个候选作者，请核对：")
        for c in candidates:
            insts = [ (i.get("display_name") or "") for i in (c.get("last_known_institutions") or []) ]
            print(f"    - {c.get('display_name')} (ID={c.get('id')}) | {', '.join(insts)[:80]}")

    author = candidates[0]
    aid = author["id"].split("/")[-1]
    print(f"[2/3] 拉取论文: {author.get('display_name')} (ID={aid})")

    works = fetch_works(aid, args.years, args.limit, args.mailto)
    if not works:
        print("⚠️  未拉取到论文，可能是姓名/单位不匹配或该作者暂无收录。")
        sys.exit(1)

    papers = works_to_papers(works)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"papers": papers}, f, ensure_ascii=False, indent=2)

    print(f"[3/3] ✅ 已抓取 {len(papers)} 篇论文（最近 {args.years} 年）-> {args.output}")
    print("提示：zone 字段为 null，需按 data-sources.md 补填期刊分区后再运行 compute_metrics.py")


if __name__ == "__main__":
    main()
