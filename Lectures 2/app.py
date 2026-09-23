"""Lease portfolio dashboard for the Lecture 2 sample leases."""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, dcc, html, dash_table


ROOT = Path(__file__).parent
with (ROOT / "lease_data.json").open() as f:
    leases = pd.DataFrame(json.load(f)["leases"])

# Approximate map points for visualization; the source JSON contains addresses,
# but not geocoded coordinates.
coordinates = {
    "01_harborview_biotech_chapel.pdf": (41.3048, -72.9279),
    "02_whitney_corridor_retail.pdf": (41.3558, -72.9216),
    "03_long_wharf_industrial.pdf": (41.2835, -72.9076),
    "04_orange_street_professional.pdf": (41.3011, -72.9247),
    "05_westville_medical_retail.pdf": (41.3190, -72.9671),
    "06_science_park_office.pdf": (41.3220, -72.9294),
    "07_chapel_west_boutique.pdf": (41.3080, -72.9344),
    "08_milford_flex_space.pdf": (41.2215, -73.0565),
    "09_state_street_amendment.pdf": (41.3053, -72.9160),
    "10_branford_office_draft.pdf": (41.2770, -72.6794),
}
leases[["lat", "lon"]] = leases["file"].apply(lambda x: pd.Series(coordinates[x]))
leases["monthly_rent"] = leases["annual_base_rent"] / 12
leases["annual_cash_flow"] = leases["annual_base_rent"]

COLORS = ["#151526", "#39203b", "#772653", "#c43b73", "#ff6f9f"]
app = Dash(__name__)
app.title = "LeaseLens"

def money(value):
    return "—" if pd.isna(value) else f"${value:,.0f}"

app.layout = html.Div([
    html.Div([html.Div("LEASELENS", className="brand"), html.Div("Lecture 02 · Property intelligence", className="eyebrow")], className="topbar"),
    html.Div([
        html.Div([html.Div("Portfolio pulse", className="eyebrow"), html.H1("Your leases, in one view."), html.P("Explore rent concentration, location, and contractual cash flow across the sample portfolio.")], className="hero-copy"),
        html.Div([html.Label("Lease structure", className="eyebrow"), dcc.Dropdown(id="structure", options=[{"label": x, "value": x} for x in sorted(leases.lease_structure.dropna().unique())], multi=True, placeholder="All structures", className="dropdown"), html.Label("Status", className="eyebrow status-label"), dcc.Dropdown(id="status", options=[{"label": x.title(), "value": x} for x in sorted(leases.status.unique())], multi=True, placeholder="All statuses", className="dropdown")], className="filters")
    ], className="hero"),
    html.Div(id="kpis", className="kpi-grid"),
    html.Div([html.Div([html.Div("Property map", className="section-label"), html.H2("Rent intensity by location"), dcc.Graph(id="map", config={"displayModeBar": False})], className="card map-card"), html.Div([html.Div("Cash flow", className="section-label"), html.H2("Annual base rent by property"), dcc.Graph(id="cashflow", config={"displayModeBar": False})], className="card cash-card")], className="grid"),
    html.Div([html.Div("Portfolio register", className="section-label"), html.H2("Lease details"), dash_table.DataTable(id="table", columns=[{"name": x, "id": x} for x in ["tenant", "address", "space_type", "lease_structure", "annual_base_rent", "status"]], page_size=10, sort_action="native", style_as_list_view=True, style_cell={"backgroundColor": "#171729", "color": "#f5f1f7", "border": "none", "padding": "14px", "fontFamily": "Inter"}, style_header={"backgroundColor": "#25243c", "fontWeight": "700", "color": "#ff9fbd"}, style_data_conditional=[{"if": {"column_id": "annual_base_rent"}, "format": {"specifier": "$,.0f"}}])], className="card table-card"),
    html.Footer("Map points are approximate visualizations derived from the listed addresses. Financial view uses annual base rent as contracted gross cash flow; expense amounts were not provided.", className="footer")
], className="app")

@app.callback(Output("kpis", "children"), Output("map", "figure"), Output("cashflow", "figure"), Output("table", "data"), Input("structure", "value"), Input("status", "value"))
def update_dashboard(structures, statuses):
    df = leases.copy()
    if structures:
        df = df[df.lease_structure.isin(structures)]
    if statuses:
        df = df[df.status.isin(statuses)]
    total = df.annual_base_rent.sum()
    kpis = [html.Div([html.Div("Properties", className="kpi-label"), html.Div(f"{len(df)}", className="kpi-value")], className="kpi"), html.Div([html.Div("Annual base rent", className="kpi-label"), html.Div(money(total), className="kpi-value")], className="kpi pink"), html.Div([html.Div("Monthly run-rate", className="kpi-label"), html.Div(money(total / 12), className="kpi-value")], className="kpi"), html.Div([html.Div("Rent / SF weighted", className="kpi-label"), html.Div(money(total / df.rentable_sqft.sum()) if len(df) else "—", className="kpi-value")], className="kpi")]
    if df.empty:
        df = leases.head(0)
    fig_map = px.scatter_map(df, lat="lat", lon="lon", color="annual_base_rent", size="annual_base_rent", hover_name="tenant", hover_data={"address": True, "annual_base_rent": ":$,.0f", "lat": False, "lon": False}, color_continuous_scale=COLORS, zoom=9.5, center={"lat": 41.31, "lon": -72.91}, height=430)
    fig_map.update_layout(map_style="open-street-map", margin={"l": 0, "r": 0, "t": 0, "b": 0}, coloraxis_colorbar_title="Annual rent", paper_bgcolor="#171729", font_color="#f5f1f7")
    chart = df.sort_values("annual_base_rent")
    fig_cash = px.bar(chart, x="annual_base_rent", y="tenant", orientation="h", color="annual_base_rent", color_continuous_scale=COLORS, labels={"annual_base_rent": "Annual base rent", "tenant": ""}, height=430)
    fig_cash.update_layout(margin={"l": 0, "r": 0, "t": 10, "b": 0}, coloraxis_showscale=False, paper_bgcolor="#171729", plot_bgcolor="#171729", font_color="#f5f1f7", xaxis_tickprefix="$", xaxis_tickformat=",.0f")
    data = df[["tenant", "address", "space_type", "lease_structure", "annual_base_rent", "status"]].to_dict("records")
    return kpis, fig_map, fig_cash, data

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
