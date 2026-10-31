"""Point-in-time fundamentals: a run dated D never receives a filing made after D, however
the model writes D. Disjoint from the hidden test: another filer, another statement (balance
sheet, instant facts), other dates, and a filing made on D itself."""
import sys; sys.path.insert(0, sys.argv[1])
import tempfile
from unittest import mock

from kit import Check, Violation, run_checks
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from tradingagents.agents import tools
from tradingagents.dataflows.vendors import sec_edgar

RUN = "2025-03-07"
TICKERS = {"0": {"cik_str": 795266, "ticker": "KBH", "title": "KB Home"}}
FACTS = {"cik": 795266, "entityName": "KB Home", "facts": {"us-gaap": {"Assets": {"units": {"USD": [
    {"end": "2024-11-30", "val": 6_941_000_000, "filed": "2025-01-21", "form": "10-K", "fy": 2024, "fp": "FY"},
    {"end": "2024-11-30", "val": 6_953_000_000, "filed": "2025-03-05", "form": "10-K/A", "fy": 2024, "fp": "FY"},
    {"end": "2024-11-30", "val": 6_977_000_000, "filed": "2025-03-07", "form": "10-K/A", "fy": 2024, "fp": "FY"},
    {"end": "2024-11-30", "val": 6_989_000_000, "filed": "2025-03-28", "form": "10-K/A", "fy": 2024, "fp": "FY"},
]}}}}}


class _State(MessagesState):
    trade_date: str
    company_of_interest: str


def balance_sheet(curr_date: str) -> str:
    graph = StateGraph(_State)
    graph.add_node("tools", ToolNode([tools.get_balance_sheet]))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)

    def vendor(method, ticker, freq, as_of_date):
        return sec_edgar.get_balance_sheet(ticker, freq, as_of_date)

    cache = tempfile.mkdtemp(prefix="fsc-verify-")
    with mock.patch.object(sec_edgar, "get_config", lambda: {"data_cache_dir": cache}), \
            mock.patch.object(sec_edgar, "_fetch_json", lambda url: TICKERS if "company_tickers" in url else FACTS), \
            mock.patch.object(tools, "route_to_vendor", side_effect=vendor):
        out = graph.compile().invoke({
            "messages": [AIMessage("", tool_calls=[{"name": "get_balance_sheet",
                                                    "args": {"freq": "annual", "curr_date": curr_date},
                                                    "id": "1"}])],
            "trade_date": RUN, "company_of_interest": "KBH"})
    return out["messages"][-1].content


def _evidence(out: str) -> str:
    """The rows that decide the check (cutoff header, Total Assets), not the tail of the table."""
    rows = [ln.strip() for ln in out.splitlines() if "filed on or before" in ln or ln.startswith("Total Assets")]
    return " | ".join(rows) if rows else out[-160:]


def latest_on_file(curr_date: str):
    out = balance_sheet(curr_date)
    if "6989" in out:
        raise Violation(f"curr_date={curr_date!r}: the amendment filed 2025-03-28 was served: {_evidence(out)}")
    if "6977" not in out:
        raise Violation(f"curr_date={curr_date!r}: expected the amendment filed on the run date (6977), got: "
                        f"{_evidence(out)}")


run_checks([
    Check("D-PIT-SEC-1", "an unpadded date does not reach filings made after the run date",
          "run 2025-03-07; model passes curr_date '2025-3-7'; amendments filed 03-05, 03-07, 03-28",
          "Total Assets 6977 (filed 03-07), never 6989 (filed 03-28)", lambda: latest_on_file("2025-3-7")),
    Check("D-PIT-SEC-2", "same with only the day unpadded", "as D-PIT-SEC-1, curr_date '2025-03-7'",
          "Total Assets 6977, never 6989", lambda: latest_on_file("2025-03-7")),
    Check("D-PIT-SEC-3", "boundary: a filing made on the run date itself is served",
          "as D-PIT-SEC-1, curr_date '2025-03-07' (padded)", "Total Assets 6977",
          lambda: latest_on_file("2025-03-07")),
])
