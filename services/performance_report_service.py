from datetime import datetime

def slugify(text):
    """Generates URL-safe IDs for HTML anchors and TOC linking."""
    if not text: return ""
    text = str(text).lower()
    text = re.sub(r'[^\w\s\-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return re.sub(r'-+', '-', text).strip('-')

def build_chart_data(years, cash_data, portfolio_data, broker_cash_data=None, daily_cash_series=None, daily_broker_cash_series=None):
    raw_chart = {
        "cash": {},
        "cash_cross_year": {
            "weekly": {"dates": [], "values": [], "pcts": []},
            "monthly": {"dates": [], "values": [], "pcts": []},
            "yearly": {"dates": [], "values": [], "pcts": []},
        },
        "portfolio": {},
        "broker_cash": {}
    }
    
    def r2(val):
        if val is None:
            return None
        try:
            return round(float(val), 2)
        except:
            return val

    def build_sub_series(series_entries):
        if not series_entries:
            return {"daily_cumulative": {"dates": [], "values": []}, "weekly_cumulative": {"dates": [], "values": []}}
        
        # 1. Daily
        daily_dates = []
        daily_vals = []
        for r in series_entries:
            try:
                dt_obj = datetime.strptime(r["date"], "%Y-%m-%d")
                daily_dates.append(dt_obj.strftime("%d %b"))
            except:
                daily_dates.append(r["date"])
            daily_vals.append(r2(r["gains"]))

        # 2. Weekly (group by isocalendar week and pick the last available record per week)
        weeks = {}
        for r in series_entries:
            try:
                dt_obj = datetime.strptime(r["date"], "%Y-%m-%d")
                iso_yr, iso_wk, _ = dt_obj.isocalendar()
                weeks[(iso_yr, iso_wk)] = r
            except:
                pass
        
        weekly_records = sorted(weeks.values(), key=lambda x: x["date"])
        weekly_dates = []
        weekly_vals = []
        for r in weekly_records:
            try:
                dt_obj = datetime.strptime(r["date"], "%Y-%m-%d")
                weekly_dates.append(dt_obj.strftime("%d %b"))
            except:
                weekly_dates.append(r["date"])
            weekly_vals.append(r2(r["gains"]))

        return {
            "daily_cumulative": {"dates": daily_dates, "values": daily_vals},
            "weekly_cumulative": {"dates": weekly_dates, "values": weekly_vals}
        }
            
    # 1. Cash chart data
    for y in years:
        y_data = cash_data.get(y, {})
        d_series = (daily_cash_series or {}).get(y, [])
        sub_chart = build_sub_series(d_series)

        raw_chart["cash"][y] = {
            "cumulative": [r2(y_data.get(m, {}).get("base_capital_gains")) for m in range(1, 13)],
            "daily_cumulative": sub_chart["daily_cumulative"],
            "weekly_cumulative": sub_chart["weekly_cumulative"],
            "mtd_val": [r2(y_data.get(m, {}).get("mtd", {}).get("base_capital_gains_val")) for m in range(1, 13)],
            "mtd_pct": [r2(y_data.get(m, {}).get("mtd", {}).get("base_capital_gains_pct")) for m in range(1, 13)],
            "mtm_val": [r2(y_data.get(m, {}).get("mtm", {}).get("base_capital_gains_val")) for m in range(1, 13)],
            "mtm_pct": [r2(y_data.get(m, {}).get("mtm", {}).get("base_capital_gains_pct")) for m in range(1, 13)]
        }
        
    # 2. Portfolio chart data
    for cls, cls_data in portfolio_data.items():
        raw_chart["portfolio"][cls] = {}
        for y in years:
            y_data = cls_data.get(y, {})
            raw_chart["portfolio"][cls][y] = {
                "cumulative": [r2(y_data.get(m, {}).get("total_returns")) for m in range(1, 13)],
                "mtd_val": [r2(y_data.get(m, {}).get("mtd", {}).get("total_returns_val")) for m in range(1, 13)],
                "mtd_pct": [r2(y_data.get(m, {}).get("mtd", {}).get("total_returns_pct")) for m in range(1, 13)],
                "mtm_val": [r2(y_data.get(m, {}).get("mtm", {}).get("base_capital_gains_val")) for m in range(1, 13)],
                "mtm_pct": [r2(y_data.get(m, {}).get("mtm", {}).get("base_capital_gains_pct")) for m in range(1, 13)]
            }
            
    # 3. Broker cash chart data
    if broker_cash_data:
        for br, br_data in broker_cash_data.items():
            raw_chart["broker_cash"][br] = {}
            for y in years:
                y_data = br_data.get(y, {})
                d_series = (daily_broker_cash_series or {}).get(br, {}).get(y, [])
                sub_chart = build_sub_series(d_series)

                raw_chart["broker_cash"][br][y] = {
                    "cumulative": [r2(y_data.get(m, {}).get("base_capital_gains")) for m in range(1, 13)],
                    "daily_cumulative": sub_chart["daily_cumulative"],
                    "weekly_cumulative": sub_chart["weekly_cumulative"],
                    "mtd_val": [r2(y_data.get(m, {}).get("mtd", {}).get("base_capital_gains_val")) for m in range(1, 13)],
                    "mtd_pct": [r2(y_data.get(m, {}).get("mtd", {}).get("base_capital_gains_pct")) for m in range(1, 13)],
                    "mtm_val": [r2(y_data.get(m, {}).get("mtm", {}).get("base_capital_gains_val")) for m in range(1, 13)],
                    "mtm_pct": [r2(y_data.get(m, {}).get("mtm", {}).get("base_capital_gains_pct")) for m in range(1, 13)]
                }

    # 4. Cross-year Combined Net Worth Cumulative Base Capital Gains (weekly, monthly, yearly)
    sorted_years = sorted(years)
    all_daily = []
    for y in sorted_years:
        all_daily.extend((daily_cash_series or {}).get(y, []))
    all_daily.sort(key=lambda x: x["date"])

    # Weekly cross-year (last available snapshot per ISO week)
    cross_weeks = {}
    for r in all_daily:
        try:
            dt_obj = datetime.strptime(r["date"], "%Y-%m-%d")
            iso_yr, iso_wk, _ = dt_obj.isocalendar()
            cross_weeks[(iso_yr, iso_wk)] = r
        except Exception:
            pass
    for r in sorted(cross_weeks.values(), key=lambda x: x["date"]):
        try:
            label = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b '%y")
        except Exception:
            label = r["date"]
        raw_chart["cash_cross_year"]["weekly"]["dates"].append(label)
        raw_chart["cash_cross_year"]["weekly"]["values"].append(r2(r.get("gains")))
        raw_chart["cash_cross_year"]["weekly"]["pcts"].append(r2(r.get("gains_pct")))

    # Monthly & Yearly cross-year
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for y in sorted_years:
        y_data = cash_data.get(y, {})
        last_month_entry = None
        for m in range(1, 13):
            m_entry = y_data.get(m)
            if not m_entry or m_entry.get("base_capital_gains") is None:
                continue
            gains = m_entry.get("base_capital_gains") or 0.0
            cap = m_entry.get("base_capital") or 0.0
            pct = (gains / cap * 100) if cap > 0 else 0.0
            raw_chart["cash_cross_year"]["monthly"]["dates"].append(f"{month_names[m - 1]} '{str(y)[-2:]}")
            raw_chart["cash_cross_year"]["monthly"]["values"].append(r2(gains))
            raw_chart["cash_cross_year"]["monthly"]["pcts"].append(r2(pct))
            last_month_entry = (gains, pct)
        if last_month_entry is not None:
            raw_chart["cash_cross_year"]["yearly"]["dates"].append(str(y))
            raw_chart["cash_cross_year"]["yearly"]["values"].append(r2(last_month_entry[0]))
            raw_chart["cash_cross_year"]["yearly"]["pcts"].append(r2(last_month_entry[1]))

    return raw_chart


