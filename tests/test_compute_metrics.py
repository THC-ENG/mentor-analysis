#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_metrics.py 的单元测试。

运行方式：
    python -m pytest tests/ -v
    # 或（无 pytest 时）
    python -m unittest discover -s tests

覆盖范围：
    1. 分区解析（中科院/JCR/非法值）
    2. 导师别名匹配
    3. 一二区占比（维度1）
    4. 导师一作占比与共一作（维度2）
    5. 一作集中度 top1/top3/HHI（维度3）
    6. 三四区占比判定（维度4）
    7. 延毕率分学位统计（维度5）
    8. 年份过滤（--recent-years 逻辑）
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from compute_metrics import (
    ZONE_MAP,
    parse_zone,
    build_mentor_names,
    is_mentor,
    zone_stat,
    judge_zone12,
    judge_zone34,
    mentor_first_stat,
    judge_mentor_first,
    first_author_concentration,
    judge_concentration,
    delay_stat,
    judge_delay,
    filter_recent_papers,
)

def mk_paper(title="t", year=2023, journal="J", zone="一区",
             authors=None, first=None, co_first=None, corresponding=None, wtype="article"):
    """构造一条论文记录。"""
    return {
        "title": title, "year": year, "journal": journal, "zone": zone,
        "authors": authors or ["Zhang Wei", "Li Ming"],
        "first_author": first or (authors[0] if authors else None),
        "co_first": co_first, "corresponding": corresponding, "type": wtype,
    }


class TestZoneParsing(unittest.TestCase):
    def test_chinese_zones(self):
        self.assertEqual(parse_zone("一区"), 1)
        self.assertEqual(parse_zone("二区"), 2)
        self.assertEqual(parse_zone("三区"), 3)
        self.assertEqual(parse_zone("四区"), 4)

    def test_jcr_zones(self):
        self.assertEqual(parse_zone("Q1"), 1)
        self.assertEqual(parse_zone("q2"), 2)
        self.assertEqual(parse_zone("Q3"), 3)
        self.assertEqual(parse_zone("Q4"), 4)

    def test_numeric_and_invalid(self):
        self.assertEqual(parse_zone("1"), 1)
        self.assertIsNone(parse_zone("中文核心"))
        self.assertIsNone(parse_zone(None))
        self.assertIsNone(parse_zone(""))


class TestMentorNames(unittest.TestCase):
    def test_aliases(self):
        names = build_mentor_names("张三,Wei Zhang")
        self.assertTrue(is_mentor("张三", names))
        self.assertTrue(is_mentor("wei zhang", names))  # 大小写不敏感
        self.assertTrue(is_mentor("Wei Zhang", names))
        self.assertFalse(is_mentor("李四", names))
        self.assertFalse(is_mentor("", names))
        self.assertFalse(is_mentor(None, names))


class TestZone12(unittest.TestCase):
    def test_ratio(self):
        papers = [
            mk_paper(zone="一区"), mk_paper(zone="二区"),
            mk_paper(zone="三区"), mk_paper(zone="四区"),
            mk_paper(zone="Q1"),
        ]
        zs = zone_stat(papers)
        self.assertEqual(zs["zoned_total"], 5)
        self.assertEqual(zs["zone12_count"], 3)
        self.assertAlmostEqual(zs["zone12_ratio"], 0.6)

    def test_null_zones_excluded(self):
        papers = [mk_paper(zone="一区"), mk_paper(zone=None), mk_paper(zone="中文核心")]
        zs = zone_stat(papers)
        self.assertEqual(zs["zoned_total"], 1)
        self.assertAlmostEqual(zs["zone12_ratio"], 1.0)

    def test_empty(self):
        zs = zone_stat([])
        self.assertIsNone(zs["zone12_ratio"])

    def test_judge_thresholds(self):
        self.assertIn("强", judge_zone12(0.6))
        self.assertIn("中等", judge_zone12(0.5))
        self.assertIn("一般", judge_zone12(0.3))
        self.assertIn("无分区", judge_zone12(None))


class TestMentorFirst(unittest.TestCase):
    def test_mentor_first_detected(self):
        papers = [
            mk_paper(first="Zhang Wei"),          # 导师一作
            mk_paper(first="Li Ming"),            # 学生一作
            mk_paper(first="Li Ming", co_first=["Zhang Wei"]),  # 共一含导师
        ]
        st = mentor_first_stat(papers, build_mentor_names("Zhang Wei"))
        self.assertEqual(st["mentor_first_count"], 2)
        self.assertAlmostEqual(st["mentor_first_ratio"], 2 / 3, places=3)

    def test_no_papers(self):
        st = mentor_first_stat([], build_mentor_names("Zhang Wei"))
        self.assertIsNone(st["mentor_first_ratio"])

    def test_judge_senior_flag(self):
        st = {"mentor_first_ratio": 0.45}
        # 资深导师 + 大组 → 高风险
        self.assertIn("风险高", judge_mentor_first(st, True, 8))
        # 新导师 → 缓和表述
        self.assertIn("结合", judge_mentor_first(st, False, 3))


class TestConcentration(unittest.TestCase):
    def test_uniform_vs_concentrated(self):
        uniform = [
            mk_paper(first="A"), mk_paper(first="B"), mk_paper(first="C"),
            mk_paper(first="D"), mk_paper(first="Zhang Wei"),  # 导师一作不算
        ]
        conc = first_author_concentration(uniform, build_mentor_names("Zhang Wei"))
        self.assertEqual(conc["student_first_total"], 4)
        self.assertAlmostEqual(conc["top1_ratio"], 0.25)
        self.assertIn("均匀", judge_concentration(conc))

        concentrated = [
            mk_paper(first="A"), mk_paper(first="A"), mk_paper(first="A"),
            mk_paper(first="A"), mk_paper(first="B"),
        ]
        conc2 = first_author_concentration(concentrated, build_mentor_names("Zhang Wei"))
        self.assertAlmostEqual(conc2["top1_ratio"], 0.8)
        self.assertAlmostEqual(conc2["hhi"], 0.8**2 + 0.2**2, places=3)
        self.assertIn("集中", judge_concentration(conc2))


class TestZone34(unittest.TestCase):
    def test_judge_three_bands(self):
        self.assertIn("压成果", judge_zone34(0.45, 20))
        self.assertIn("正常", judge_zone34(0.25, 20))
        # 低占比 + 低总量 → 严进严出
        self.assertIn("严进严出", judge_zone34(0.05, 8))
        # 低占比 + 高总量 → 只发好刊
        self.assertIn("好刊", judge_zone34(0.05, 50))


class TestDelay(unittest.TestCase):
    def test_ms_and_phd(self):
        theses = [
            {"student": "A", "degree": "硕士", "enroll_year": 2019, "grant_year": 2022},  # 3年 正常
            {"student": "B", "degree": "硕士", "enroll_year": 2019, "grant_year": 2023},  # 4年 延毕
            {"student": "C", "degree": "博士", "enroll_year": 2018, "grant_year": 2023},  # 5年 正常
            {"student": "D", "degree": "博士", "enroll_year": 2017, "grant_year": 2024},  # 7年 延毕
        ]
        ds = delay_stat(theses)
        self.assertEqual(ds["total"], 4)
        self.assertAlmostEqual(ds["overall_delay_ratio"], 0.5)
        self.assertEqual(ds["ms"]["delay_count"], 1)
        self.assertEqual(ds["phd"]["delay_count"], 1)
        self.assertAlmostEqual(ds["average_duration"], 4.75)

    def test_custom_std(self):
        theses = [
            {"student": "A", "degree": "硕士", "enroll_year": 2019, "grant_year": 2022},  # 3年
        ]
        # 2 年制专硕：3 年 → 延毕
        ds = delay_stat(theses, ms_std=2, phd_std=5)
        self.assertTrue(ds["detail"][0]["delayed"])

    def test_zhiliandu_calibration(self):
        # 硕博连读：6 年不判延毕（标准为 6 年）
        theses = [
            {"student": "A", "degree": "硕博连读", "enroll_year": 2017, "grant_year": 2023},
        ]
        ds = delay_stat(theses)
        self.assertFalse(ds["detail"][0]["delayed"])

    def test_missing_years(self):
        theses = [{"student": "A", "degree": "硕士", "enroll_year": None, "grant_year": 2022}]
        ds = delay_stat(theses)
        self.assertEqual(ds["total"], 0)
        self.assertIsNone(ds["overall_delay_ratio"])

    def test_judge_small_sample(self):
        self.assertIn("样本", judge_delay({"total": 2, "overall_delay_ratio": 0.5}))
        self.assertIn("良好", judge_delay({"total": 6, "overall_delay_ratio": 0.1}))


class TestRecentFilter(unittest.TestCase):
    def test_filter_recent_years(self):
        papers = [
            mk_paper(year=2024), mk_paper(year=2023), mk_paper(year=2022),
            mk_paper(year=2021), mk_paper(year=2020), mk_paper(year=2019),
        ]
        # 最近 5 年：2020-2024（含当年）
        recent = filter_recent_papers(papers, years=5)
        years = sorted(p.get("year") for p in recent)
        self.assertEqual(years, [2020, 2021, 2022, 2023, 2024])

        # years=0 → 不过滤
        all_p = filter_recent_papers(papers, years=0)
        self.assertEqual(len(all_p), 6)

    def test_empty(self):
        self.assertEqual(filter_recent_papers([], years=5), [])

    def test_invalid_years(self):
        """year 为 None / 字符串 / 非法值时不应崩溃（回归：原实现会 TypeError）。"""
        papers = [
            mk_paper(year=2024),
            mk_paper(year="2023"),          # 字符串年份
            mk_paper(year=None),            # None
            mk_paper(year="invalid"),       # 非法字符串
            {"title": "no-year", "journal": "J", "zone": "一区"},  # 缺字段
        ]
        recent = filter_recent_papers(papers, years=5)
        # None/非法被丢弃；字符串 "2023" 保留原样；int 2024 保留
        self.assertEqual(len(recent), 2)
        self.assertIn(2024, [p.get("year") for p in recent])
        self.assertIn("2023", [p.get("year") for p in recent])


if __name__ == "__main__":
    unittest.main()
