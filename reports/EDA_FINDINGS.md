
# FlightGraph — Exploratory Data Analysis Findings

## 1. Dataset Overview

The training dataset contains 31,149,502 records and 65 columns.
The data-quality checks found no null or empty-string values in the
tested columns. The preliminary invalid-value screening and sampled
duplicate-key check did not identify issues in their checked scope.

## 2. Overall Arrival Delay Distribution

Among 31,149,502 training records, 5,560,469 records (17.85%)
had an ArrDel15 value of 1, representing an arrival delay of
15 minutes or more. The remaining 82.15% did not meet this threshold.

## 3. Airline-Level Analysis

In the comparison of airlines with at least 100,000 training records,
the highest observed delayed-flight proportions were:

- B6: 26.14%
- G4: 25.08%
- F9: 25.05%

These findings describe this dataset and should not be interpreted
as a definitive ranking of overall airline service quality.

## 4. Monthly Trend Analysis

The monthly delay rate varied substantially across the period
from January 2018 through December 2022. The lowest values appear
around May–June 2020, at approximately 4.6–4.9%. The highest point
appears in December 2022, at approximately 27%.

The chart shows temporal variation but does not establish the
causes of these changes.

## 5. Limitations

- Duplicate detection was performed on a 0.5% sample using a
  six-column candidate key.
- Invalid-value screening covered selected columns in a 1% sample.
- No nulls or empty strings were detected by the implemented check,
  but floating-point NaN values require separate validation.
- The airline and monthly findings are descriptive and do not
  establish causal relationships.

## 6. Generated Visualizations

- figures/overall_delay_distribution.png
- figures/airline_delay_comparison.png
- figures/monthly_delay_trend.png
