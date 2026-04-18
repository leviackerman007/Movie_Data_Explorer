from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_PATH = Path("Dataset") / "tmdb_movies_data.csv"
MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

st.set_page_config(
    page_title="TMDb Movie Intelligence Dashboard",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    """Load and clean TMDb data for dashboard consumption."""
    df = pd.read_csv(path)
    df = df.drop_duplicates().copy()

    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    columns_to_drop = ["budget_adj", "revenue_adj", "overview", "imdb_id", "homepage", "tagline"]
    existing_columns = [col for col in columns_to_drop if col in df.columns]
    df = df.drop(columns=existing_columns)

    df["profit"] = df["revenue"] - df["budget"]

    for col in ["budget", "revenue", "runtime", "vote_average", "popularity", "profit"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def split_pipe_values(series: pd.Series) -> pd.Series:
    """Normalize pipe-delimited string fields into a flat series of values."""
    cleaned = series.dropna().astype(str).str.split("|")
    exploded = cleaned.explode().str.strip()
    return exploded[exploded != ""]


def format_large_number(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"${value:,.0f}"


def filter_dataset(df: pd.DataFrame, year_range: tuple[int, int], selected_genres: list[str]) -> pd.DataFrame:
    filtered = df[df["release_year"].between(year_range[0], year_range[1])].copy()

    if selected_genres:
        genre_pattern = "|".join(selected_genres)
        mask = filtered["genres"].fillna("").str.contains(genre_pattern, case=False, regex=True)
        filtered = filtered[mask]

    return filtered


def render_header(df: pd.DataFrame) -> None:
    st.markdown(
        """
        <style>
            .hero {
                border-radius: 16px;
                padding: 1.2rem 1.4rem;
                background: linear-gradient(120deg, #0f766e 0%, #14532d 45%, #1f2937 100%);
                color: white;
                margin-bottom: 1rem;
            }
            .hero h1 {
                margin: 0;
                font-size: 1.8rem;
            }
            .hero p {
                margin: 0.5rem 0 0;
                color: #e5e7eb;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="hero">
            <h1>TMDb Movie Intelligence Dashboard</h1>
            <p>
                Interactive analysis for {df['release_year'].min()}-{df['release_year'].max()}.
                Explore release behavior, profitability, and creative ecosystem trends.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df: pd.DataFrame) -> None:
    col1, col2, col3, col4 = st.columns(4)

    valid_profit = df.loc[(df["budget"] > 0) & (df["revenue"] > 0), "profit"]
    median_profit_value = valid_profit.median() if not valid_profit.empty else float("nan")

    col1.metric("Movies", f"{len(df):,}")
    col2.metric("Avg Rating", f"{df['vote_average'].mean():.2f}")
    col3.metric("Total Revenue", format_large_number(df["revenue"].sum()))
    col4.metric("Median Profit", format_large_number(median_profit_value))


def render_overview_tab(df: pd.DataFrame) -> None:
    st.subheader("Release Trends")

    releases_per_year = (
        df.groupby("release_year", as_index=False)
        .agg(movie_count=("id", "count"))
        .sort_values("release_year")
    )
    fig_releases = px.line(
        releases_per_year,
        x="release_year",
        y="movie_count",
        markers=True,
        labels={"release_year": "Release Year", "movie_count": "Movies Released"},
        title="Movies Released Per Year",
    )
    fig_releases.update_layout(height=420)
    st.plotly_chart(fig_releases, use_container_width=True)

    col1, col2 = st.columns(2)

    monthly_count = (
        df["release_date"].dt.month.value_counts(dropna=True).sort_index().rename_axis("month_number").reset_index(name="movies")
    )
    monthly_count["month"] = monthly_count["month_number"].map(MONTH_NAMES)

    fig_monthly_count = px.bar(
        monthly_count,
        x="month",
        y="movies",
        title="Release Volume by Month",
        labels={"month": "Month", "movies": "Movies Released"},
        color="movies",
        color_continuous_scale="Teal",
    )
    fig_monthly_count.update_layout(height=360, coloraxis_showscale=False)

    monthly_revenue = (
        df.assign(release_month=df["release_date"].dt.month)
        .groupby("release_month", as_index=False)
        .agg(avg_revenue=("revenue", "mean"))
        .dropna()
    )
    monthly_revenue["month"] = monthly_revenue["release_month"].map(MONTH_NAMES)

    fig_monthly_revenue = px.bar(
        monthly_revenue,
        x="month",
        y="avg_revenue",
        title="Average Revenue by Release Month",
        labels={"month": "Month", "avg_revenue": "Avg Revenue"},
        color="avg_revenue",
        color_continuous_scale="Viridis",
    )
    fig_monthly_revenue.update_layout(height=360, coloraxis_showscale=False)

    col1.plotly_chart(fig_monthly_count, use_container_width=True)
    col2.plotly_chart(fig_monthly_revenue, use_container_width=True)


def render_finance_tab(df: pd.DataFrame) -> None:
    st.subheader("Budget, Revenue, and Profitability")

    non_zero_money = df[(df["budget"] > 0) & (df["revenue"] > 0)].copy()
    fig_budget_revenue = px.scatter(
        non_zero_money,
        x="budget",
        y="revenue",
        color="vote_average",
        hover_name="original_title",
        hover_data={"release_year": True, "profit": ":,.0f"},
        title="Budget vs Revenue (Color by Rating)",
        labels={"budget": "Budget", "revenue": "Revenue", "vote_average": "Rating"},
    )
    fig_budget_revenue.update_layout(height=480)
    st.plotly_chart(fig_budget_revenue, use_container_width=True)

    top_profitable = (
        df[["original_title", "profit"]]
        .dropna()
        .sort_values("profit", ascending=False)
        .head(10)
        .sort_values("profit")
    )
    fig_profit = px.bar(
        top_profitable,
        x="profit",
        y="original_title",
        orientation="h",
        title="Top 10 Profitable Movies",
        labels={"profit": "Profit", "original_title": "Movie"},
        color="profit",
        color_continuous_scale="Mint",
    )
    fig_profit.update_layout(height=420, coloraxis_showscale=False)

    corr_cols = ["budget", "revenue", "profit", "popularity", "runtime", "vote_average"]
    corr_matrix = df[corr_cols].corr(numeric_only=True).round(2)
    fig_corr = px.imshow(
        corr_matrix,
        text_auto=True,
        color_continuous_scale="RdYlGn",
        title="Feature Correlation Matrix",
        aspect="auto",
    )
    fig_corr.update_layout(height=420)

    col1, col2 = st.columns(2)
    col1.plotly_chart(fig_profit, use_container_width=True)
    col2.plotly_chart(fig_corr, use_container_width=True)


def render_talent_tab(df: pd.DataFrame, top_n: int) -> None:
    st.subheader("Genre, Director, and Production Insights")

    genre_counts = split_pipe_values(df["genres"]).value_counts().head(top_n).sort_values()
    director_counts = split_pipe_values(df["director"]).value_counts().head(top_n).sort_values()
    company_counts = split_pipe_values(df["production_companies"]).value_counts().head(top_n).sort_values()

    col1, col2, col3 = st.columns(3)

    fig_genres = px.bar(
        genre_counts,
        orientation="h",
        title=f"Top {top_n} Genres",
        labels={"value": "Movies", "index": "Genre"},
        color=genre_counts.values,
        color_continuous_scale="Blues",
    )
    fig_genres.update_layout(height=500, coloraxis_showscale=False)

    fig_directors = px.bar(
        director_counts,
        orientation="h",
        title=f"Top {top_n} Directors",
        labels={"value": "Movies", "index": "Director"},
        color=director_counts.values,
        color_continuous_scale="Burg",
    )
    fig_directors.update_layout(height=500, coloraxis_showscale=False)

    fig_companies = px.bar(
        company_counts,
        orientation="h",
        title=f"Top {top_n} Production Companies",
        labels={"value": "Movies", "index": "Production Company"},
        color=company_counts.values,
        color_continuous_scale="Greens",
    )
    fig_companies.update_layout(height=500, coloraxis_showscale=False)

    col1.plotly_chart(fig_genres, use_container_width=True)
    col2.plotly_chart(fig_directors, use_container_width=True)
    col3.plotly_chart(fig_companies, use_container_width=True)


def render_explorer_tab(df: pd.DataFrame) -> None:
    st.subheader("Movie Explorer")

    display_columns = [
        "original_title",
        "release_year",
        "genres",
        "director",
        "vote_average",
        "budget",
        "revenue",
        "profit",
        "runtime",
        "popularity",
    ]

    explorer_df = df[display_columns].sort_values("revenue", ascending=False)
    st.dataframe(explorer_df, use_container_width=True, height=500)

    csv_data = explorer_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Filtered Data (CSV)",
        data=csv_data,
        file_name="tmdb_filtered_movies.csv",
        mime="text/csv",
    )


def _linear_projection(years: list[int], values: list[float], horizon: int) -> pd.DataFrame:
    """Create a simple linear projection using closed-form slope/intercept."""
    if len(years) < 2:
        return pd.DataFrame(columns=["year", "value", "series"])

    x_mean = sum(years) / len(years)
    y_mean = sum(values) / len(values)

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(years, values))
    denominator = sum((x - x_mean) ** 2 for x in years)
    slope = 0.0 if denominator == 0 else numerator / denominator
    intercept = y_mean - slope * x_mean

    projected_years = list(range(years[-1] + 1, years[-1] + horizon + 1))
    projected_values = [intercept + slope * year for year in projected_years]

    historical_df = pd.DataFrame({"year": years, "value": values, "series": "Historical"})
    projected_df = pd.DataFrame({"year": projected_years, "value": projected_values, "series": "Projected"})
    return pd.concat([historical_df, projected_df], ignore_index=True)


def render_executive_tab(df: pd.DataFrame, forecast_horizon: int) -> None:
    st.subheader("Executive Summary")

    yearly_rollup = (
        df.groupby("release_year", as_index=False)
        .agg(
            movies=("id", "count"),
            avg_revenue=("revenue", "mean"),
            avg_profit=("profit", "mean"),
        )
        .sort_values("release_year")
    )

    if yearly_rollup.empty:
        st.info("Not enough data for executive summary.")
        return

    best_release_year = int(yearly_rollup.loc[yearly_rollup["movies"].idxmax(), "release_year"])
    best_revenue_year = int(yearly_rollup.loc[yearly_rollup["avg_revenue"].idxmax(), "release_year"])
    avg_profit_value = float(yearly_rollup["avg_profit"].mean())

    top_genre = "N/A"
    genre_values = split_pipe_values(df["genres"]).value_counts()
    if not genre_values.empty:
        top_genre = str(genre_values.index[0])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Peak Release Year", str(best_release_year))
    col2.metric("Peak Revenue Year", str(best_revenue_year))
    col3.metric("Top Genre", top_genre)
    col4.metric("Avg Yearly Profit", format_large_number(avg_profit_value))

    st.markdown("### Analyst Notes")
    st.write(
        f"- The busiest release cycle in this filtered view is **{best_release_year}**.\n"
        f"- Average revenue reaches its highest level in **{best_revenue_year}**.\n"
        f"- **{top_genre}** appears most often among selected records.\n"
        "- Use this summary as a quick business brief before drilling into chart-level details."
    )

    st.markdown("### Short-Horizon Revenue Projection")
    projection_source = yearly_rollup.dropna(subset=["avg_revenue"])
    years = projection_source["release_year"].astype(int).tolist()
    values = projection_source["avg_revenue"].astype(float).tolist()

    projection_df = _linear_projection(years, values, horizon=forecast_horizon)
    if projection_df.empty:
        st.info("Not enough yearly history to generate a projection.")
        return

    fig_projection = px.line(
        projection_df,
        x="year",
        y="value",
        color="series",
        markers=True,
        labels={"year": "Year", "value": "Average Revenue", "series": "Data Type"},
        title=f"Historical vs Next {forecast_horizon} Year Projection",
        color_discrete_map={"Historical": "#0f766e", "Projected": "#b45309"},
    )
    fig_projection.update_layout(height=440)
    st.plotly_chart(fig_projection, use_container_width=True)


def main() -> None:
    if not DATA_PATH.exists():
        st.error(f"Dataset file not found at: {DATA_PATH}")
        st.stop()

    df = load_data(DATA_PATH)

    render_header(df)

    with st.sidebar:
        st.header("Dashboard Controls")

        year_min = int(df["release_year"].min())
        year_max = int(df["release_year"].max())
        selected_year_range = st.slider(
            "Release Year Range",
            min_value=year_min,
            max_value=year_max,
            value=(year_min, year_max),
        )

        all_genres = sorted(split_pipe_values(df["genres"]).unique().tolist())
        selected_genres = st.multiselect("Genres", options=all_genres, default=[])

        top_n = st.selectbox("Top-N Rankings", [10, 15, 20, 25], index=1)
        forecast_horizon = st.selectbox("Projection Horizon (Years)", [3, 5, 7], index=1)

    filtered_df = filter_dataset(df, selected_year_range, selected_genres)

    if filtered_df.empty:
        st.warning("No data available for the current filter selection.")
        st.stop()

    render_kpis(filtered_df)

    tabs = st.tabs(["Executive Summary", "Overview", "Financial Insights", "Talent & Production", "Explorer"])

    with tabs[0]:
        render_executive_tab(filtered_df, forecast_horizon=forecast_horizon)
    with tabs[1]:
        render_overview_tab(filtered_df)
    with tabs[2]:
        render_finance_tab(filtered_df)
    with tabs[3]:
        render_talent_tab(filtered_df, top_n=top_n)
    with tabs[4]:
        render_explorer_tab(filtered_df)


if __name__ == "__main__":
    main()
