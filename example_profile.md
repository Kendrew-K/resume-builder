# Example Profile

Fictional profile used as the default input for `python job_search_cli.py rank`
and as a shape reference for your own `experiences.md`. Nothing here is real.

Copy it to `experiences.md`, replace everything with your own history, and keep
it out of version control (`.gitignore` already excludes it).

The ranker does not care about the headings. It lowercases this whole file and
looks for the skill terms in `job_search/rank.py::SKILLS_VOCAB`, so the only
thing that changes your fit scores is which of those terms genuinely appear.

## Contact
- Name: Jordan Rivera
- Email: jordan.rivera@example.com
- Phone: (555) 010-4477
- Location: Austin, Texas, United States
- LinkedIn: linkedin.com/in/example
- GitHub: github.com/example

## Education
- **State University**, Austin, TX
  - B.S. in Data Science, Aug 2024 – expected May 2027
  - GPA 3.8

## Technical Skills
Python, SQL, R, Excel, Power BI, Tableau, pandas, NumPy, scikit-learn, Git,
statistics, hypothesis testing, regression, logistic regression, clustering,
forecasting, data visualization, ETL, data pipeline, dashboard, A/B testing,
Snowflake, AWS

## Experience

### Data Analytics Intern, Northwind Logistics (Jun 2025 – Aug 2025)
- Built an ETL pipeline in Python and SQL that consolidated 14 regional
  shipment feeds into a single Snowflake table, cutting the weekly reporting
  cycle from 6 hours to 20 minutes.
- Designed a Power BI dashboard tracking on-time delivery by lane, adopted by
  the operations team as their standing Monday review.
- Ran an A/B test on two dispatch-routing heuristics across 1,200 shipments and
  found no significant difference (p = 0.41), which stopped a planned rollout.

### Undergraduate Research Assistant, Statistics Department (Jan 2025 – present)
- Fit logistic regression and gradient-boosted models on a 90,000-row survey
  dataset to predict program dropout, reaching 0.81 AUC on held-out data.
- Wrote the data-cleaning layer in pandas that the other four assistants use.

## Projects

### Transit Delay Forecaster
- Forecasting model over three years of city bus arrival data, using seasonal
  decomposition plus regression on weather and event features.
- Published as a Streamlit dashboard with a per-route drilldown.

### Grocery Price Tracker
- Scraper plus SQLite warehouse tracking 400 SKUs daily; clustering on price
  trajectories to group items that move together.
