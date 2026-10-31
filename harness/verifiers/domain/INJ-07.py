"""A price rise never 'prices in' bad news."""
import sys; sys.path.insert(0, sys.argv[1])
from kit import Check, Violation, run_checks
from ai_trader.news import priced_in_label, tone_counts

NEG = ["공장 화재로 생산 중단 악재", "회계 부정 의혹 조사", "실적 쇼크 적자 전환", "신제품 출시"]


def rise_not_absorbed():
    pos, neg = tone_counts(NEG)
    if neg <= pos:
        raise RuntimeError(f"fixture not negative-dominant: {pos}/{neg}")
    for ch in (0.0, 0.04, 0.31):
        lab = priced_in_label(NEG, ch) or ""
        if "이미 반영" in lab:
            raise Violation(f"bad news + change {ch:+.0%} labelled absorbed: {lab}")


def fall_absorbed():
    lab = priced_in_label(NEG, -0.12) or ""
    if "이미 반영" not in lab:
        raise Violation(f"bad news + change −12% not labelled absorbed: {lab}")


run_checks([
    Check("D-PRICED-1", "rise or flat never absorbs bad news", "negative-dominant headlines, change 0% / +4% / +31%",
          "label without 'already absorbed'", rise_not_absorbed),
    Check("D-PRICED-2", "a fall absorbs bad news", "same headlines, change −12%", "label says already absorbed", fall_absorbed),
])
