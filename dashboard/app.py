from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

st.set_page_config(
    page_title="FlightGraph | Flight Analytics",
    page_icon="✈️",
    layout="wide",
)


@st.cache_data
def load_csv(filename: str) -> pd.DataFrame:
    path = REPORTS / filename
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")
    return pd.read_csv(path)


def format_number(value) -> str:
    return f"{int(value):,}"


def make_report_zip(report_tables: dict[str, pd.DataFrame], notes: str) -> bytes:
    """Package the current dashboard tables as a portable ZIP of CSV files."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, dataframe in report_tables.items():
            archive.writestr(
                filename,
                dataframe.to_csv(index=False).encode("utf-8-sig"),
            )
        archive.writestr("README.txt", notes.encode("utf-8"))
    return buffer.getvalue()


def main():
    st.title("✈️ FlightGraph")
    st.subheader("Large-Scale Flight Delay Analytics")
    st.caption(
        "Powered by PySpark, Parquet and Streamlit | "
        "Exploratory analysis of flight-delay patterns"
    )

    try:
        summary = load_csv("eda_summary.csv")
        monthly = load_csv("monthly_delay.csv")
        airlines = load_csv("airline_delay.csv")
    except Exception as exc:
        st.error(f"Could not load EDA reports: {exc}")
        st.info("Run the existing EDA script first: python src/05_eda.py")
        st.stop()

    if summary.empty:
        st.error("The overall EDA report contains no data.")
        st.stop()

    overall = summary.iloc[0]
    required_monthly = {"Year", "Month", "delayed_15min_or_more_pct"}
    required_airline = {
        "Reporting_Airline", "flight_records", "delayed_15min_or_more_pct"
    }
    if not required_monthly.issubset(monthly.columns):
        st.error("Monthly report has unexpected columns.")
        st.stop()
    if not required_airline.issubset(airlines.columns):
        st.error("Airline report has unexpected columns.")
        st.stop()

    total_flights = int(overall["flight_records"])
    valid_labels = int(overall["valid_labels"])
    delayed_flights = int(overall["delayed_15min_or_more"])
    delay_pct = float(overall["delayed_15min_or_more_pct"])

    st.markdown("### Overall Flight Statistics")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Flight Records", format_number(total_flights))
    k2.metric("Valid Delay Labels", format_number(valid_labels))
    k3.metric("Flights Delayed 15+ Min", format_number(delayed_flights))
    k4.metric("15+ Min Delay Rate", f"{delay_pct:.2f}%")
    st.caption("These figures come from the training dataset's EDA summary.")

    # Prepare monthly data and filters.
    monthly_chart = monthly.copy()
    for column in ["Year", "Month", "delayed_15min_or_more_pct"]:
        monthly_chart[column] = pd.to_numeric(monthly_chart[column], errors="coerce")
    monthly_chart = monthly_chart.dropna(
        subset=["Year", "Month", "delayed_15min_or_more_pct"]
    )
    monthly_chart["Year"] = monthly_chart["Year"].astype(int)
    monthly_chart["Month"] = monthly_chart["Month"].astype(int)
    monthly_chart = monthly_chart[monthly_chart["Month"].between(1, 12)]
    monthly_chart = monthly_chart.sort_values(["Year", "Month"])

    st.sidebar.header("Dashboard Filters")
    st.sidebar.caption("Filters update the corresponding charts and report tables.")
    min_records = st.sidebar.number_input(
        "Minimum flight records per airline",
        min_value=1,
        max_value=10_000_000,
        value=100_000,
        step=100_000,
    )
    top_n = st.sidebar.slider(
        "Number of airlines to display", min_value=5, max_value=20, value=10
    )

    available_years = sorted(monthly_chart["Year"].unique().tolist())
    year_options = ["All years"] + available_years
    selected_year = st.sidebar.selectbox("Year for monthly trend", year_options)
    month_options = ["All months"] + list(MONTH_NAMES.values())
    selected_month = st.sidebar.selectbox("Month for monthly trend", month_options)

    filtered_monthly = monthly_chart.copy()
    if selected_year != "All years":
        filtered_monthly = filtered_monthly[filtered_monthly["Year"] == selected_year]
    if selected_month != "All months":
        selected_month_number = next(
            month for month, name in MONTH_NAMES.items() if name == selected_month
        )
        filtered_monthly = filtered_monthly[
            filtered_monthly["Month"] == selected_month_number
        ]

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("### Arrival Delay Distribution")
        distribution = pd.DataFrame(
            {"Percentage": [delay_pct, 100.0 - delay_pct]},
            index=[
                "Arrival delay 15+ minutes",
                "Below 15-minute delay threshold",
            ],
        )
        st.bar_chart(distribution, y="Percentage")
        st.caption(
            "Below threshold includes early arrivals and flights delayed "
            "by less than 15 minutes."
        )

    with right:
        st.markdown("### Monthly Delay Trend")
        if filtered_monthly.empty:
            st.warning("No monthly records match the selected year/month filters.")
        else:
            filtered_monthly["Year-Month"] = (
                filtered_monthly["Year"].astype(str)
                + "-"
                + filtered_monthly["Month"].astype(str).str.zfill(2)
            )
            chart_data = filtered_monthly.set_index("Year-Month")[
                ["delayed_15min_or_more_pct"]
            ].rename(columns={"delayed_15min_or_more_pct": "Delayed flights (%)"})
            st.line_chart(chart_data)
        st.caption("Use the Year and Month filters in the sidebar to focus this trend.")

    st.divider()
    st.markdown("### Airline Performance Comparison")
    airline_chart = airlines.copy()
    airline_chart["flight_records"] = pd.to_numeric(
        airline_chart["flight_records"], errors="coerce"
    )
    airline_chart["delayed_15min_or_more_pct"] = pd.to_numeric(
        airline_chart["delayed_15min_or_more_pct"], errors="coerce"
    )
    airline_chart = airline_chart.dropna(
        subset=["flight_records", "delayed_15min_or_more_pct"]
    )
    airline_chart = airline_chart[airline_chart["flight_records"] >= min_records]
    airline_chart = airline_chart.sort_values(
        "delayed_15min_or_more_pct", ascending=False
    )

    if airline_chart.empty:
        st.warning("No airlines match this minimum record count. Lower the filter value.")
        displayed_airlines = airline_chart
        airline_table = pd.DataFrame(
            columns=["Airline", "Flight records", "15+ min delay (%)"]
        )
    else:
        displayed_airlines = airline_chart.head(top_n)
        st.bar_chart(
            displayed_airlines.set_index("Reporting_Airline")[
                ["delayed_15min_or_more_pct"]
            ].rename(columns={"delayed_15min_or_more_pct": "Delayed flights (%)"})
        )
        airline_table = displayed_airlines[
            ["Reporting_Airline", "flight_records", "delayed_15min_or_more_pct"]
        ].rename(
            columns={
                "Reporting_Airline": "Airline",
                "flight_records": "Flight records",
                "delayed_15min_or_more_pct": "15+ min delay (%)",
            }
        )
        st.dataframe(airline_table, use_container_width=True, hide_index=True)
        st.download_button(
            "Download airline comparison (CSV)",
            data=airline_table.to_csv(index=False).encode("utf-8-sig"),
            file_name="flightgraph_airline_comparison.csv",
            mime="text/csv",
        )

    # Route data is created once by a Spark aggregation script; dashboard only reads
    # the compact report, never the 31M-row Parquet dataset.
    st.divider()
    st.markdown("### Flight Route Analysis")
    route_file = REPORTS / "route_delay.csv"
    route_table_for_report = pd.DataFrame(
        columns=[
            "Origin", "Destination", "Route", "Flight records",
            "Delayed flights", "15+ min delay (%)",
        ]
    )
    route_analysis_available = False

    if not route_file.exists():
        st.info(
            "Route analysis report has not been generated yet. Run "
            "`python src/14_route_analysis.py` from the project root, "
            "then refresh this dashboard."
        )
    else:
        try:
            routes = load_csv("route_delay.csv")
            required_routes = {
                "Origin", "Dest", "flight_records", "delayed_15min_or_more",
                "delayed_15min_or_more_pct",
            }
            if not required_routes.issubset(routes.columns):
                st.error(
                    "Route report has unexpected columns. Regenerate it with "
                    "src/14_route_analysis.py."
                )
            else:
                routes = routes.copy()
                routes["flight_records"] = pd.to_numeric(
                    routes["flight_records"], errors="coerce"
                )
                routes["delayed_15min_or_more"] = pd.to_numeric(
                    routes["delayed_15min_or_more"], errors="coerce"
                )
                routes["delayed_15min_or_more_pct"] = pd.to_numeric(
                    routes["delayed_15min_or_more_pct"], errors="coerce"
                )
                routes = routes.dropna(
                    subset=[
                        "Origin", "Dest", "flight_records",
                        "delayed_15min_or_more", "delayed_15min_or_more_pct",
                    ]
                )
                routes["Origin"] = routes["Origin"].astype(str).str.upper().str.strip()
                routes["Dest"] = routes["Dest"].astype(str).str.upper().str.strip()
                routes["Route"] = routes["Origin"] + " → " + routes["Dest"]

                st.caption(
                    "Routes are grouped by origin and destination airports. "
                    "Delay rate is the percentage of valid records with ArrDel15 = 1."
                )
                r1, r2, r3 = st.columns(3)
                min_route_records = r1.number_input(
                    "Minimum records per route", min_value=1, max_value=5_000_000,
                    value=1_000, step=500, key="min_route_records",
                )
                top_routes = r2.slider(
                    "Routes to display", min_value=5, max_value=25, value=10,
                    key="top_routes",
                )
                r3.metric("Routes in report", format_number(len(routes)))

                route_filtered = routes[routes["flight_records"] >= min_route_records].copy()
                origin_options = ["All origins"] + sorted(route_filtered["Origin"].unique())
                selected_origin = st.selectbox(
                    "Filter by origin airport", origin_options, key="route_origin"
                )
                if selected_origin != "All origins":
                    route_filtered = route_filtered[
                        route_filtered["Origin"] == selected_origin
                    ]
                destination_options = ["All destinations"] + sorted(
                    route_filtered["Dest"].unique()
                )
                selected_destination = st.selectbox(
                    "Filter by destination airport", destination_options,
                    key="route_destination",
                )
                if selected_destination != "All destinations":
                    route_filtered = route_filtered[
                        route_filtered["Dest"] == selected_destination
                    ]

                route_filtered = route_filtered.sort_values(
                    ["delayed_15min_or_more_pct", "flight_records"],
                    ascending=[False, False],
                )
                route_display = route_filtered.head(top_routes).copy()
                route_table_for_report = route_filtered[
                    [
                        "Origin", "Dest", "Route", "flight_records",
                        "delayed_15min_or_more", "delayed_15min_or_more_pct",
                    ]
                ].rename(
                    columns={
                        "Dest": "Destination",
                        "flight_records": "Flight records",
                        "delayed_15min_or_more": "Delayed flights",
                        "delayed_15min_or_more_pct": "15+ min delay (%)",
                    }
                )

                if route_filtered.empty:
                    st.warning(
                        "No routes match these filters. Lower the minimum records "
                        "or reset the origin/destination filters."
                    )
                else:
                    top_route = route_filtered.iloc[0]
                    rm1, rm2 = st.columns(2)
                    rm1.metric("Highest-delay route in selection", top_route["Route"])
                    rm2.metric(
                        "Delay rate on that route",
                        f"{top_route['delayed_15min_or_more_pct']:.2f}%",
                    )
                    route_chart = route_display.set_index("Route")[[
                        "delayed_15min_or_more_pct"
                    ]].rename(
                        columns={"delayed_15min_or_more_pct": "Delayed flights (%)"}
                    )
                    st.bar_chart(route_chart)
                    visible_route_table = route_display[
                        [
                            "Origin", "Dest", "flight_records",
                            "delayed_15min_or_more", "delayed_15min_or_more_pct",
                        ]
                    ].rename(
                        columns={
                            "Dest": "Destination",
                            "flight_records": "Flight records",
                            "delayed_15min_or_more": "Delayed flights",
                            "delayed_15min_or_more_pct": "15+ min delay (%)",
                        }
                    )
                    st.dataframe(
                        visible_route_table, use_container_width=True, hide_index=True
                    )
                    st.download_button(
                        "Download route analysis (CSV)",
                        data=route_table_for_report.to_csv(index=False).encode("utf-8-sig"),
                        file_name="flightgraph_route_analysis.csv",
                        mime="text/csv",
                    )
                    route_analysis_available = True
        except Exception as exc:
            st.error(f"Could not load route analysis report: {exc}")

    # Key insights remain grounded in the selected EDA summaries.
    st.divider()
    st.markdown("### Key Insights")
    insight1, insight2, insight3 = st.columns(3)
    if not filtered_monthly.empty:
        highest_month = filtered_monthly.loc[
            filtered_monthly["delayed_15min_or_more_pct"].idxmax()
        ]
        month_label = (
            f"{MONTH_NAMES[int(highest_month['Month'])]} {int(highest_month['Year'])}"
        )
        insight1.metric(
            "Highest-delay month in selection", month_label,
            f"{highest_month['delayed_15min_or_more_pct']:.2f}% delay",
        )
    else:
        insight1.metric("Highest-delay month in selection", "No matching data")

    if not airline_chart.empty:
        highest_airline = airline_chart.iloc[0]
        insight2.metric(
            "Highest-delay eligible airline",
            str(highest_airline["Reporting_Airline"]),
            f"{highest_airline['delayed_15min_or_more_pct']:.2f}% delay",
        )
        insight3.metric(
            "Airlines meeting record filter", format_number(len(airline_chart)),
            f"Showing up to {min(top_n, len(airline_chart))}",
        )
    else:
        insight2.metric("Highest-delay eligible airline", "No matching data")
        insight3.metric("Airlines meeting record filter", "0")

    # One ZIP download combines the currently selected report views.
    st.divider()
    st.markdown("### Download Full Report")
    report_tables = {
        "overall_summary.csv": pd.DataFrame([overall]),
        "monthly_delay_selected_period.csv": filtered_monthly[
            ["Year", "Month", "delayed_15min_or_more_pct"]
        ].copy(),
        "airline_comparison_filtered.csv": airline_chart[
            ["Reporting_Airline", "flight_records", "delayed_15min_or_more_pct"]
        ].rename(
            columns={
                "Reporting_Airline": "Airline",
                "flight_records": "Flight records",
                "delayed_15min_or_more_pct": "15+ min delay (%)",
            }
        ),
    }
    if route_analysis_available:
        report_tables["route_analysis_filtered.csv"] = route_table_for_report

    report_notes = (
        "FlightGraph analytics report\n"
        "Summary metrics are from the training dataset EDA summary.\n"
        f"Monthly filters: year={selected_year}; month={selected_month}.\n"
        f"Airline filter: minimum records={int(min_records)}; displayed top N={top_n}.\n"
        "Route analysis is included only when reports/route_delay.csv has been generated.\n"
        "Delay rate refers to records with ArrDel15 = 1. This report is descriptive, "
        "not causal, and does not predict future delays.\n"
    )
    report_zip = make_report_zip(report_tables, report_notes)
    st.download_button(
        label="📦 Download Full FlightGraph Report (ZIP)",
        data=report_zip,
        file_name="FlightGraph_Analytics_Report.zip",
        mime="application/zip",
        help="Downloads summary, selected monthly data, airline comparison and route analysis CSV files.",
    )

    st.divider()
    st.markdown("### About this analysis")
    st.write(
        "FlightGraph uses PySpark to process large flight datasets and creates "
        "EDA summaries for interactive exploration. The charts describe patterns "
        "in the available training records; they do not establish why delays happen "
        "or prove causal relationships. Route analysis is calculated from the "
        "processed training split and is an observational comparison."
    )
    st.caption("FlightGraph | Interactive Analytics Dashboard")


if __name__ == "__main__":
    main()
