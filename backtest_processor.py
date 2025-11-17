import json
import csv
import io
from helpers import _to_float, load_backtest_memory, save_backtest_memory

def process_backtest_data(raw_data, content_type, ticker_hint=""):
    """Process backtest data from CSV or JSON."""
    rows = []

    if "application/json" in content_type:
        try:
            payload = json.loads(raw_data.decode("utf-8"))
            if isinstance(payload, dict) and "trades" in payload:
                rows = payload["trades"]
            elif isinstance(payload, list):
                rows = payload
            else:
                return None, "invalid_json_structure"
        except Exception as e:
            print("❌ JSON error:", e)
            return None, "bad_json"
    else:
        # CSV processing
        try:
            text = raw_data.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = [r for r in reader]
        except Exception as e:
            print("❌ CSV error:", e)
            return None, "bad_csv"

    if not rows:
        return None, "no_rows"

    return process_trades(rows, ticker_hint)

def process_trades(rows, ticker_hint):
    """Process and aggregate trade data."""
    summary = {}

    for r in rows:
        row_ticker = (r.get("ticker") or r.get("Ticker") or ticker_hint or "UNKNOWN").upper()
        pattern = (r.get("pattern") or r.get("Pattern") or r.get("Signal") or "").strip() or "unknown"
        key = f"{row_ticker}:{pattern}"

        if key not in summary:
            summary[key] = {
                "ticker": row_ticker,
                "pattern": pattern,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "rr_values": []
            }

        rec = summary[key]
        rec["total_trades"] += 1

        # Determine win/loss
        pl = None
        if r.get("Net P&L USD") not in (None, ""):
            pl = _to_float(r.get("Net P&L USD"))
        elif r.get("Net P&L %") not in (None, ""):
            pl = _to_float(r.get("Net P&L %"))

        if pl is not None:
            if pl > 0:
                rec["wins"] += 1
            elif pl < 0:
                rec["losses"] += 1

        # Compute R:R
        runup = _to_float(r.get("Run-up %") or r.get("Run up %") or r.get("Run-up%"))
        drawdown_raw = _to_float(r.get("Drawdown %") or r.get("Drawdown%"))

        if runup is not None and drawdown_raw not in (None, 0) and runup > 0:
            rr = runup / abs(drawdown_raw)
            if 0 < rr < 20:
                rec["rr_values"].append(rr)

    return finalize_summary(summary)

def finalize_summary(summary):
    """Finalize summary statistics and save to memory."""
    memory = load_backtest_memory()
    out = []

    for key, rec in summary.items():
        total = rec["total_trades"]
        wins = rec["wins"]
        losses = rec["losses"]

        winrate = round((wins / total) * 100, 2) if total > 0 else 0
        avg_rr = round(sum(rec["rr_values"]) / len(rec["rr_values"]), 2) if rec["rr_values"] else None

        result = {
            "ticker": rec["ticker"],
            "pattern": rec["pattern"],
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "winrate_pct": winrate,
            "avg_rr": avg_rr
        }

        out.append(result)
        memory[key] = result

    save_backtest_memory(memory)
    print("📊 Backtest summary:", out)
    return out
