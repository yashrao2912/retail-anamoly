"""Basic smoke tests for the bundled synthetic dataset and anomaly detector."""
from pathlib import Path

import pandas as pd

from anomaly_detection import detect_anomalies, load_data

BASE_DIR = Path(__file__).resolve().parent


def test_demo_dataset_shape_and_injected_issues():
    data = load_data(BASE_DIR / "retail_sales_stock_1000.csv")
    report = detect_anomalies(data)

    assert len(data) == 1000, f"Expected 1,000 rows, got {len(data)}"
    assert data["store_id"].nunique() == 25
    assert data["date"].nunique() == 40
    assert (report["status"] == "REVIEW").any(), "Expected injected anomalies to be flagged"

    flags = set(
        flag
        for value in report["anomaly_flags"].astype(str)
        for flag in value.split("; ")
        if flag and flag != "NONE"
    )
    expected_flags = {
        "DUPLICATE_STORE_DATE",
        "MISSING_SALES_QTY",
        "MISSING_STOCK",
        "NEGATIVE_STOCK",
        "REVENUE_MISMATCH",
        "SALES_OUTLIER",
    }
    missing = expected_flags - flags
    assert not missing, f"Expected demo flags missing: {sorted(missing)}"


def test_detector_accepts_minimum_columns_without_unit_price():
    data = pd.DataFrame({
        "date": ["2026-01-01", "2026-01-02"],
        "store_id": ["A", "A"],
        "sales_qty": [10, 11],
        "revenue_inr": [100, 110],
        "stock_qty": [30, 19],
    })
    report = detect_anomalies(data)
    assert len(report) == 2
    assert {"status", "severity", "anomaly_flags"}.issubset(report.columns)


if __name__ == "__main__":
    test_demo_dataset_shape_and_injected_issues()
    test_detector_accepts_minimum_columns_without_unit_price()
    print("All anomaly detection smoke tests passed.")
