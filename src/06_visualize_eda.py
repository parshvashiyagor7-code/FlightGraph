
from pathlib import Path
import csv

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)


def load_csv(filename):
    path = REPORTS / filename

    with open(path, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def number(value):
    return float(value) if value not in (None, "") else None


def main():
    summary = load_csv("eda_summary.csv")[0]
    monthly = load_csv("monthly_delay.csv")
    airlines = load_csv("airline_delay.csv")

    # Chart 1: Overall delayed vs non-delayed flights
    valid = int(summary["valid_labels"])
    delayed = int(summary["delayed_15min_or_more"])
    not_delayed = valid - delayed

    plt.figure(figsize=(7, 5))
    plt.bar(
        ["Delayed 15+ min", "Not delayed 15+ min"],
        [delayed / valid * 100, not_delayed / valid * 100],
    )
    plt.ylabel("Percentage of flights (%)")
    plt.title("FlightGraph: Overall Arrival Delay Distribution")
    plt.ylim(0, 100)

    for i, value in enumerate(
        [delayed / valid * 100, not_delayed / valid * 100]
    ):
        plt.text(i, value + 1, f"{value:.2f}%", ha="center")

    plt.tight_layout()
    plt.savefig(FIGURES / "overall_delay_distribution.png", dpi=160)
    plt.close()

    # Chart 2: Monthly delay trend
    monthly = sorted(
        monthly,
        key=lambda row: (int(row["Year"]), int(row["Month"])),
    )

    monthly = [
        row for row in monthly
        if number(row["delayed_15min_or_more_pct"]) is not None
    ]

    labels = [
        f'{int(row["Year"])}-{int(row["Month"]):02d}'
        for row in monthly
    ]
    percentages = [
        number(row["delayed_15min_or_more_pct"])
        for row in monthly
    ]

    plt.figure(figsize=(12, 5))
    plt.plot(labels, percentages, marker="o")
    plt.xlabel("Year-Month")
    plt.ylabel("Flights delayed 15+ min (%)")
    plt.title("FlightGraph: Monthly Arrival Delay Trend")
    plt.xticks(rotation=45, ha="right")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "monthly_delay_trend.png", dpi=160)
    plt.close()

    # Chart 3: Airline comparison, excluding small samples
    airline_rows = [
        row for row in airlines
        if int(row["flight_records"]) >= 100_000
        and number(row["delayed_15min_or_more_pct"]) is not None
    ]

    airline_rows.sort(
        key=lambda row: number(row["delayed_15min_or_more_pct"]),
        reverse=True,
    )
    top = airline_rows[:10][::-1]

    plt.figure(figsize=(9, 6))
    plt.barh(
        [row["Reporting_Airline"] for row in top],
        [number(row["delayed_15min_or_more_pct"]) for row in top],
    )
    plt.xlabel("Flights delayed 15+ min (%)")
    plt.title("Airline Delay Comparison (Minimum 100,000 Records)")
    plt.tight_layout()
    plt.savefig(FIGURES / "airline_delay_comparison.png", dpi=160)
    plt.close()

    print("All charts generated successfully.")
    print(f"Charts saved in: {FIGURES}")
    for file in sorted(FIGURES.glob("*.png")):
        print(file.name)


if __name__ == "__main__":
    main()
