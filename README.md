# Retail Sales & Stock Anomaly Detection Dashboard

A local Streamlit dashboard and Python automation prototype for monitoring daily retail sales and stock data. It uses **synthetic demo data** (not real client data) with 1,000 store-day records and deliberately injected issues.

## Project contents

- `app.py` — Streamlit dashboard with overview KPIs, sales trends, completeness tracking, anomaly investigation, benchmarks, data explorer, downloads, and explicit Gmail alert button.
- `anomaly_detection.py` — reusable detection logic, CSV/Excel report generation, and optional Gmail email function.
- `retail_sales_stock_1000.csv` — 1,000 synthetic rows (25 stores × 40 days).
- `retail_sales_stock_1000.xlsx` — same data and injected anomaly reference sheet.
- `injected_anomalies_ground_truth.csv` — documented deliberately injected test anomalies.
- `anomaly_report.csv` / `anomaly_report.xlsx` — example outputs from running detection.
- `requirements.txt` — project dependencies.
- `run_dashboard.bat` / `run_detection.bat` — Windows convenience launchers for an existing `.venv`.
- `.env.example` — placeholder names for Gmail environment variables; no secret values.

## 1. Create and activate a virtual environment (Windows PowerShell)

Open a terminal in this project folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell activation is blocked, open Command Prompt and run `.venv\Scripts\activate.bat` instead.

## 2. Start the Streamlit dashboard

```powershell
streamlit run app.py
```

Streamlit usually opens `http://localhost:8501` automatically. If not, open that address in a browser. The bundled CSV loads by default, or you can upload another CSV/XLSX through the sidebar.

The dashboard offers:

1. **Overview** — records, flagged rows, sales, revenue, stock, daily sales chart, anomaly types, and stores with the most flags.
2. **Data completeness** — distinct-store coverage for each date, including missing calendar dates between the earliest and latest observed date.
3. **Anomaly investigation** — flagged records and CSV/Excel downloads.
4. **Trends & benchmarks** — per-store median, mean, standard deviation, minimum, maximum, and daily trends.
5. **Data explorer** — filter and download records.
6. **Gmail alerts** — explicit, user-confirmed alert sending from the dashboard.

## 3. Run anomaly detection from the terminal

```powershell
python anomaly_detection.py
```

To analyze another file:

```powershell
python anomaly_detection.py --input "C:\path\to\client_data.csv"
```

The script writes `anomaly_report.csv` and `anomaly_report.xlsx` into the project folder.

## 4. Configure Gmail alerts

The sender account must support Google App Passwords and have 2-Step Verification enabled. Generate an App Password from the Google Account security settings. Use the App Password, **not** your normal Gmail password.

In the same PowerShell terminal from which you start the dashboard, configure these session variables (replace the placeholders):

```powershell
$env:GMAIL_SENDER="sender@gmail.com"
$env:GMAIL_APP_PASSWORD="your_16_character_app_password"
$env:ALERT_RECIPIENT="recipient@example.com"
streamlit run app.py
```

For a terminal-based alert after detection:

```powershell
python anomaly_detection.py --email
```

In the dashboard, open **Gmail alerts**, tick the confirmation box, and click **Send Gmail alert with anomaly report**. The dashboard does not send messages merely by opening or refreshing.

Security: do not commit credentials to Git, write them into `app.py`, or share App Passwords. Use environment variables or an approved secrets manager. For team deployments, use `.streamlit/secrets.toml` only if protected and excluded from source control.

## Detection rules

- Missing or invalid date, store ID, sales quantity, revenue, or stock.
- Negative sales, revenue, or stock.
- Duplicate `(date, store_id)` keys (assumes one aggregate row per store per day).
- Revenue inconsistency where `revenue_inr` differs from `sales_qty × unit_price_inr` beyond a small tolerance, when unit price is available.
- Per-store median absolute deviation (MAD) checks on sales, revenue, and stock outliers.
- Store coverage by date against the configured expected store count; interior dates missing from the observed date range are shown as missing days.

A flag is a **review signal**, not proof that the data is wrong. The duplicate key must be changed if the client's file legitimately contains multiple product/category rows per store-day.

## Important demo limitations before production

- Current benchmarks are calculated from the provided dataset. A production process should compare new data against a clean historical baseline that excludes the incoming day, to reduce self-influence and feedback effects.
- The completeness chart defaults expected stores to the number of distinct stores in the selected file. Enter the client's official expected store count, and ideally load an authoritative store list and delivery calendar.
- A completely missing file can only be detected if there is a schedule/expected-file manifest to compare with actual arrivals. This sample demonstrates missing dates and store coverage within the observed date range.
- Gmail and the dashboard have not been connected to any actual client or live email account by default.
- For daily automation, schedule the detection command using Windows Task Scheduler, cron, or an approved orchestration platform. Do not run a production job from a personal laptop without approval.
