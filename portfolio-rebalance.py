#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Portfolio Rebalancer
# -----------------------------------------------------------------------------
# Author:  Ana Andújar
# Contact: ana.andcal@gmail.com
# Web:     https://dietaridigital.substack.com/
# Social:  https://www.linkedin.com/in/andujara/
# Loc:     Barcelona
# -----------------------------------------------------------------------------
# Description:
# A Python script to rebalance an investment portfolio efficiently.
# It supports different strategies (Standard vs Efficient to save fees) and
# tracks performance history (XIRR ready).
# -----------------------------------------------------------------------------
import argparse, csv, json, math, sys, shutil
from pathlib import Path
from datetime import date
from pyxirr import xirr

# -------- CLI --------
def parse_args():
    ap = argparse.ArgumentParser(description="Portfolio rebalancer")
    ap.add_argument("--config", default="config.json", help="YAML or JSON config")
    ap.add_argument("--holdings", default="holdings.csv", help="Holdings CSV")
    ap.add_argument("--cash", type=float, required=True, help="Cash to add (negative to withdraw)")
    ap.add_argument("--risk", type=str, default=None, help="Risk profile key (e.g., 5 or 7)")
    ap.add_argument("--mode", choices=["plan","commit", "perf"], default="plan", help="plan, commit or view performance")
    ap.add_argument("--strategy", choices=["standard", "efficient"], default="efficient", 
                    help="standard: fill all gaps; efficient: concentrates trades")
    
    ap.add_argument("--min-fee", type=float, default=None, help="Override min fee")
    ap.add_argument("--max-fee", type=float, default=None, help="Override max fee")
    
    ap.add_argument("--perf", default="perf.json", help="Performance state file")
    ap.add_argument("--history", default="history.csv", help="Historical data for XIRR")
    return ap.parse_args()

# -------- IO --------
def load_config(path, risk_key):
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml
        cfg = yaml.safe_load(text)
    except Exception:
        cfg = json.loads(text)

    cfg.setdefault("base_currency", "EUR")
    cfg.setdefault("fractional", False)
    
    if "fees" not in cfg:
        cfg["fees"] = {"fixed": 0.0, "bps": 12.0, "min": 0.0, "max": 0.0}
    else:
        cfg["fees"].setdefault("fixed", 0.0)
        cfg["fees"].setdefault("bps", 12.0)
        cfg["fees"].setdefault("min", 0.0) 
        cfg["fees"].setdefault("max", 0.0)
    
    if risk_key is None:
        risk_key = list(cfg["risk_profiles"].keys())[0]
        print(f"No risk profile specified. Using default: '{risk_key}'")
    
    if risk_key not in cfg["risk_profiles"]:
        sys.stderr.write(f"Error: Risk profile '{risk_key}' not found.\n")
        sys.exit(1)

    return cfg, cfg["risk_profiles"][risk_key]

def load_holdings(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["qty"] = float(r["qty"])
            r["price"] = float(r["price"])
            rows.append(r)
    return rows

def show_performance(history_path, current_holdings):
    if xirr is None:
        print("❌ Error: Necessites instal·lar 'pyxirr'. Executa: pip install pyxirr")
        return

    # 1. Valor actual (Això és un ingrés potencial, per tant POSITIU)
    current_value = sum(r["qty"] * r["price"] for r in current_holdings)
    
    dates = []
    amounts = []
    
    # Per calcular el ROI simple en cas que no hi hagi prou temps
    total_invested = 0.0

    try:
        with open(history_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = date.fromisoformat(row["date"]) # Convertim a objecte data real
                dates.append(d)
                
                raw_cash = float(row["cash_flow"])
                # Invertim signe pel càlcul de XIRR
                amounts.append(raw_cash * -1)
                
                # Sumem el total invertit (només les entrades de diners)
                if raw_cash > 0:
                    total_invested += raw_cash
                
    except FileNotFoundError:
        print("❌ No history file found yet.")
        return

    # 2. Afegim el valor actual a data d'avui
    today = date.today()
    dates.append(today)
    amounts.append(current_value)

    print(f"\n📈 PERFORMANCE METRICS")
    print("-" * 30)
    print(f"Current Value : {current_value:,.2f} €")
    print(f"Total Invested: {total_invested:,.2f} €")
    
    profit = current_value - total_invested
    sign = "+" if profit >= 0 else ""
    print(f"Total P&L     : {sign}{profit:,.2f} €")

    # 3. LÒGICA ANTIPROBLEMES (INF)
    # Si la primera inversió va ser avui (o no ha passat ni un dia), el XIRR peta.
    # En aquest cas mostrem el ROI simple.
    days_diff = (today - min(dates)).days

    if days_diff < 1:
        # Càlcul de rendibilitat simple (ROI)
        roi = (profit / total_invested * 100) if total_invested > 0 else 0.0
        print(f"Return (ROI)  : {roi:.2f}% (Portfolio is too new for XIRR)")
    else:
        # Càlcul de XIRR (Anualitzat)
        try:
            res = xirr(dates, amounts)
            if res is not None:
                # A vegades el XIRR pot ser extrem si el període és molt curt (ex: 2 dies)
                # Si és gegant, mostrem també el ROI per context
                print(f"XIRR (Annual) : {res * 100:.2f}%")
            else:
                print("XIRR (Annual) : N/A (Calculation failed)")
        except Exception as e:
            print(f"XIRR Error    : {e}")
            
    print("-" * 30)

def write_holdings(path, rows):
    fieldnames = ["isin", "name", "qty", "price", "currency"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def load_perf(path):
    if not Path(path).exists(): return {}
    try: return json.loads(Path(path).read_text())
    except: return {}

def save_perf(path, baseline_val):
    data = {"date": str(date.today()), "baseline_value": baseline_val}
    Path(path).write_text(json.dumps(data, indent=2))

# --- NOVA FUNCIÓ PER OPCIÓ B (HISTÒRIC) ---
def update_history_csv(path, cash_flow, total_value):
    file_path = Path(path)
    file_exists = file_path.exists()
    
    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Si el fitxer és nou, posem capçaleres
        if not file_exists:
            writer.writerow(["date", "cash_flow", "total_value"])
        
        # Escrivim l'operació d'avui
        # cash_flow: Diners que entren (+) o surten (-)
        # total_value: Valor de la cartera just DESPRÉS de l'operació
        writer.writerow([str(date.today()), f"{cash_flow:.2f}", f"{total_value:.2f}"])
    return file_path

def snapshot_holdings_with_date(src, dest_dir):
    dest_dir.mkdir(exist_ok=True)
    today_str = str(date.today())
    filename = f"holdings-post-{today_str}.csv"
    dest_path = dest_dir / filename
    rows = load_holdings(src)
    fieldnames = ["date", "isin", "name", "qty", "price", "currency"]
    with open(dest_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            r["date"] = today_str
            writer.writerow(r)
    return dest_path

# -------- LOGICA DE COMISSIONS --------

def calc_fee_advanced(amount, cfg_fees, ovr_min=None, ovr_max=None):
    if amount <= 0: return 0.0
    bps = cfg_fees.get("bps", 0.0)
    fixed = cfg_fees.get("fixed", 0.0)
    min_fee = cfg_fees.get("min", 0.0)
    if ovr_min is not None: min_fee = ovr_min
    max_fee = cfg_fees.get("max", 0.0)
    if ovr_max is not None: max_fee = ovr_max
    
    base_fee = fixed + (amount * (bps / 10000.0))
    final_fee = max(base_fee, min_fee)
    if max_fee > 0:
        final_fee = min(final_fee, max_fee)
    return final_fee

def plan(cfg, target_weights, holdings, cash_in, strategy="efficient", ovr_min=None, ovr_max=None):
    h_map = {row["isin"]: row for row in holdings}
    for tw in target_weights:
        isin = tw["isin"]
        if isin not in h_map:
            h_map[isin] = {"isin": isin, "name": tw["name"], "qty": 0.0, "price": 0.0, "currency": cfg["base_currency"]}

    current_value = sum(r["qty"] * r["price"] for r in h_map.values())
    projected_total = current_value + cash_in
    
    eff_min = cfg["fees"].get("min", 0.0)
    if ovr_min is not None: eff_min = ovr_min

    print(f"Current Value : {current_value:,.2f} €")
    print(f"Cash Input    : {cash_in:,.2f} €")
    print(f"Projected     : {projected_total:,.2f} €")
    print(f"Strategy      : {strategy.upper()}")
    
    bps_disp = cfg['fees']['bps']
    min_disp = eff_min
    max_disp = cfg['fees'].get('max', 0.0)
    if ovr_max is not None: max_disp = ovr_max
    max_str = f"| Max: {max_disp} €" if max_disp > 0 else ""
    print(f"Fees Config   : {bps_disp} bps | Min: {min_disp} € {max_str}")
    print("-" * 75)
    print(f"{'NAME':<20} | {'TGT %':<6} | {'ACT %':<6} | {'DEFICIT (€)':<12} | {'POST %':<6} | {'ACTION'}")
    print("-" * 75)

    deficits = []
    for tw in target_weights:
        isin = tw["isin"]
        h = h_map[isin]
        current_val = h["qty"] * h["price"]
        target_val = projected_total * tw["target_weight"]
        diff = target_val - current_val
        actual_pct = (current_val / current_value) if current_value > 0 else 0
        deficits.append({
            "isin": isin, "name": tw["name"], "price": h["price"],
            "qty": h["qty"],
            "diff": diff, "target_w": tw["target_weight"], "actual_pct": actual_pct
        })
    deficits.sort(key=lambda x: x["diff"], reverse=True)

    planned_trades = []
    remaining_cash = cash_in
    use_concentration = (strategy == "efficient" and eff_min > 0.05) 

    if use_concentration:
        MAX_TRADES = 4 
        candidates = [d for d in deficits if d["diff"] > 0]
        top_picks = candidates[:MAX_TRADES]
        sum_deficit_top = sum(d["diff"] for d in top_picks)
        
        if sum_deficit_top > 0:
            for d in top_picks:
                buy_units = 0
                cost = 0
                if remaining_cash >= 10:
                    weight_in_deficit = d["diff"] / sum_deficit_top
                    amount_to_spend = cash_in * weight_in_deficit
                    if amount_to_spend > remaining_cash: amount_to_spend = remaining_cash
                    
                    if d["price"] > 0:
                        if cfg["fractional"]: buy_units = amount_to_spend / d["price"]
                        else: buy_units = math.floor(amount_to_spend / d["price"])
                        cost = buy_units * d["price"]
                        
                        if cost > eff_min: 
                            planned_trades.append({
                                "isin": d["isin"], "name": d["name"],
                                "units": buy_units, "price": d["price"], "cost": cost
                            })
                            remaining_cash -= cost
                
                post_val = (d["qty"] + buy_units) * d["price"]
                post_pct = post_val / projected_total if projected_total > 0 else 0.0
                action_str = f"BUY {buy_units} ({cost:.1f}€) [Conc.]" if buy_units > 0 else "SKIP (Low funds)"
                print(f"{d['name']:<20} | {d['target_w']*100:4.1f}% | {d['actual_pct']*100:4.1f}% | {d['diff']:10.2f}   | {post_pct*100:4.1f}% | {action_str}")
        
        for s in candidates[MAX_TRADES:]:
             post_val = s["qty"] * s["price"]
             post_pct = post_val / projected_total if projected_total > 0 else 0.0
             print(f"{s['name']:<20} | {s['target_w']*100:4.1f}% | {s['actual_pct']*100:4.1f}% | {s['diff']:10.2f}   | {post_pct*100:4.1f}% | SKIP (Saving fees)")

    else:
        for d in deficits:
            buy_units = 0
            cost = 0
            action_str = "Hold"
            if d["diff"] > 0 and remaining_cash > 0:
                amount = min(d["diff"], remaining_cash)
                if d["price"] > 0:
                    if cfg["fractional"]: buy_units = amount / d["price"]
                    else: buy_units = math.floor(amount / d["price"])
                    cost = buy_units * d["price"]
                    if cost > 0:
                        planned_trades.append({
                            "isin": d["isin"], "name": d["name"], 
                            "units": buy_units, "price": d["price"], "cost": cost
                        })
                        remaining_cash -= cost
                        action_str = f"BUY {buy_units} ({cost:.1f}€)"
            
            post_val = (d["qty"] + buy_units) * d["price"]
            post_pct = post_val / projected_total if projected_total > 0 else 0.0
            print(f"{d['name']:<20} | {d['target_w']*100:4.1f}% | {d['actual_pct']*100:4.1f}% | {d['diff']:10.2f}   | {post_pct*100:4.1f}% | {action_str}")

    total_fees = 0.0
    print("\n--- ORDER SUMMARY & FEES ---")
    for t in planned_trades:
        fee = calc_fee_advanced(t["cost"], cfg["fees"], ovr_min, ovr_max)
        total_fees += fee
        print(f"Order: {t['name']:<20} | Units: {t['units']:>4} | Val: {t['cost']:>8.2f}€ | Fee: {fee:>5.2f}€")

    summary = {
        "post_value": current_value + (cash_in - remaining_cash),
        "fees_total": total_fees,
        "cash_leftover": remaining_cash
    }
    return planned_trades, summary

def apply_trades_to_holdings(holdings, trades):
    h_map = {r["isin"]: r for r in holdings}
    for t in trades:
        if t["isin"] in h_map:
            h_map[t["isin"]]["qty"] += t["units"]
    return list(h_map.values())

# -------- MAIN --------
def main():  
    args = parse_args()
    cfg, target_weights = load_config(args.config, args.risk)
    holdings = load_holdings(args.holdings)

    if args.mode == "perf":
        show_performance(args.history, holdings)
        return  # Sortim immediatament
    
    planned_trades, summary = plan(cfg, target_weights, holdings, args.cash, 
                                   strategy=args.strategy, 
                                   ovr_min=args.min_fee, ovr_max=args.max_fee)
    
    print("-" * 40)
    print(f"Total Fees to Pay: {summary['fees_total']:.2f} €")
    print(f"Uninvested Cash:   {summary['cash_leftover']:.2f} €")
    print("-" * 40)

    if args.mode == "commit":
        # 1. Actualitzar Holdings
        updated_rows = apply_trades_to_holdings(holdings, planned_trades)
        write_holdings(args.holdings, updated_rows)
        
        current_post_trade_val = sum(r["qty"] * r["price"] for r in updated_rows)
        
        # 2. Guardar Snapshot
        snap = snapshot_holdings_with_date(args.holdings, Path("snapshots"))
        
        # 3. Guardar Perf (Baseline simple)
        save_perf(args.perf, current_post_trade_val)

        # 4. Actualitzar Històric
        hist_file = update_history_csv(args.history, args.cash, current_post_trade_val)

        print(f"\n[OK] Holdings updated: {args.holdings}")
        print(f"[OK] New baseline value: {current_post_trade_val:.2f} €")
        print(f"[OK] Snapshot saved: {snap}")
        print(f"[OK] History appended: {hist_file} (Date, Cash Flow, Total Val)")
    else:
        print("\nMode is PLAN. No files updated.")
        print("Run with --mode commit to finalize and save to history.")

if __name__ == "__main__":
    main()