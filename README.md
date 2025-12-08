# Portfolio Rebalancer 📊

A clean, dependency-free Python script to rebalance investment portfolios. Designed for investors who want to minimize fees and track real performance (XIRR) without relying on complex spreadsheets or paid software.

**Author:** Ana Andújar  
**Contact:** [ana.andcal@gmail.com](mailto:ana.andcal@gmail.com)  
**Blog:** [Dietari Digital](https://dietaridigital.substack.com/)  
**LinkedIn:** [Andujara](https://www.linkedin.com/in/andujara/)  

---

## Features

* **Lean & Fast:** No heavy libraries like Pandas. Uses only Python standard libraries.
* **Dual Strategy:**
    * `Standard`: Classic rebalancing. Fills every gap to reach target %.
    * `Efficient`: Smart logic to avoid small trades if brokerage fees (min fee) make them inefficient.
* **Safety First:** Two distinct modes (`plan` vs `commit`) to prevent accidental trades.
* **Performance Tracking:** Automatically generates a history log (`history.csv`) compatible with XIRR (Internal Rate of Return) calculations.
* **Snapshots:** Creates backups of your holdings before every commit.

## Configuration

You need two files to run the script (JSON and CSV).

### 1. `config.json`
To start, rename config-template.json to config.json and add your own ISINs.
Define your risk profiles and fee structure.

```json
{
  "fees": {
    "bps": 12.0,      
    "min": 1.50,      
    "max": 0.0        
  },
  "risk_profiles": {
    "7": [
      { "isin": "IE00B4X9L533", "name": "MSCI World", "target_weight": 0.80 },
      { "isin": "IE00BKM4GZ66", "name": "Emerging Mkts", "target_weight": 0.10 },
      { "isin": "IE00B3F81R35", "name": "Corp Bond", "target_weight": 0.10 }
    ]
  }
}
```

### 2. holdings.csv
Rename holdings-template.cvs to holdings.csv and add your own data.
Your current portfolio status. Note: Update prices manually or via script before running.

isin,name,qty,price,currency
IE00B4X9L533,MSCI World,120.0,92.50,EUR
IE00BKM4GZ66,Emerging Mkts,45.0,28.10,EUR

## User Flow
### Step 1: PLAN (Dry Run)

Simulate the rebalance. This will not modify any files. It calculates the necessary trades to reach your target allocation based on the cash you inject.

python3 portfolio-rebalancer.py --cash 3000 --risk 7 --mode plan

Output:
    Deficits per asset.
    Proposed "BUY" orders.
    Estimated fees.
    Projected new weights (POST %).

### Step 2: EXECUTE (Commit)
Once you have physically executed the orders at your broker, run the script in commit mode to update your records.

python3 portfolio-rebalancer.py --cash 3000 --risk 7 --mode commit

Actions performed:
    Updates quantities in holdings.csv.
    Saves a backup in snapshots/.
    Appends the transaction to history.csv (Date, Cash Flow, Total Value).

#### Advanced Options
Fee Optimization: If you have a minimum fee (e.g., 2€) and want to avoid buying small amounts (e.g., 10€ stock purchase paying 2€ fee), use the efficient strategy:

--strategy efficient --min-fee 2.0

Withdrawals: Use negative cash numbers to plan a withdrawal
--cash -1000

## License
This project is open-source. Feel free to use and modify.