# """Streamlit dashboard for retail sales and stock anomaly monitoring.

# Start with: streamlit run app.py
# """
# from __future__ import annotations

# import os
# from datetime import date
# from io import BytesIO
# from pathlib import Path

# import numpy as np
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import streamlit as st
# from dotenv import load_dotenv

# from anomaly_detection import detect_anomalies, report_to_excel_bytes, send_gmail_alert

# st.set_page_config(
#     page_title="Retail Anomaly Monitor",
#     page_icon="🛡️",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# BASE_DIR = Path(__file__).resolve().parent
# # Load local Gmail settings from .env before checking whether email is configured.
# load_dotenv(BASE_DIR / ".env", override=True)
# DEFAULT_DATA = BASE_DIR / "retail_sales_stock_1000.csv"
# REQUIRED = ["date", "store_id", "sales_qty", "revenue_inr", "stock_qty"]


# def load_uploaded_or_sample(uploaded_file: object | None) -> pd.DataFrame:
#     if uploaded_file is None:
#         if not DEFAULT_DATA.exists():
#             return pd.DataFrame()
#         data = pd.read_csv(DEFAULT_DATA)
#     elif uploaded_file.name.lower().endswith(".csv"):
#         data = pd.read_csv(uploaded_file)
#     else:
#         data = pd.read_excel(uploaded_file, sheet_name=0)
#     missing = [column for column in REQUIRED if column not in data.columns]
#     if missing:
#         raise ValueError("Missing required column(s): " + ", ".join(missing))
#     data = data.copy()
#     data["date"] = pd.to_datetime(data["date"], errors="coerce")
#     for column in ["sales_qty", "revenue_inr", "stock_qty", "unit_price_inr"]:
#         if column in data.columns:
#             data[column] = pd.to_numeric(data[column], errors="coerce")
#     return data


# def build_completeness(data: pd.DataFrame, expected_stores: int) -> pd.DataFrame:
#     """Count stores and rows per calendar date, including entirely missing dates in-range."""
#     valid = data.dropna(subset=["date", "store_id"]).copy()
#     if valid.empty:
#         return pd.DataFrame(columns=["date", "records_received", "distinct_stores", "expected_stores", "coverage_pct", "status"])
#     valid["date"] = pd.to_datetime(valid["date"]).dt.normalize()
#     counts = valid.groupby("date").agg(
#         records_received=("store_id", "size"),
#         distinct_stores=("store_id", "nunique"),
#     )
#     calendar = pd.date_range(valid["date"].min(), valid["date"].max(), freq="D")
#     counts = counts.reindex(calendar, fill_value=0)
#     counts.index.name = "date"
#     result = counts.reset_index()
#     result["expected_stores"] = int(expected_stores)
#     result["coverage_pct"] = (result["distinct_stores"] / max(1, expected_stores) * 100).round(1)
#     result["status"] = np.select(
#         [result["distinct_stores"].eq(0), result["distinct_stores"].lt(expected_stores)],
#         ["MISSING DAY", "PARTIAL"],
#         default="COMPLETE",
#     )
#     return result


# def fmt_inr(value: float | int) -> str:
#     return "—" if pd.isna(value) else f"₹{value:,.0f}"


# def to_csv_bytes(data: pd.DataFrame) -> bytes:
#     return data.to_csv(index=False).encode("utf-8-sig")


# def env_value(name: str) -> str:
#     value = os.getenv(name, "").strip()
#     try:
#         if not value and name in st.secrets:
#             value = str(st.secrets[name]).strip()
#     except Exception:
#         pass
#     return value


# def missing_gmail_settings() -> list[str]:
#     required = ["GMAIL_SENDER", "GMAIL_APP_PASSWORD", "ALERT_RECIPIENT"]
#     return [name for name in required if not env_value(name) or env_value(name).startswith("your_") or "example.com" in env_value(name)]

# def gmail_is_configured() -> bool:
#     return len(missing_gmail_settings()) == 0


# def primary_anomaly_category(flags: object) -> str:
#     """Assign a display category from the detector's existing flags (UI-only)."""
#     text = "" if pd.isna(flags) else str(flags)
#     if not text or text == "NONE":
#         return "Normal"
#     items = set(text.split("; "))
#     # This is a display priority when a row has multiple flags; all flags remain visible.
#     if "INVALID_DATE" in items or any(x.startswith("MISSING_") for x in items):
#         return "Missing / Invalid Data"
#     if any(x.startswith("DUPLICATE_") for x in items):
#         return "Duplicate Data"
#     if any(x.startswith("NEGATIVE_") for x in items):
#         return "Invalid Numeric Value"
#     if "REVENUE_MISMATCH" in items:
#         return "Revenue Inconsistency"
#     if any(x.endswith("_OUTLIER") for x in items):
#         return "Statistical Outlier"
#     return "Other Review"


# def category_explanation(category: str) -> str:
#     explanations = {
#         "Normal": "No configured anomaly rule was triggered for this row.",
#         "Missing / Invalid Data": "A required field is missing or the date could not be parsed.",
#         "Duplicate Data": "The same date + store_id key appears in more than one row. This assumes one aggregate row per store per day.",
#         "Invalid Numeric Value": "A quantity, revenue, stock, or unit price is negative, which should be checked against business rules.",
#         "Revenue Inconsistency": "Recorded revenue differs from sales_qty × unit_price_inr beyond the configured tolerance (3% of expected revenue + ₹2).",
#         "Statistical Outlier": "Sales, revenue, or stock is unusually far from that store's median under the robust MAD rule (absolute robust Z-score > 3.5); a fallback is used when MAD is zero/unavailable.",
#         "Other Review": "One or more flags require manual inspection.",
#     }
#     return explanations.get(category, "Inspect the flags for the reason this row was selected.")


# st.title("🛡️ Retail Sales & Stock Anomaly Monitor")
# st.caption("Client data intake  →  quality validation  →  anomaly detection  →  investigation  →  Gmail alert")

# with st.sidebar:
#     st.header("Data & filters")
#     uploaded_file = st.file_uploader("Upload client data", type=["csv", "xlsx"])
#     st.caption("Leave empty to use the bundled 1,000-record demo dataset.")

# try:
#     raw = load_uploaded_or_sample(uploaded_file)
# except Exception as exc:
#     st.error(f"Could not load the file: {exc}")
#     st.stop()

# if raw.empty:
#     st.warning("No data found. Upload a CSV/XLSX file or place retail_sales_stock_1000.csv beside app.py.")
#     st.stop()

# try:
#     report = detect_anomalies(raw)
#     # Categorization is a dashboard presentation layer. The detector's original
#     # detailed anomaly_flags remain unchanged and are still shown to users.
#     report["anomaly_category"] = report["anomaly_flags"].apply(primary_anomaly_category)
# except Exception as exc:
#     st.error(f"Anomaly detection failed: {exc}")
#     st.stop()

# all_store_count = int(raw["store_id"].dropna().astype(str).nunique())
# default_expected = max(1, all_store_count)
# with st.sidebar:
#     expected_stores = st.number_input(
#         "Expected stores per day",
#         min_value=1,
#         max_value=100000,
#         value=default_expected,
#         step=1,
#         help="Set this to the client's official expected store count. It helps identify partial or entirely missing days.",
#     )
#     st.markdown("---")
#     store_options = sorted(report["store_id"].dropna().astype(str).unique().tolist())
#     selected_stores = st.multiselect("Stores", options=store_options, default=store_options)
#     status_options = ["OK", "REVIEW"]
#     selected_status = st.multiselect("Record status", options=status_options, default=status_options)
#     if report["date"].notna().any():
#         min_day = report["date"].min().date()
#         max_day = report["date"].max().date()
#         chosen_dates = st.date_input(
#             "Date range",
#             value=(min_day, max_day),
#             min_value=min_day,
#             max_value=max_day,
#         )
#     else:
#         chosen_dates = None
#     st.markdown("---")
#     st.subheader("Gmail setup")
#     configured = gmail_is_configured()
#     if configured:
#         st.success("Credentials detected")
#     else:
#         st.warning("Credentials not configured")
#     st.caption("Email is sent only when you explicitly click the send button in the Gmail Alerts tab.")

# filtered = report.copy()
# filtered = filtered[filtered["store_id"].astype(str).isin(selected_stores)]
# filtered = filtered[filtered["status"].isin(selected_status)]
# if isinstance(chosen_dates, (tuple, list)) and len(chosen_dates) == 2:
#     start_date, end_date = chosen_dates
#     filtered = filtered[filtered["date"].dt.date.between(start_date, end_date)]

# flagged = filtered[filtered["status"].eq("REVIEW")].copy()
# completeness = build_completeness(report, int(expected_stores))
# latest_day = completeness.iloc[-1] if not completeness.empty else None
# latest_coverage = float(latest_day["coverage_pct"]) if latest_day is not None else np.nan

# # Top-level KPI ribbon
# kpis = st.columns(6)
# kpis[0].metric("Records analyzed", f"{len(filtered):,}")
# kpis[1].metric("Rows flagged", f"{len(flagged):,}", delta=f"{(len(flagged) / len(filtered) * 100):.1f}%" if len(filtered) else "0%", delta_color="inverse")
# kpis[2].metric("Sales quantity", f"{filtered['sales_qty'].sum(min_count=1):,.0f}" if filtered["sales_qty"].notna().any() else "—")
# kpis[3].metric("Revenue", fmt_inr(filtered["revenue_inr"].sum(min_count=1)))
# kpis[4].metric("Stock quantity", f"{filtered['stock_qty'].sum(min_count=1):,.0f}" if filtered["stock_qty"].notna().any() else "—")
# kpis[5].metric("Latest store coverage", f"{latest_coverage:.1f}%" if pd.notna(latest_coverage) else "—")

# st.markdown("---")
# tab_overview, tab_quality, tab_investigation, tab_categorization, tab_benchmarks, tab_explorer, tab_email = st.tabs(
#     ["Overview", "Data completeness", "Anomaly investigation", "How anomalies are categorized", "Trends & benchmarks", "Data explorer", "Gmail alerts"]
# )

# with tab_overview:
#     left, right = st.columns([1.35, 1])
#     with left:
#         st.subheader("Daily sales quantity")
#         if not filtered.empty and filtered["date"].notna().any():
#             daily = filtered.groupby("date", as_index=False).agg(
#                 sales_qty=("sales_qty", "sum"), revenue_inr=("revenue_inr", "sum"), stock_qty=("stock_qty", "sum")
#             )
#             fig = go.Figure()
#             fig.add_trace(go.Scatter(x=daily["date"], y=daily["sales_qty"], mode="lines+markers", name="Sales quantity"))
#             fig.update_layout(height=340, margin=dict(l=8, r=8, t=25, b=8), xaxis_title="Date", yaxis_title="Units sold")
#             st.plotly_chart(fig, use_container_width=True)
#         else:
#             st.info("No dated records match the selected filters.")
#     with right:
#         st.subheader("Data quality status")
#         status_counts = filtered["status"].value_counts().rename_axis("status").reset_index(name="rows")
#         if not status_counts.empty:
#             fig = px.pie(status_counts, names="status", values="rows", hole=0.58, color="status",
#                          color_discrete_map={"OK": "#18A999", "REVIEW": "#E76F51"})
#             fig.update_layout(height=340, margin=dict(l=8, r=8, t=25, b=8), showlegend=True)
#             st.plotly_chart(fig, use_container_width=True)
#         else:
#             st.info("No records match the selected filters.")

#     left, right = st.columns(2)
#     with left:
#         st.subheader("Most common anomaly types")
#         anomaly_types = flagged["anomaly_flags"].fillna("").str.split("; ").explode()
#         anomaly_types = anomaly_types[~anomaly_types.isin(["NONE", ""])]
#         type_counts = anomaly_types.value_counts().head(12).rename_axis("anomaly_type").reset_index(name="rows")
#         if not type_counts.empty:
#             st.plotly_chart(px.bar(type_counts, x="rows", y="anomaly_type", orientation="h"), use_container_width=True)
#         else:
#             st.success("No anomalies in the current selection.")
#     with right:
#         st.subheader("Stores with most flagged rows")
#         if not flagged.empty:
#             by_store = flagged.groupby("store_id").size().sort_values(ascending=False).head(10).reset_index(name="flagged_rows")
#             st.plotly_chart(px.bar(by_store, x="store_id", y="flagged_rows"), use_container_width=True)
#         else:
#             st.info("No flagged stores in the current selection.")

#     st.subheader("Monitoring workflow")
#     workflow = st.columns(5)
#     workflow_items = [
#         ("1 · Receive", "Client sales and stock files"),
#         ("2 · Validate", "Missing values and duplicate keys"),
#         ("3 · Compare", "Historical store-level patterns"),
#         ("4 · Flag", "Suspicious records for review"),
#         ("5 · Notify", "Gmail alert with report attachment"),
#     ]
#     for column, (heading, detail) in zip(workflow, workflow_items):
#         with column:
#             st.markdown(f"**{heading}**")
#             st.caption(detail)

# with tab_quality:
#     st.subheader("Daily data completeness")
#     st.write("Coverage checks compare received distinct stores with the expected store count. The dashboard also inserts calendar dates missing between the first and last date in the uploaded data.")
#     if not completeness.empty:
#         fig = px.bar(completeness, x="date", y="coverage_pct", color="status",
#                      hover_data=["records_received", "distinct_stores", "expected_stores"],
#                      color_discrete_map={"COMPLETE": "#18A999", "PARTIAL": "#F4A261", "MISSING DAY": "#E76F51"},
#                      labels={"date": "Date", "coverage_pct": "Store coverage (%)", "status": "Coverage status"})
#         fig.update_layout(yaxis_range=[0, max(105, float(completeness["coverage_pct"].max() or 0) + 5)])
#         st.plotly_chart(fig, use_container_width=True)
#         st.dataframe(completeness, use_container_width=True, hide_index=True)
#         issue_days = completeness[completeness["status"].ne("COMPLETE")]
#         if not issue_days.empty:
#             st.warning(f"{len(issue_days)} date(s) have partial or missing store coverage. Verify against the client's official delivery schedule.")
#         else:
#             st.success("All dates in the observed date range meet the configured store-count expectation.")
#     else:
#         st.info("Date and store identifiers are needed for daily completeness checks.")

#     st.subheader("Data validation checks")
#     if not flagged.empty:
#         flag_counts = flagged["anomaly_flags"].fillna("").str.split("; ").explode()
#         flag_counts = flag_counts[~flag_counts.isin(["NONE", ""])]
#         validation = flag_counts.value_counts().rename_axis("check").reset_index(name="flagged row count")
#         st.dataframe(validation, use_container_width=True, hide_index=True)
#     else:
#         st.success("No data quality exceptions are flagged in the current selection.")

# with tab_investigation:
#     st.subheader("Rows requiring investigation")
#     if flagged.empty:
#         st.success("No rows are flagged for review under the current filters.")
#     else:
#         visible_cols = [c for c in ["date", "store_id", "category", "sales_qty", "unit_price_inr", "revenue_inr", "stock_qty", "severity", "anomaly_flags", "source_file"] if c in flagged.columns]
#         st.dataframe(flagged[visible_cols].sort_values(["severity", "date"], ascending=[False, False]), use_container_width=True, hide_index=True)
#         st.download_button("Download flagged rows (CSV)", to_csv_bytes(flagged[visible_cols]), "flagged_rows.csv", "text/csv")
#         st.download_button("Download flagged report (Excel)", report_to_excel_bytes(flagged), "flagged_anomaly_report.xlsx",
#                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
#     st.caption("A flag means the record is suspicious and needs review; it does not prove the record is wrong.")

# with tab_categorization:
#     st.subheader("How this dashboard categorizes anomalies")
#     st.write(
#         "This page explains the rules used by the detector and shows how the current dataset was categorized. "
#         "The category is a readable summary; the detailed `anomaly_flags` column preserves every rule that fired."
#     )
#     st.info(
#         "Important: a flag means 'investigate this record', not 'confirmed error'. "
#         "If a row has several flags, the dashboard assigns one primary category using the priority below, "
#         "while keeping all its detailed flags."
#     )

#     # Counts reflect the currently selected sidebar filters.
#     category_counts = filtered["anomaly_category"].value_counts().rename_axis("Primary category").reset_index(name="Rows")
#     category_counts = category_counts.sort_values("Rows", ascending=False)
#     left, right = st.columns([1, 1.15])
#     with left:
#         st.markdown("**Categorization of selected records**")
#         if not category_counts.empty:
#             st.dataframe(category_counts, use_container_width=True, hide_index=True)
#             fig = px.bar(category_counts, x="Primary category", y="Rows", color="Primary category")
#             fig.update_layout(showlegend=False, xaxis_tickangle=-25, margin=dict(t=20, b=80))
#             st.plotly_chart(fig, use_container_width=True)
#     with right:
#         st.markdown("**Rules used by the detector**")
#         rule_rows = [
#             ("Missing / Invalid Data", "INVALID_DATE or any MISSING_* flag", "Required fields are missing or the date is invalid."),
#             ("Duplicate Data", "DUPLICATE_STORE_DATE", "Repeated date + store_id key; valid only if one row per store per day is expected."),
#             ("Invalid Numeric Value", "NEGATIVE_* flag", "Negative sales, unit price, revenue, or stock needs checking."),
#             ("Revenue Inconsistency", "REVENUE_MISMATCH", "Absolute difference > 3% of expected revenue + ₹2, where expected revenue = sales_qty × unit_price_inr."),
#             ("Statistical Outlier", "SALES_OUTLIER / REVENUE_OUTLIER / STOCK_OUTLIER", "Within each store, robust Z-score absolute value > 3.5; fallback threshold is used when MAD is zero/unavailable."),
#             ("Normal", "No flag (NONE)", "No configured row-level rule was triggered."),
#         ]
#         st.dataframe(pd.DataFrame(rule_rows, columns=["Primary category", "Trigger", "Meaning"]), use_container_width=True, hide_index=True)

#     st.markdown("**Primary category priority when a row has multiple flags**")
#     st.caption("1. Missing / Invalid Data → 2. Duplicate Data → 3. Invalid Numeric Value → 4. Revenue Inconsistency → 5. Statistical Outlier → 6. Normal. This priority is only for display; all detailed flags are retained.")

#     st.markdown("---")
#     st.markdown("**Walk through a specific record**")
#     candidates = report[report["status"].eq("REVIEW")].copy()
#     if candidates.empty:
#         st.success("No records are flagged under the current dataset.")
#     else:
#         candidates["_row_label"] = candidates.apply(
#             lambda r: f"Row {r.name + 1} · Store {r.get('store_id', '—')} · {str(r.get('date', '—'))[:10]} · {r['anomaly_category']}",
#             axis=1,
#         )
#         selected_label = st.selectbox(
#             "Choose a flagged row to see why it was categorized",
#             candidates["_row_label"].tolist(),
#             key="categorization_example_row",
#         )
#         chosen = candidates.loc[candidates["_row_label"].eq(selected_label)].iloc[0]
#         st.markdown(f"**Primary category:** `{chosen['anomaly_category']}`")
#         st.write(category_explanation(chosen["anomaly_category"]))
#         st.markdown(f"**Detailed flags:** `{chosen['anomaly_flags']}`")
#         metric_cols = st.columns(4)
#         if "sales_qty" in chosen.index:
#             metric_cols[0].metric("Sales quantity", "—" if pd.isna(chosen["sales_qty"]) else f"{chosen['sales_qty']:,.2f}")
#         if "unit_price_inr" in chosen.index:
#             metric_cols[1].metric("Unit price", fmt_inr(chosen["unit_price_inr"]))
#         if "revenue_inr" in chosen.index:
#             metric_cols[2].metric("Revenue", fmt_inr(chosen["revenue_inr"]))
#         if "stock_qty" in chosen.index:
#             metric_cols[3].metric("Stock quantity", "—" if pd.isna(chosen["stock_qty"]) else f"{chosen['stock_qty']:,.2f}")
#         if "sales_qty" in chosen.index and "unit_price_inr" in chosen.index and "revenue_inr" in chosen.index:
#             if pd.notna(chosen["sales_qty"]) and pd.notna(chosen["unit_price_inr"]) and pd.notna(chosen["revenue_inr"]):
#                 expected_rev = float(chosen["sales_qty"]) * float(chosen["unit_price_inr"])
#                 st.write(
#                     f"Revenue cross-check: expected = {chosen['sales_qty']:,.2f} × "
#                     f"{fmt_inr(chosen['unit_price_inr'])} = {fmt_inr(expected_rev)}; "
#                     f"recorded revenue = {fmt_inr(chosen['revenue_inr'])}."
#                 )
#         show_cols = [c for c in ["date", "store_id", "category", "sales_qty", "unit_price_inr", "revenue_inr", "stock_qty", "severity", "anomaly_category", "anomaly_flags"] if c in chosen.index]
#         st.dataframe(pd.DataFrame([chosen[show_cols]]), use_container_width=True, hide_index=True)
#         st.caption("The row number is based on its position in the loaded dataset. Always verify against the original source file before correcting data.")

# with tab_benchmarks:
#     st.subheader("Store-level historical benchmarks")
#     numeric_metrics = [column for column in ["sales_qty", "revenue_inr", "stock_qty"] if column in filtered.columns]
#     if numeric_metrics and not filtered.empty:
#         metric = st.selectbox("Metric to inspect", numeric_metrics, key="benchmark_metric")
#         benchmark = filtered.groupby("store_id")[metric].agg(
#             record_count="count", median="median", mean="mean", std_dev="std", minimum="min", maximum="max"
#         ).reset_index()
#         st.dataframe(benchmark, use_container_width=True, hide_index=True)
#         daily = filtered.groupby("date", as_index=False)[metric].sum(min_count=1)
#         st.plotly_chart(px.line(daily, x="date", y=metric, markers=True, title=f"Daily total: {metric}"), use_container_width=True)
#     else:
#         st.info("No supported numeric metrics are available for these filters.")
#     st.info("The demo calculates MAD-based outlier checks from the supplied dataset. For production, build benchmarks from clean historical data and compare incoming data against that separate baseline.")

# with tab_explorer:
#     st.subheader("Data explorer")
#     st.write(f"Selected rows: **{len(filtered):,}** · Latest date in selection: **{filtered['date'].max().strftime('%d %b %Y') if not filtered.empty and filtered['date'].notna().any() else '—'}**")
#     st.dataframe(filtered, use_container_width=True, hide_index=True)
#     st.download_button("Download filtered data (CSV)", to_csv_bytes(filtered), "filtered_retail_data.csv", "text/csv")
#     st.download_button("Download full anomaly report (Excel)", report_to_excel_bytes(report), "anomaly_report.xlsx",
#                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# with tab_email:
#     st.subheader("Gmail alert configuration")
#     configured = gmail_is_configured()
#     if configured:
#         st.success(
#             f"Gmail variables are configured for sender {env_value('GMAIL_SENDER')} "
#             f"→ recipient {env_value('ALERT_RECIPIENT')}."
#         )
#     else:
#         env_file = BASE_DIR / ".env"
#         st.warning("Gmail credentials are not configured in this Streamlit process.")
#         if not env_file.exists():
#             st.error(f"No .env file was found beside app.py. Expected location: {env_file}")
#             st.markdown("In the VS Code terminal, run `Copy-Item .env.example .env`, then edit `.env` and replace every example value.")
#         else:
#             st.info(f".env file found at: {env_file}")
#             missing = missing_gmail_settings()
#             if missing:
#                 st.write("These settings are missing or still contain example placeholders:")
#                 for name in missing:
#                     st.code(name, language="text")
#             st.markdown("Save `.env`, fully stop Streamlit with Ctrl+C, and restart it with `streamlit run app.py`.")
#         st.caption("Use a Google App Password, not your normal Gmail password. Never print or share the App Password.")

#     st.write(f"Current filters contain **{len(flagged)}** rows flagged for review.")
#     confirm_email = st.checkbox("I have reviewed the flagged records and want to send an email alert", value=False)
#     if st.button("Send Gmail alert with anomaly report", type="primary", disabled=(not configured or not confirm_email or flagged.empty)):
#         with st.spinner("Sending Gmail alert…"):
#             try:
#                 # Email only the records matching the current filters; attach an Excel report.
#                 send_gmail_alert(flagged)
#                 st.success(f"Alert email sent to {env_value('ALERT_RECIPIENT')}.")
#             except Exception as exc:
#                 st.error(f"Email could not be sent: {exc}")
#     if flagged.empty:
#         st.info("No flagged rows match the current filters, so the alert button is disabled.")
#     st.caption("Opening or refreshing the dashboard does not send email. An alert is sent only after the explicit confirmation checkbox and button click.")

# st.markdown("---")
# st.caption("Demo data is synthetic. Configure official store lists, delivery calendars, thresholds, access controls, and approved secrets handling before production use.")
































# """Streamlit dashboard for retail sales and stock anomaly monitoring.

# Start with: streamlit run app.py
# """
# from __future__ import annotations

# import os
# from datetime import date
# from io import BytesIO
# from pathlib import Path

# import numpy as np
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import streamlit as st
# from dotenv import load_dotenv

# from anomaly_detection import detect_anomalies, report_to_excel_bytes, send_gmail_alert

# st.set_page_config(
#     page_title="Retail Anomaly Monitor",
#     page_icon="🛡️",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# BASE_DIR = Path(__file__).resolve().parent
# # Load local Gmail settings from .env before checking whether email is configured.
# load_dotenv(BASE_DIR / ".env", override=True)
# DEFAULT_DATA = BASE_DIR / "retail_sales_stock_1000.csv"
# REQUIRED = ["date", "store_id", "sales_qty", "revenue_inr", "stock_qty"]


# def load_uploaded_or_sample(uploaded_file: object | None) -> pd.DataFrame:
#     if uploaded_file is None:
#         if not DEFAULT_DATA.exists():
#             return pd.DataFrame()
#         data = pd.read_csv(DEFAULT_DATA)
#     elif uploaded_file.name.lower().endswith(".csv"):
#         data = pd.read_csv(uploaded_file)
#     else:
#         data = pd.read_excel(uploaded_file, sheet_name=0)
#     missing = [column for column in REQUIRED if column not in data.columns]
#     if missing:
#         raise ValueError("Missing required column(s): " + ", ".join(missing))
#     data = data.copy()
#     data["date"] = pd.to_datetime(data["date"], errors="coerce")
#     for column in ["sales_qty", "revenue_inr", "stock_qty", "unit_price_inr"]:
#         if column in data.columns:
#             data[column] = pd.to_numeric(data[column], errors="coerce")
#     return data


# def build_completeness(data: pd.DataFrame, expected_stores: int) -> pd.DataFrame:
#     """Count stores and rows per calendar date, including entirely missing dates in-range."""
#     valid = data.dropna(subset=["date", "store_id"]).copy()
#     if valid.empty:
#         return pd.DataFrame(columns=["date", "records_received", "distinct_stores", "expected_stores", "coverage_pct", "status"])
#     valid["date"] = pd.to_datetime(valid["date"]).dt.normalize()
#     counts = valid.groupby("date").agg(
#         records_received=("store_id", "size"),
#         distinct_stores=("store_id", "nunique"),
#     )
#     calendar = pd.date_range(valid["date"].min(), valid["date"].max(), freq="D")
#     counts = counts.reindex(calendar, fill_value=0)
#     counts.index.name = "date"
#     result = counts.reset_index()
#     result["expected_stores"] = int(expected_stores)
#     result["coverage_pct"] = (result["distinct_stores"] / max(1, expected_stores) * 100).round(1)
#     result["status"] = np.select(
#         [result["distinct_stores"].eq(0), result["distinct_stores"].lt(expected_stores)],
#         ["MISSING DAY", "PARTIAL"],
#         default="COMPLETE",
#     )
#     return result


# def fmt_inr(value: float | int) -> str:
#     return "—" if pd.isna(value) else f"₹{value:,.0f}"


# def to_csv_bytes(data: pd.DataFrame) -> bytes:
#     return data.to_csv(index=False).encode("utf-8-sig")


# def env_value(name: str) -> str:
#     value = os.getenv(name, "").strip()
#     try:
#         if not value and name in st.secrets:
#             value = str(st.secrets[name]).strip()
#     except Exception:
#         pass
#     return value


# def missing_gmail_settings() -> list[str]:
#     required = ["GMAIL_SENDER", "GMAIL_APP_PASSWORD", "ALERT_RECIPIENT"]
#     return [name for name in required if not env_value(name) or env_value(name).startswith("your_") or "example.com" in env_value(name)]

# def gmail_is_configured() -> bool:
#     return len(missing_gmail_settings()) == 0


# st.title("🛡️ Retail Sales & Stock Anomaly Monitor")
# st.caption("Client data intake  →  quality validation  →  anomaly detection  →  investigation  →  Gmail alert")

# with st.sidebar:
#     st.header("Data & filters")
#     uploaded_file = st.file_uploader("Upload client data", type=["csv", "xlsx"])
#     st.caption("Leave empty to use the bundled 1,000-record demo dataset.")

# try:
#     raw = load_uploaded_or_sample(uploaded_file)
# except Exception as exc:
#     st.error(f"Could not load the file: {exc}")
#     st.stop()

# if raw.empty:
#     st.warning("No data found. Upload a CSV/XLSX file or place retail_sales_stock_1000.csv beside app.py.")
#     st.stop()

# try:
#     report = detect_anomalies(raw)
# except Exception as exc:
#     st.error(f"Anomaly detection failed: {exc}")
#     st.stop()

# all_store_count = int(raw["store_id"].dropna().astype(str).nunique())
# default_expected = max(1, all_store_count)
# with st.sidebar:
#     expected_stores = st.number_input(
#         "Expected stores per day",
#         min_value=1,
#         max_value=100000,
#         value=default_expected,
#         step=1,
#         help="Set this to the client's official expected store count. It helps identify partial or entirely missing days.",
#     )
#     st.markdown("---")
#     store_options = sorted(report["store_id"].dropna().astype(str).unique().tolist())
#     selected_stores = st.multiselect("Stores", options=store_options, default=store_options)
#     status_options = ["OK", "REVIEW"]
#     selected_status = st.multiselect("Record status", options=status_options, default=status_options)
#     if report["date"].notna().any():
#         min_day = report["date"].min().date()
#         max_day = report["date"].max().date()
#         chosen_dates = st.date_input(
#             "Date range",
#             value=(min_day, max_day),
#             min_value=min_day,
#             max_value=max_day,
#         )
#     else:
#         chosen_dates = None
#     st.markdown("---")
#     st.subheader("Gmail setup")
#     configured = gmail_is_configured()
#     if configured:
#         st.success("Credentials detected")
#     else:
#         st.warning("Credentials not configured")
#     st.caption("Email is sent only when you explicitly click the send button in the Gmail Alerts tab.")

# filtered = report.copy()
# filtered = filtered[filtered["store_id"].astype(str).isin(selected_stores)]
# filtered = filtered[filtered["status"].isin(selected_status)]
# if isinstance(chosen_dates, (tuple, list)) and len(chosen_dates) == 2:
#     start_date, end_date = chosen_dates
#     filtered = filtered[filtered["date"].dt.date.between(start_date, end_date)]

# flagged = filtered[filtered["status"].eq("REVIEW")].copy()
# completeness = build_completeness(report, int(expected_stores))
# latest_day = completeness.iloc[-1] if not completeness.empty else None
# latest_coverage = float(latest_day["coverage_pct"]) if latest_day is not None else np.nan

# # Top-level KPI ribbon
# kpis = st.columns(6)
# kpis[0].metric("Records analyzed", f"{len(filtered):,}")
# kpis[1].metric("Rows flagged", f"{len(flagged):,}", delta=f"{(len(flagged) / len(filtered) * 100):.1f}%" if len(filtered) else "0%", delta_color="inverse")
# kpis[2].metric("Sales quantity", f"{filtered['sales_qty'].sum(min_count=1):,.0f}" if filtered["sales_qty"].notna().any() else "—")
# kpis[3].metric("Revenue", fmt_inr(filtered["revenue_inr"].sum(min_count=1)))
# kpis[4].metric("Stock quantity", f"{filtered['stock_qty'].sum(min_count=1):,.0f}" if filtered["stock_qty"].notna().any() else "—")
# kpis[5].metric("Latest store coverage", f"{latest_coverage:.1f}%" if pd.notna(latest_coverage) else "—")

# st.markdown("---")
# tab_overview, tab_quality, tab_investigation, tab_benchmarks, tab_explorer, tab_email = st.tabs(
#     ["Overview", "Data completeness", "Anomaly investigation", "Trends & benchmarks", "Data explorer", "Gmail alerts"]
# )

# with tab_overview:
#     left, right = st.columns([1.35, 1])
#     with left:
#         st.subheader("Daily sales quantity")
#         if not filtered.empty and filtered["date"].notna().any():
#             daily = filtered.groupby("date", as_index=False).agg(
#                 sales_qty=("sales_qty", "sum"), revenue_inr=("revenue_inr", "sum"), stock_qty=("stock_qty", "sum")
#             )
#             fig = go.Figure()
#             fig.add_trace(go.Scatter(x=daily["date"], y=daily["sales_qty"], mode="lines+markers", name="Sales quantity"))
#             fig.update_layout(height=340, margin=dict(l=8, r=8, t=25, b=8), xaxis_title="Date", yaxis_title="Units sold")
#             st.plotly_chart(fig, use_container_width=True)
#         else:
#             st.info("No dated records match the selected filters.")
#     with right:
#         st.subheader("Data quality status")
#         status_counts = filtered["status"].value_counts().rename_axis("status").reset_index(name="rows")
#         if not status_counts.empty:
#             fig = px.pie(status_counts, names="status", values="rows", hole=0.58, color="status",
#                          color_discrete_map={"OK": "#18A999", "REVIEW": "#E76F51"})
#             fig.update_layout(height=340, margin=dict(l=8, r=8, t=25, b=8), showlegend=True)
#             st.plotly_chart(fig, use_container_width=True)
#         else:
#             st.info("No records match the selected filters.")

#     left, right = st.columns(2)
#     with left:
#         st.subheader("Most common anomaly types")
#         anomaly_types = flagged["anomaly_flags"].fillna("").str.split("; ").explode()
#         anomaly_types = anomaly_types[~anomaly_types.isin(["NONE", ""])]
#         type_counts = anomaly_types.value_counts().head(12).rename_axis("anomaly_type").reset_index(name="rows")
#         if not type_counts.empty:
#             st.plotly_chart(px.bar(type_counts, x="rows", y="anomaly_type", orientation="h"), use_container_width=True)
#         else:
#             st.success("No anomalies in the current selection.")
#     with right:
#         st.subheader("Stores with most flagged rows")
#         if not flagged.empty:
#             by_store = flagged.groupby("store_id").size().sort_values(ascending=False).head(10).reset_index(name="flagged_rows")
#             st.plotly_chart(px.bar(by_store, x="store_id", y="flagged_rows"), use_container_width=True)
#         else:
#             st.info("No flagged stores in the current selection.")

#     st.subheader("Monitoring workflow")
#     workflow = st.columns(5)
#     workflow_items = [
#         ("1 · Receive", "Client sales and stock files"),
#         ("2 · Validate", "Missing values and duplicate keys"),
#         ("3 · Compare", "Historical store-level patterns"),
#         ("4 · Flag", "Suspicious records for review"),
#         ("5 · Notify", "Gmail alert with report attachment"),
#     ]
#     for column, (heading, detail) in zip(workflow, workflow_items):
#         with column:
#             st.markdown(f"**{heading}**")
#             st.caption(detail)

# with tab_quality:
#     st.subheader("Daily data completeness")
#     st.write("Coverage checks compare received distinct stores with the expected store count. The dashboard also inserts calendar dates missing between the first and last date in the uploaded data.")
#     if not completeness.empty:
#         fig = px.bar(completeness, x="date", y="coverage_pct", color="status",
#                      hover_data=["records_received", "distinct_stores", "expected_stores"],
#                      color_discrete_map={"COMPLETE": "#18A999", "PARTIAL": "#F4A261", "MISSING DAY": "#E76F51"},
#                      labels={"date": "Date", "coverage_pct": "Store coverage (%)", "status": "Coverage status"})
#         fig.update_layout(yaxis_range=[0, max(105, float(completeness["coverage_pct"].max() or 0) + 5)])
#         st.plotly_chart(fig, use_container_width=True)
#         st.dataframe(completeness, use_container_width=True, hide_index=True)
#         issue_days = completeness[completeness["status"].ne("COMPLETE")]
#         if not issue_days.empty:
#             st.warning(f"{len(issue_days)} date(s) have partial or missing store coverage. Verify against the client's official delivery schedule.")
#         else:
#             st.success("All dates in the observed date range meet the configured store-count expectation.")
#     else:
#         st.info("Date and store identifiers are needed for daily completeness checks.")

#     st.subheader("Data validation checks")
#     if not flagged.empty:
#         flag_counts = flagged["anomaly_flags"].fillna("").str.split("; ").explode()
#         flag_counts = flag_counts[~flag_counts.isin(["NONE", ""])]
#         validation = flag_counts.value_counts().rename_axis("check").reset_index(name="flagged row count")
#         st.dataframe(validation, use_container_width=True, hide_index=True)
#     else:
#         st.success("No data quality exceptions are flagged in the current selection.")

# with tab_investigation:
#     st.subheader("Rows requiring investigation")
#     if flagged.empty:
#         st.success("No rows are flagged for review under the current filters.")
#     else:
#         visible_cols = [c for c in ["date", "store_id", "category", "sales_qty", "unit_price_inr", "revenue_inr", "stock_qty", "severity", "anomaly_flags", "source_file"] if c in flagged.columns]
#         st.dataframe(flagged[visible_cols].sort_values(["severity", "date"], ascending=[False, False]), use_container_width=True, hide_index=True)
#         st.download_button("Download flagged rows (CSV)", to_csv_bytes(flagged[visible_cols]), "flagged_rows.csv", "text/csv")
#         st.download_button("Download flagged report (Excel)", report_to_excel_bytes(flagged), "flagged_anomaly_report.xlsx",
#                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
#     st.caption("A flag means the record is suspicious and needs review; it does not prove the record is wrong.")

# with tab_benchmarks:
#     st.subheader("Store-level historical benchmarks")
#     numeric_metrics = [column for column in ["sales_qty", "revenue_inr", "stock_qty"] if column in filtered.columns]
#     if numeric_metrics and not filtered.empty:
#         metric = st.selectbox("Metric to inspect", numeric_metrics, key="benchmark_metric")
#         benchmark = filtered.groupby("store_id")[metric].agg(
#             record_count="count", median="median", mean="mean", std_dev="std", minimum="min", maximum="max"
#         ).reset_index()
#         st.dataframe(benchmark, use_container_width=True, hide_index=True)
#         daily = filtered.groupby("date", as_index=False)[metric].sum(min_count=1)
#         st.plotly_chart(px.line(daily, x="date", y=metric, markers=True, title=f"Daily total: {metric}"), use_container_width=True)
#     else:
#         st.info("No supported numeric metrics are available for these filters.")
#     st.info("The demo calculates MAD-based outlier checks from the supplied dataset. For production, build benchmarks from clean historical data and compare incoming data against that separate baseline.")

# with tab_explorer:
#     st.subheader("Data explorer")
#     st.write(f"Selected rows: **{len(filtered):,}** · Latest date in selection: **{filtered['date'].max().strftime('%d %b %Y') if not filtered.empty and filtered['date'].notna().any() else '—'}**")
#     st.dataframe(filtered, use_container_width=True, hide_index=True)
#     st.download_button("Download filtered data (CSV)", to_csv_bytes(filtered), "filtered_retail_data.csv", "text/csv")
#     st.download_button("Download full anomaly report (Excel)", report_to_excel_bytes(report), "anomaly_report.xlsx",
#                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# with tab_email:
#     st.subheader("Gmail alert configuration")
#     configured = gmail_is_configured()
#     if configured:
#         st.success(
#             f"Gmail variables are configured for sender {env_value('GMAIL_SENDER')} "
#             f"→ recipient {env_value('ALERT_RECIPIENT')}."
#         )
#     else:
#         env_file = BASE_DIR / ".env"
#         st.warning("Gmail credentials are not configured in this Streamlit process.")
#         if not env_file.exists():
#             st.error(f"No .env file was found beside app.py. Expected location: {env_file}")
#             st.markdown("In the VS Code terminal, run `Copy-Item .env.example .env`, then edit `.env` and replace every example value.")
#         else:
#             st.info(f".env file found at: {env_file}")
#             missing = missing_gmail_settings()
#             if missing:
#                 st.write("These settings are missing or still contain example placeholders:")
#                 for name in missing:
#                     st.code(name, language="text")
#             st.markdown("Save `.env`, fully stop Streamlit with Ctrl+C, and restart it with `streamlit run app.py`.")
#         st.caption("Use a Google App Password, not your normal Gmail password. Never print or share the App Password.")

#     st.write(f"Current filters contain **{len(flagged)}** rows flagged for review.")
#     confirm_email = st.checkbox("I have reviewed the flagged records and want to send an email alert", value=False)
#     if st.button("Send Gmail alert with anomaly report", type="primary", disabled=(not configured or not confirm_email or flagged.empty)):
#         with st.spinner("Sending Gmail alert…"):
#             try:
#                 # Email only the records matching the current filters; attach an Excel report.
#                 send_gmail_alert(flagged)
#                 st.success(f"Alert email sent to {env_value('ALERT_RECIPIENT')}.")
#             except Exception as exc:
#                 st.error(f"Email could not be sent: {exc}")
#     if flagged.empty:
#         st.info("No flagged rows match the current filters, so the alert button is disabled.")
#     st.caption("Opening or refreshing the dashboard does not send email. An alert is sent only after the explicit confirmation checkbox and button click.")

# st.markdown("---")
# st.caption("Demo data is synthetic. Configure official store lists, delivery calendars, thresholds, access controls, and approved secrets handling before production use.")




































"""Streamlit dashboard for retail sales and stock anomaly monitoring.

Start with: streamlit run app.py
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from anomaly_detection import (
    detect_anomalies,
    report_to_excel_bytes,
    send_gmail_alert,
)

st.set_page_config(
    page_title="Retail Anomaly Monitor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

# Fixed dataset: no file upload is required.
DEFAULT_DATA = BASE_DIR / "retail_sales_stock_1000.csv"

REQUIRED = [
    "date",
    "store_id",
    "sales_qty",
    "revenue_inr",
    "stock_qty",
]


def load_fixed_dataset() -> pd.DataFrame:
    """Load the predefined dataset."""
    if not DEFAULT_DATA.exists():
        return pd.DataFrame()

    data = pd.read_csv(DEFAULT_DATA)

    missing = [
        column for column in REQUIRED
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            "Missing required column(s): "
            + ", ".join(missing)
        )

    data = data.copy()
    data["date"] = pd.to_datetime(
        data["date"], errors="coerce"
    )

    for column in [
        "sales_qty",
        "revenue_inr",
        "stock_qty",
        "unit_price_inr",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(
                data[column], errors="coerce"
            )

    return data


def build_completeness(
    data: pd.DataFrame,
    expected_stores: int,
) -> pd.DataFrame:
    """Calculate daily store coverage."""
    valid = data.dropna(
        subset=["date", "store_id"]
    ).copy()

    columns = [
        "date",
        "records_received",
        "distinct_stores",
        "expected_stores",
        "coverage_pct",
        "status",
    ]

    if valid.empty:
        return pd.DataFrame(columns=columns)

    valid["date"] = (
        pd.to_datetime(valid["date"]).dt.normalize()
    )

    counts = valid.groupby("date").agg(
        records_received=("store_id", "size"),
        distinct_stores=("store_id", "nunique"),
    )

    calendar = pd.date_range(
        valid["date"].min(),
        valid["date"].max(),
        freq="D",
    )

    counts = counts.reindex(calendar, fill_value=0)
    counts.index.name = "date"
    result = counts.reset_index()

    result["expected_stores"] = int(expected_stores)
    result["coverage_pct"] = (
        result["distinct_stores"]
        / max(1, expected_stores)
        * 100
    ).round(1)

    result["status"] = np.select(
        [
            result["distinct_stores"].eq(0),
            result["distinct_stores"].lt(expected_stores),
        ],
        ["MISSING DAY", "PARTIAL"],
        default="COMPLETE",
    )

    return result


def fmt_inr(value: float | int) -> str:
    if pd.isna(value):
        return "—"
    return f"₹{value:,.0f}"


def to_csv_bytes(data: pd.DataFrame) -> bytes:
    return data.to_csv(index=False).encode("utf-8-sig")


def env_value(name: str) -> str:
    value = os.getenv(name, "").strip()

    try:
        if not value and name in st.secrets:
            value = str(st.secrets[name]).strip()
    except Exception:
        pass

    return value


def missing_gmail_settings() -> list[str]:
    required = [
        "GMAIL_SENDER",
        "GMAIL_APP_PASSWORD",
        "ALERT_RECIPIENT",
    ]

    return [
        name
        for name in required
        if (
            not env_value(name)
            or env_value(name).startswith("your_")
            or "example.com" in env_value(name)
        )
    ]


def gmail_is_configured() -> bool:
    return len(missing_gmail_settings()) == 0


def primary_anomaly_category(flags: object) -> str:
    """Convert detector flags into a readable category."""
    text = "" if pd.isna(flags) else str(flags)

    if not text or text == "NONE":
        return "Normal"

    items = set(text.split("; "))

    if (
        "INVALID_DATE" in items
        or any(x.startswith("MISSING_") for x in items)
    ):
        return "Missing / Invalid Data"

    if any(x.startswith("DUPLICATE_") for x in items):
        return "Duplicate Data"

    if any(x.startswith("NEGATIVE_") for x in items):
        return "Invalid Numeric Value"

    if "REVENUE_MISMATCH" in items:
        return "Revenue Inconsistency"

    if any(x.endswith("_OUTLIER") for x in items):
        return "Statistical Outlier"

    return "Other Review"


def category_explanation(category: str) -> str:
    explanations = {
        "Normal":
            "No configured anomaly rule was triggered.",
        "Missing / Invalid Data":
            "A required field is missing or the date is invalid.",
        "Duplicate Data":
            "The same store and date appear more than once.",
        "Invalid Numeric Value":
            "A negative numeric value needs investigation.",
        "Revenue Inconsistency":
            "Revenue differs from sales quantity multiplied by unit price.",
        "Statistical Outlier":
            "Sales, revenue, or stock is unusual compared with the store's pattern.",
        "Other Review":
            "Inspect the detailed anomaly flags.",
    }

    return explanations.get(category, "Inspect the record.")


# --------------------------------------------------
# Dashboard header and fixed dataset loading
# --------------------------------------------------

st.title("🛡️ Retail Sales & Stock Anomaly Monitor")
st.caption(
    "Data validation → anomaly detection → investigation → Gmail alert"
)

# The sidebar no longer contains upload or expected-store inputs.
with st.sidebar:
    st.header("Data & filters")
    st.caption("Using the predefined 1,000-record dataset.")

try:
    raw = load_fixed_dataset()
except Exception as exc:
    st.error(f"Could not load the dataset: {exc}")
    st.stop()

if raw.empty:
    st.warning(
        "Dataset not found. Place "
        "'retail_sales_stock_1000.csv' beside app.py."
    )
    st.stop()

try:
    report = detect_anomalies(raw)
    report["anomaly_category"] = (
        report["anomaly_flags"].apply(
            primary_anomaly_category
        )
    )
except Exception as exc:
    st.error(f"Anomaly detection failed: {exc}")
    st.stop()


# Automatically determine the expected number of stores.
expected_stores = max(
    1,
    int(raw["store_id"].dropna().astype(str).nunique()),
)


# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------

with st.sidebar:
    st.markdown("---")

    store_options = sorted(
        report["store_id"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected_stores = st.multiselect(
        "Stores",
        options=store_options,
        default=store_options,
    )

    status_options = ["OK", "REVIEW"]

    selected_status = st.multiselect(
        "Record status",
        options=status_options,
        default=status_options,
    )

    if report["date"].notna().any():
        min_day = report["date"].min().date()
        max_day = report["date"].max().date()

        chosen_dates = st.date_input(
            "Date range",
            value=(min_day, max_day),
            min_value=min_day,
            max_value=max_day,
        )
    else:
        chosen_dates = None

    st.markdown("---")
    st.subheader("Gmail setup")

    configured = gmail_is_configured()

    if configured:
        st.success("Credentials detected")
    else:
        st.warning("Credentials not configured")

    st.caption(
        "Email is sent only after you explicitly click "
        "the send button in the Gmail Alerts tab."
    )


# --------------------------------------------------
# Apply filters
# --------------------------------------------------

filtered = report.copy()

filtered = filtered[
    filtered["store_id"].astype(str).isin(selected_stores)
]

filtered = filtered[
    filtered["status"].isin(selected_status)
]

if (
    isinstance(chosen_dates, (tuple, list))
    and len(chosen_dates) == 2
):
    start_date, end_date = chosen_dates

    filtered = filtered[
        filtered["date"].dt.date.between(
            start_date, end_date
        )
    ]

flagged = filtered[
    filtered["status"].eq("REVIEW")
].copy()

completeness = build_completeness(
    report,
    expected_stores,
)

latest_day = (
    completeness.iloc[-1]
    if not completeness.empty
    else None
)

latest_coverage = (
    float(latest_day["coverage_pct"])
    if latest_day is not None
    else np.nan
)


# --------------------------------------------------
# KPI cards
# --------------------------------------------------

kpis = st.columns(6)

kpis[0].metric(
    "Records analyzed",
    f"{len(filtered):,}",
)

kpis[1].metric(
    "Rows flagged",
    f"{len(flagged):,}",
    delta=(
        f"{len(flagged) / len(filtered) * 100:.1f}%"
        if len(filtered)
        else "0%"
    ),
    delta_color="inverse",
)

kpis[2].metric(
    "Sales quantity",
    (
        f"{filtered['sales_qty'].sum(min_count=1):,.0f}"
        if filtered["sales_qty"].notna().any()
        else "—"
    ),
)

kpis[3].metric(
    "Revenue",
    fmt_inr(filtered["revenue_inr"].sum(min_count=1)),
)

kpis[4].metric(
    "Stock quantity",
    (
        f"{filtered['stock_qty'].sum(min_count=1):,.0f}"
        if filtered["stock_qty"].notna().any()
        else "—"
    ),
)

kpis[5].metric(
    "Latest store coverage",
    (
        f"{latest_coverage:.1f}%"
        if pd.notna(latest_coverage)
        else "—"
    ),
)

st.markdown("---")


# --------------------------------------------------
# Dashboard tabs
# --------------------------------------------------

(
    tab_overview,
    tab_quality,
    tab_investigation,
    tab_categorization,
    tab_benchmarks,
    tab_explorer,
    tab_email,
) = st.tabs([
    "Overview",
    "Data completeness",
    "Anomaly investigation",
    "How anomalies are categorized",
    "Trends & benchmarks",
    "Data explorer",
    "Gmail alerts",
])


# --------------------------------------------------
# Overview tab
# --------------------------------------------------

with tab_overview:
    left, right = st.columns([1.35, 1])

    with left:
        st.subheader("Daily sales quantity")

        if (
            not filtered.empty
            and filtered["date"].notna().any()
        ):
            daily = filtered.groupby(
                "date", as_index=False
            ).agg(
                sales_qty=("sales_qty", "sum"),
                revenue_inr=("revenue_inr", "sum"),
                stock_qty=("stock_qty", "sum"),
            )

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=daily["date"],
                    y=daily["sales_qty"],
                    mode="lines+markers",
                    name="Sales quantity",
                )
            )

            fig.update_layout(
                height=340,
                margin=dict(l=8, r=8, t=25, b=8),
                xaxis_title="Date",
                yaxis_title="Units sold",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )
        else:
            st.info("No dated records match the selected filters.")

    with right:
        st.subheader("Data quality status")

        status_counts = (
            filtered["status"]
            .value_counts()
            .rename_axis("status")
            .reset_index(name="rows")
        )

        if not status_counts.empty:
            fig = px.pie(
                status_counts,
                names="status",
                values="rows",
                hole=0.58,
                color="status",
                color_discrete_map={
                    "OK": "#18A999",
                    "REVIEW": "#E76F51",
                },
            )

            fig.update_layout(
                height=340,
                margin=dict(l=8, r=8, t=25, b=8),
                showlegend=True,
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )
        else:
            st.info("No records match the selected filters.")

    left, right = st.columns(2)

    with left:
        st.subheader("Most common anomaly types")

        anomaly_types = (
            flagged["anomaly_flags"]
            .fillna("")
            .str.split("; ")
            .explode()
        )

        anomaly_types = anomaly_types[
            ~anomaly_types.isin(["NONE", ""])
        ]

        type_counts = (
            anomaly_types.value_counts()
            .head(12)
            .rename_axis("anomaly_type")
            .reset_index(name="rows")
        )

        if not type_counts.empty:
            st.plotly_chart(
                px.bar(
                    type_counts,
                    x="rows",
                    y="anomaly_type",
                    orientation="h",
                ),
                use_container_width=True,
            )
        else:
            st.success("No anomalies in the current selection.")

    with right:
        st.subheader("Stores with most flagged rows")

        if not flagged.empty:
            by_store = (
                flagged.groupby("store_id")
                .size()
                .sort_values(ascending=False)
                .head(10)
                .reset_index(name="flagged_rows")
            )

            st.plotly_chart(
                px.bar(
                    by_store,
                    x="store_id",
                    y="flagged_rows",
                ),
                use_container_width=True,
            )
        else:
            st.info("No flagged stores in the current selection.")

    st.subheader("Monitoring workflow")

    workflow = st.columns(5)

    workflow_items = [
        ("1 · Load", "Predefined retail dataset"),
        ("2 · Validate", "Check missing values and duplicates"),
        ("3 · Compare", "Compare store-level patterns"),
        ("4 · Flag", "Identify suspicious records"),
        ("5 · Notify", "Send an approved Gmail alert"),
    ]

    for column, (heading, detail) in zip(
        workflow, workflow_items
    ):
        with column:
            st.markdown(f"**{heading}**")
            st.caption(detail)


# --------------------------------------------------
# Data completeness tab
# --------------------------------------------------

with tab_quality:
    st.subheader("Daily data completeness")

    st.write(
        "Coverage compares the number of distinct stores "
        "observed each day with the number of stores in the "
        "predefined dataset. Missing calendar dates between "
        "the first and last date are also included."
    )

    if not completeness.empty:
        fig = px.bar(
            completeness,
            x="date",
            y="coverage_pct",
            color="status",
            hover_data=[
                "records_received",
                "distinct_stores",
                "expected_stores",
            ],
            color_discrete_map={
                "COMPLETE": "#18A999",
                "PARTIAL": "#F4A261",
                "MISSING DAY": "#E76F51",
            },
            labels={
                "date": "Date",
                "coverage_pct": "Store coverage (%)",
                "status": "Coverage status",
            },
        )

        fig.update_layout(
            yaxis_range=[
                0,
                max(
                    105,
                    float(
                        completeness["coverage_pct"].max() or 0
                    ) + 5,
                ),
            ]
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        st.dataframe(
            completeness,
            use_container_width=True,
            hide_index=True,
        )

        issue_days = completeness[
            completeness["status"].ne("COMPLETE")
        ]

        if not issue_days.empty:
            st.warning(
                f"{len(issue_days)} date(s) have partial or "
                "missing store coverage. Verify the expected "
                "schedule before treating this as an issue."
            )
        else:
            st.success(
                "All dates meet the observed store-count expectation."
            )
    else:
        st.info(
            "Date and store identifiers are needed for "
            "daily completeness checks."
        )

    st.subheader("Data validation checks")

    if not flagged.empty:
        flag_counts = (
            flagged["anomaly_flags"]
            .fillna("")
            .str.split("; ")
            .explode()
        )

        flag_counts = flag_counts[
            ~flag_counts.isin(["NONE", ""])
        ]

        validation = (
            flag_counts.value_counts()
            .rename_axis("check")
            .reset_index(name="flagged row count")
        )

        st.dataframe(
            validation,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success(
            "No data quality exceptions are flagged in this selection."
        )


# --------------------------------------------------
# Anomaly investigation tab
# --------------------------------------------------

with tab_investigation:
    st.subheader("Rows requiring investigation")

    if flagged.empty:
        st.success(
            "No rows are flagged for review under the current filters."
        )
    else:
        visible_cols = [
            column
            for column in [
                "date",
                "store_id",
                "category",
                "sales_qty",
                "unit_price_inr",
                "revenue_inr",
                "stock_qty",
                "severity",
                "anomaly_flags",
                "source_file",
            ]
            if column in flagged.columns
        ]

        st.dataframe(
            flagged[visible_cols].sort_values(
                ["severity", "date"],
                ascending=[False, False],
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download flagged rows (CSV)",
            to_csv_bytes(flagged[visible_cols]),
            "flagged_rows.csv",
            "text/csv",
        )

        st.download_button(
            "Download flagged report (Excel)",
            report_to_excel_bytes(flagged),
            "flagged_anomaly_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.caption(
        "A flag means the record needs review; it does not prove "
        "the record is wrong."
    )


# --------------------------------------------------
# Anomaly categorization tab
# --------------------------------------------------

with tab_categorization:
    st.subheader("How this dashboard categorizes anomalies")

    st.write(
        "This page explains the detector rules and shows how "
        "records in the fixed dataset were categorized. The "
        "category is a readable summary; detailed anomaly flags "
        "are retained."
    )

    st.info(
        "A flag means investigate the record, not confirmed error. "
        "When multiple flags exist, the dashboard assigns one "
        "primary category while retaining all detailed flags."
    )

    category_counts = (
        filtered["anomaly_category"]
        .value_counts()
        .rename_axis("Primary category")
        .reset_index(name="Rows")
        .sort_values("Rows", ascending=False)
    )

    left, right = st.columns([1, 1.15])

    with left:
        st.markdown("**Categorization of selected records**")

        if not category_counts.empty:
            st.dataframe(
                category_counts,
                use_container_width=True,
                hide_index=True,
            )

            fig = px.bar(
                category_counts,
                x="Primary category",
                y="Rows",
                color="Primary category",
            )

            fig.update_layout(
                showlegend=False,
                xaxis_tickangle=-25,
                margin=dict(t=20, b=80),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    with right:
        st.markdown("**Rules used by the detector**")

        rule_rows = [
            (
                "Missing / Invalid Data",
                "INVALID_DATE or MISSING_*",
                "Required fields are missing or the date is invalid.",
            ),
            (
                "Duplicate Data",
                "DUPLICATE_STORE_DATE",
                "Repeated store-date key; valid only if one row per store per day is expected.",
            ),
            (
                "Invalid Numeric Value",
                "NEGATIVE_*",
                "A negative sales, price, revenue, or stock value needs checking.",
            ),
            (
                "Revenue Inconsistency",
                "REVENUE_MISMATCH",
                "Revenue differs from quantity × unit price beyond the configured tolerance.",
            ),
            (
                "Statistical Outlier",
                "SALES_OUTLIER / REVENUE_OUTLIER / STOCK_OUTLIER",
                "A value differs substantially from the store's usual pattern.",
            ),
            (
                "Normal",
                "No flag (NONE)",
                "No configured row-level rule was triggered.",
            ),
        ]

        st.dataframe(
            pd.DataFrame(
                rule_rows,
                columns=[
                    "Primary category",
                    "Trigger",
                    "Meaning",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("**Primary category priority**")

    st.caption(
        "Missing / Invalid Data → Duplicate Data → "
        "Invalid Numeric Value → Revenue Inconsistency → "
        "Statistical Outlier → Normal. This priority only "
        "determines the displayed category; all flags are retained."
    )

    st.markdown("---")
    st.markdown("**Investigate a specific record**")

    candidates = report[
        report["status"].eq("REVIEW")
    ].copy()

    if candidates.empty:
        st.success("No records are flagged in the dataset.")
    else:
        candidates["_row_label"] = candidates.apply(
            lambda row: (
                f"Row {row.name + 1} · "
                f"Store {row.get('store_id', '—')} · "
                f"{str(row.get('date', '—'))[:10]} · "
                f"{row['anomaly_category']}"
            ),
            axis=1,
        )

        selected_label = st.selectbox(
            "Choose a flagged row",
            candidates["_row_label"].tolist(),
            key="categorization_example_row",
        )

        chosen = candidates.loc[
            candidates["_row_label"].eq(selected_label)
        ].iloc[0]

        st.markdown(
            f"**Primary category:** `{chosen['anomaly_category']}`"
        )

        st.write(
            category_explanation(chosen["anomaly_category"])
        )

        st.markdown(
            f"**Detailed flags:** `{chosen['anomaly_flags']}`"
        )

        metric_cols = st.columns(4)

        if "sales_qty" in chosen.index:
            metric_cols[0].metric(
                "Sales quantity",
                (
                    "—"
                    if pd.isna(chosen["sales_qty"])
                    else f"{chosen['sales_qty']:,.2f}"
                ),
            )

        if "unit_price_inr" in chosen.index:
            metric_cols[1].metric(
                "Unit price",
                fmt_inr(chosen["unit_price_inr"]),
            )

        if "revenue_inr" in chosen.index:
            metric_cols[2].metric(
                "Revenue",
                fmt_inr(chosen["revenue_inr"]),
            )

        if "stock_qty" in chosen.index:
            metric_cols[3].metric(
                "Stock quantity",
                (
                    "—"
                    if pd.isna(chosen["stock_qty"])
                    else f"{chosen['stock_qty']:,.2f}"
                ),
            )

        if all(
            column in chosen.index
            for column in [
                "sales_qty",
                "unit_price_inr",
                "revenue_inr",
            ]
        ):
            if all(
                pd.notna(chosen[column])
                for column in [
                    "sales_qty",
                    "unit_price_inr",
                    "revenue_inr",
                ]
            ):
                expected_revenue = (
                    float(chosen["sales_qty"])
                    * float(chosen["unit_price_inr"])
                )

                st.write(
                    f"Expected revenue: "
                    f"{chosen['sales_qty']:,.2f} × "
                    f"{fmt_inr(chosen['unit_price_inr'])} = "
                    f"{fmt_inr(expected_revenue)}. "
                    f"Recorded revenue: "
                    f"{fmt_inr(chosen['revenue_inr'])}."
                )

        show_cols = [
            column
            for column in [
                "date",
                "store_id",
                "category",
                "sales_qty",
                "unit_price_inr",
                "revenue_inr",
                "stock_qty",
                "severity",
                "anomaly_category",
                "anomaly_flags",
            ]
            if column in chosen.index
        ]

        st.dataframe(
            pd.DataFrame([chosen[show_cols]]),
            use_container_width=True,
            hide_index=True,
        )


# --------------------------------------------------
# Trends and benchmarks tab
# --------------------------------------------------

with tab_benchmarks:
    st.subheader("Store-level historical benchmarks")

    numeric_metrics = [
        column
        for column in [
            "sales_qty",
            "revenue_inr",
            "stock_qty",
        ]
        if column in filtered.columns
    ]

    if numeric_metrics and not filtered.empty:
        metric = st.selectbox(
            "Metric to inspect",
            numeric_metrics,
            key="benchmark_metric",
        )

        benchmark = filtered.groupby("store_id")[metric].agg(
            record_count="count",
            median="median",
            mean="mean",
            std_dev="std",
            minimum="min",
            maximum="max",
        ).reset_index()

        st.dataframe(
            benchmark,
            use_container_width=True,
            hide_index=True,
        )

        daily = filtered.groupby(
            "date", as_index=False
        )[metric].sum(min_count=1)

        st.plotly_chart(
            px.line(
                daily,
                x="date",
                y=metric,
                markers=True,
                title=f"Daily total: {metric}",
            ),
            use_container_width=True,
        )
    else:
        st.info(
            "No supported numeric metrics are available for these filters."
        )

    st.info(
        "This demo calculates outlier checks from the supplied dataset. "
        "For production, compare incoming data against a separate "
        "clean historical baseline."
    )


# --------------------------------------------------
# Data explorer tab
# --------------------------------------------------

with tab_explorer:
    st.subheader("Data explorer")

    latest_date = (
        filtered["date"].max().strftime("%d %b %Y")
        if (
            not filtered.empty
            and filtered["date"].notna().any()
        )
        else "—"
    )

    st.write(
        f"Selected rows: **{len(filtered):,}** · "
        f"Latest date in selection: **{latest_date}**"
    )

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download filtered data (CSV)",
        to_csv_bytes(filtered),
        "filtered_retail_data.csv",
        "text/csv",
    )

    st.download_button(
        "Download full anomaly report (Excel)",
        report_to_excel_bytes(report),
        "anomaly_report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# --------------------------------------------------
# Gmail alerts tab
# --------------------------------------------------

with tab_email:
    st.subheader("Gmail alert configuration")

    configured = gmail_is_configured()

    if configured:
        st.success(
            f"Gmail variables are configured for sender "
            f"{env_value('GMAIL_SENDER')} → recipient "
            f"{env_value('ALERT_RECIPIENT')}."
        )
    else:
        env_file = BASE_DIR / ".env"

        st.warning(
            "Gmail credentials are not configured in this process."
        )

        if not env_file.exists():
            st.error(
                f"No .env file was found beside app.py. "
                f"Expected location: {env_file}"
            )

            st.markdown(
                "Create `.env` from `.env.example`, then replace "
                "the example values with your own settings."
            )
        else:
            st.info(f".env file found at: {env_file}")

            missing = missing_gmail_settings()

            if missing:
                st.write(
                    "These settings are missing or still use placeholders:"
                )

                for name in missing:
                    st.code(name, language="text")

            st.markdown(
                "Save `.env`, stop Streamlit with Ctrl+C, "
                "and restart it with `streamlit run app.py`."
            )

        st.caption(
            "Use a Google App Password, not your normal Gmail password. "
            "Never print or share the App Password."
        )

    st.write(
        f"Current filters contain **{len(flagged)}** "
        "rows flagged for review."
    )

    confirm_email = st.checkbox(
        "I have reviewed the flagged records and want to send an email alert",
        value=False,
    )

    if st.button(
        "Send Gmail alert with anomaly report",
        type="primary",
        disabled=(
            not configured
            or not confirm_email
            or flagged.empty
        ),
    ):
        with st.spinner("Sending Gmail alert…"):
            try:
                send_gmail_alert(flagged)

                st.success(
                    f"Alert email sent to "
                    f"{env_value('ALERT_RECIPIENT')}."
                )
            except Exception as exc:
                st.error(f"Email could not be sent: {exc}")

    if flagged.empty:
        st.info(
            "No flagged rows match the current filters, "
            "so the alert button is disabled."
        )

    st.caption(
        "Refreshing the dashboard does not send email. "
        "An alert is sent only after confirmation and a button click."
    )


st.markdown("---")
st.caption(
    "Demo data is synthetic. Before production use, verify store lists, "
    "delivery calendars, detection thresholds, access controls, "
    "and secrets handling."
)
