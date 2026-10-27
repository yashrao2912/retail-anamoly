# """Retail sales and stock anomaly detection with optional Gmail email alerts.

# Quick start:
#     pip install -r requirements.txt
#     python anomaly_detection.py
#     python anomaly_detection.py --email

# Gmail environment variables:
#     GMAIL_SENDER, GMAIL_APP_PASSWORD, ALERT_RECIPIENT
# """
# from __future__ import annotations

# import argparse
# import os
# import smtplib
# from email.message import EmailMessage
# from io import BytesIO
# from pathlib import Path

# import numpy as np
# import pandas as pd

# BASE_DIR = Path(__file__).resolve().parent
# DEFAULT_INPUT = BASE_DIR / "retail_sales_stock_1000.csv"
# OUTPUT_CSV = BASE_DIR / "anomaly_report.csv"
# OUTPUT_XLSX = BASE_DIR / "anomaly_report.xlsx"
# REQUIRED_COLUMNS = ["date", "store_id", "sales_qty", "revenue_inr", "stock_qty"]
# NUMERIC_COLUMNS = ["sales_qty", "unit_price_inr", "revenue_inr", "stock_qty"]


# def load_data(path: Path) -> pd.DataFrame:
#     """Read CSV or Excel data and normalize types, with clear validation errors."""
#     if not path.exists():
#         raise FileNotFoundError(f"Input file not found: {path}")
#     if path.suffix.lower() in {".xlsx", ".xls"}:
#         data = pd.read_excel(path, sheet_name=0)
#     else:
#         data = pd.read_csv(path)
#     missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
#     if missing:
#         raise ValueError(f"Input is missing required columns: {', '.join(missing)}")
#     data = data.copy()
#     data["date"] = pd.to_datetime(data["date"], errors="coerce")
#     for column in NUMERIC_COLUMNS:
#         if column in data.columns:
#             data[column] = pd.to_numeric(data[column], errors="coerce")
#     return data


# def detect_anomalies(data: pd.DataFrame) -> pd.DataFrame:
#     """Apply data-quality rules and per-store robust median/MAD outlier checks.

#     This demo calculates its statistical benchmark from the provided data. For live use,
#     compare each incoming day against a clean historical baseline that excludes that day.
#     """
#     missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
#     if missing:
#         raise ValueError(f"Data is missing required columns: {', '.join(missing)}")

#     out = data.copy()
#     out["date"] = pd.to_datetime(out["date"], errors="coerce")
#     for column in NUMERIC_COLUMNS:
#         if column in out.columns:
#             out[column] = pd.to_numeric(out[column], errors="coerce")
#     out["anomaly_flags"] = ""
#     out["severity"] = "Normal"

#     severity_rank = {"Normal": 0, "Low": 1, "Medium": 2, "High": 3}

#     def add_flag(mask: pd.Series, name: str, severity: str = "High") -> None:
#         mask = pd.Series(mask, index=out.index).fillna(False).astype(bool)
#         if not mask.any():
#             return
#         out.loc[mask, "anomaly_flags"] = out.loc[mask, "anomaly_flags"].apply(
#             lambda current: f"{current}; {name}".strip("; ")
#         )
#         current_rank = out.loc[mask, "severity"].map(severity_rank).fillna(0)
#         out.loc[mask, "severity"] = np.where(
#             current_rank < severity_rank[severity], severity, out.loc[mask, "severity"]
#         )

#     add_flag(out["date"].isna(), "INVALID_DATE")
#     add_flag(out["store_id"].isna() | out["store_id"].astype(str).str.strip().eq(""), "MISSING_STORE_ID")
#     add_flag(out["sales_qty"].isna(), "MISSING_SALES_QTY")
#     add_flag(out["revenue_inr"].isna(), "MISSING_REVENUE")
#     add_flag(out["stock_qty"].isna(), "MISSING_STOCK")
#     add_flag(out["sales_qty"].lt(0), "NEGATIVE_SALES_QTY")
#     add_flag(out["revenue_inr"].lt(0), "NEGATIVE_REVENUE")
#     add_flag(out["stock_qty"].lt(0), "NEGATIVE_STOCK")

#     # Assumes a single aggregate row per store per day. Adjust the key if multiple
#     # product/category rows per store-day are valid in the client's source data.
#     add_flag(out.duplicated(subset=["date", "store_id"], keep=False), "DUPLICATE_STORE_DATE")

#     if "unit_price_inr" in out.columns:
#         expected_revenue = out["sales_qty"] * out["unit_price_inr"]
#         mismatch = (
#             expected_revenue.notna()
#             & out["revenue_inr"].notna()
#             & ((out["revenue_inr"] - expected_revenue).abs() > (expected_revenue.abs() * 0.03 + 2))
#         )
#         add_flag(mismatch, "REVENUE_MISMATCH")

#     for column, flag_name in [
#         ("sales_qty", "SALES_OUTLIER"),
#         ("revenue_inr", "REVENUE_OUTLIER"),
#         ("stock_qty", "STOCK_OUTLIER"),
#     ]:
#         valid = out[column].notna() & out["store_id"].notna()
#         if not valid.any():
#             continue
#         values = out.loc[valid, column]
#         store_ids = out.loc[valid, "store_id"]
#         medians = values.groupby(store_ids).transform("median")
#         mads = values.groupby(store_ids).transform(
#             lambda series: np.median(np.abs(series - np.median(series)))
#         )
#         robust_z = 0.6745 * (values - medians) / mads.replace(0, np.nan)
#         fallback = (values - medians).abs() > (medians.abs() * 0.75 + 10)
#         outlier = pd.Series(False, index=out.index)
#         outlier.loc[valid] = (robust_z.abs() > 3.5) | (robust_z.isna() & fallback)
#         add_flag(outlier, flag_name, "Medium")

#     out["anomaly_flags"] = out["anomaly_flags"].replace("", "NONE")
#     out["status"] = np.where(out["anomaly_flags"].eq("NONE"), "OK", "REVIEW")
#     return out


# def report_to_excel_bytes(report: pd.DataFrame) -> bytes:
#     """Return an Excel workbook in memory for email attachments or downloads."""
#     buffer = BytesIO()
#     flagged = report[report["status"].eq("REVIEW")]
#     with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
#         report.to_excel(writer, index=False, sheet_name="Anomaly_Report")
#         flagged.to_excel(writer, index=False, sheet_name="Flagged_Rows")
#     return buffer.getvalue()


# def send_gmail_alert(report: pd.DataFrame) -> None:
#     """Email an anomaly digest and report to the configured recipient."""
#     sender = os.getenv("GMAIL_SENDER", "").strip()
#     password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
#     recipient = os.getenv("ALERT_RECIPIENT", "").strip()
#     if not all([sender, password, recipient]):
#         raise RuntimeError(
#             "Set GMAIL_SENDER, GMAIL_APP_PASSWORD, and ALERT_RECIPIENT environment variables first."
#         )

#     flagged = report[report["status"].eq("REVIEW")]
#     message = EmailMessage()
#     message["Subject"] = f"[Retail Data Alert] {len(flagged)} row(s) flagged for review"
#     message["From"] = sender
#     message["To"] = recipient
#     if flagged.empty:
#         body = "Daily retail data validation completed. No anomalies were detected."
#     else:
#         display_columns = [
#             column for column in ["date", "store_id", "sales_qty", "revenue_inr", "stock_qty", "anomaly_flags"]
#             if column in flagged.columns
#         ]
#         body = (
#             f"The daily retail data validation flagged {len(flagged)} row(s) for review.\n\n"
#             "Please inspect the attached report before using the data for business reporting.\n\n"
#             + flagged[display_columns].head(30).to_string(index=False)
#             + "\n\nThese are review signals, not proof that the data is incorrect."
#         )
#     message.set_content(body)
#     message.add_attachment(
#         report_to_excel_bytes(report),
#         maintype="application",
#         subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#         filename="anomaly_report.xlsx",
#     )
#     with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
#         smtp.login(sender, password)
#         smtp.send_message(message)
#     print(f"Gmail alert sent to {recipient}")


# def main() -> None:
#     parser = argparse.ArgumentParser(description="Detect suspicious retail sales and stock data.")
#     parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV/XLSX path")
#     parser.add_argument("--email", action="store_true", help="Send an email alert if suspicious rows are found")
#     args = parser.parse_args()

#     data = load_data(Path(args.input))
#     report = detect_anomalies(data)
#     report.to_csv(OUTPUT_CSV, index=False)
#     report.to_excel(OUTPUT_XLSX, index=False, engine="openpyxl")
#     flagged = report[report["status"].eq("REVIEW")]
#     print(f"Rows analyzed: {len(report):,}")
#     print(f"Rows flagged for review: {len(flagged):,}")
#     print(f"Saved report: {OUTPUT_CSV}")
#     print(f"Saved report: {OUTPUT_XLSX}")

#     if args.email:
#         if flagged.empty:
#             print("No anomalies detected; no alert email sent.")
#         else:
#             send_gmail_alert(report)


# if __name__ == "__main__":
#     main()

























"""Retail sales and stock anomaly detection with optional Gmail email alerts.

Quick start:
    pip install -r requirements.txt
    python anomaly_detection.py
    python anomaly_detection.py --email

Gmail environment variables:
    GMAIL_SENDER, GMAIL_APP_PASSWORD, ALERT_RECIPIENT
"""
from __future__ import annotations

import argparse
import os
import smtplib
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Load secrets from a local .env file, if present. The file should never be committed.
load_dotenv(BASE_DIR / ".env")
DEFAULT_INPUT = BASE_DIR / "retail_sales_stock_1000.csv"
OUTPUT_CSV = BASE_DIR / "anomaly_report.csv"
OUTPUT_XLSX = BASE_DIR / "anomaly_report.xlsx"
REQUIRED_COLUMNS = ["date", "store_id", "sales_qty", "revenue_inr", "stock_qty"]
NUMERIC_COLUMNS = ["sales_qty", "unit_price_inr", "revenue_inr", "stock_qty"]


def load_data(path: Path) -> pd.DataFrame:
    """Read CSV or Excel data and normalize types, with clear validation errors."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        data = pd.read_excel(path, sheet_name=0)
    else:
        data = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Input is missing required columns: {', '.join(missing)}")
    data = data.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def detect_anomalies(data: pd.DataFrame) -> pd.DataFrame:
    """Apply data-quality rules and per-store robust median/MAD outlier checks.

    This demo calculates its statistical benchmark from the provided data. For live use,
    compare each incoming day against a clean historical baseline that excludes that day.
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Data is missing required columns: {', '.join(missing)}")

    out = data.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out["anomaly_flags"] = ""
    out["severity"] = "Normal"

    severity_rank = {"Normal": 0, "Low": 1, "Medium": 2, "High": 3}

    def add_flag(mask: pd.Series, name: str, severity: str = "High") -> None:
        mask = pd.Series(mask, index=out.index).fillna(False).astype(bool)
        if not mask.any():
            return
        out.loc[mask, "anomaly_flags"] = out.loc[mask, "anomaly_flags"].apply(
            lambda current: f"{current}; {name}".strip("; ")
        )
        current_rank = out.loc[mask, "severity"].map(severity_rank).fillna(0)
        out.loc[mask, "severity"] = np.where(
            current_rank < severity_rank[severity], severity, out.loc[mask, "severity"]
        )

    add_flag(out["date"].isna(), "INVALID_DATE")
    add_flag(out["store_id"].isna() | out["store_id"].astype(str).str.strip().eq(""), "MISSING_STORE_ID")
    add_flag(out["sales_qty"].isna(), "MISSING_SALES_QTY")
    add_flag(out["revenue_inr"].isna(), "MISSING_REVENUE")
    add_flag(out["stock_qty"].isna(), "MISSING_STOCK")
    add_flag(out["sales_qty"].lt(0), "NEGATIVE_SALES_QTY")
    add_flag(out["revenue_inr"].lt(0), "NEGATIVE_REVENUE")
    add_flag(out["stock_qty"].lt(0), "NEGATIVE_STOCK")

    # Assumes a single aggregate row per store per day. Adjust the key if multiple
    # product/category rows per store-day are valid in the client's source data.
    add_flag(out.duplicated(subset=["date", "store_id"], keep=False), "DUPLICATE_STORE_DATE")

    if "unit_price_inr" in out.columns:
        expected_revenue = out["sales_qty"] * out["unit_price_inr"]
        mismatch = (
            expected_revenue.notna()
            & out["revenue_inr"].notna()
            & ((out["revenue_inr"] - expected_revenue).abs() > (expected_revenue.abs() * 0.03 + 2))
        )
        add_flag(mismatch, "REVENUE_MISMATCH")

    for column, flag_name in [
        ("sales_qty", "SALES_OUTLIER"),
        ("revenue_inr", "REVENUE_OUTLIER"),
        ("stock_qty", "STOCK_OUTLIER"),
    ]:
        valid = out[column].notna() & out["store_id"].notna()
        if not valid.any():
            continue
        values = out.loc[valid, column]
        store_ids = out.loc[valid, "store_id"]
        medians = values.groupby(store_ids).transform("median")
        mads = values.groupby(store_ids).transform(
            lambda series: np.median(np.abs(series - np.median(series)))
        )
        robust_z = 0.6745 * (values - medians) / mads.replace(0, np.nan)
        fallback = (values - medians).abs() > (medians.abs() * 0.75 + 10)
        outlier = pd.Series(False, index=out.index)
        outlier.loc[valid] = (robust_z.abs() > 3.5) | (robust_z.isna() & fallback)
        add_flag(outlier, flag_name, "Medium")

    out["anomaly_flags"] = out["anomaly_flags"].replace("", "NONE")
    out["status"] = np.where(out["anomaly_flags"].eq("NONE"), "OK", "REVIEW")
    return out


def report_to_excel_bytes(report: pd.DataFrame) -> bytes:
    """Return an Excel workbook in memory for email attachments or downloads."""
    buffer = BytesIO()
    flagged = report[report["status"].eq("REVIEW")]
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        report.to_excel(writer, index=False, sheet_name="Anomaly_Report")
        flagged.to_excel(writer, index=False, sheet_name="Flagged_Rows")
    return buffer.getvalue()


def send_gmail_alert(report: pd.DataFrame) -> None:
    """Email an anomaly digest and report to the configured recipient."""
    sender = os.getenv("GMAIL_SENDER", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    recipient = os.getenv("ALERT_RECIPIENT", "").strip()
    if not all([sender, password, recipient]):
        raise RuntimeError(
            "Set GMAIL_SENDER, GMAIL_APP_PASSWORD, and ALERT_RECIPIENT environment variables first."
        )

    flagged = report[report["status"].eq("REVIEW")]
    message = EmailMessage()
    message["Subject"] = f"[Retail Data Alert] {len(flagged)} row(s) flagged for review"
    message["From"] = sender
    message["To"] = recipient
    if flagged.empty:
        body = "Daily retail data validation completed. No anomalies were detected."
    else:
        display_columns = [
            column for column in ["date", "store_id", "sales_qty", "revenue_inr", "stock_qty", "anomaly_flags"]
            if column in flagged.columns
        ]
        body = (
            f"The daily retail data validation flagged {len(flagged)} row(s) for review.\n\n"
            "Please inspect the attached report before using the data for business reporting.\n\n"
            + flagged[display_columns].head(30).to_string(index=False)
            + "\n\nThese are review signals, not proof that the data is incorrect."
        )
    message.set_content(body)
    message.add_attachment(
        report_to_excel_bytes(report),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="anomaly_report.xlsx",
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)
    print(f"Gmail alert sent to {recipient}")



def main() -> None:
    parser = argparse.ArgumentParser(description="Detect suspicious retail sales and stock data.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV/XLSX path")
    parser.add_argument("--email", action="store_true", help="Send an email alert if suspicious rows are found")
    args = parser.parse_args()

    data = load_data(Path(args.input))
    report = detect_anomalies(data)
    report.to_csv(OUTPUT_CSV, index=False)
    report.to_excel(OUTPUT_XLSX, index=False, engine="openpyxl")
    flagged = report[report["status"].eq("REVIEW")]
    print(f"Rows analyzed: {len(report):,}")
    print(f"Rows flagged for review: {len(flagged):,}")
    print(f"Saved report: {OUTPUT_CSV}")
    print(f"Saved report: {OUTPUT_XLSX}")

    if args.email:
        if flagged.empty:
            print("No anomalies detected; no alert email sent.")
        else:
            send_gmail_alert(report)


if __name__ == "__main__":
    main()
