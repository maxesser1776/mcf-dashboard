import plotly.graph_objects as go
import pandas as pd

# --- 1. Line chart with optional second y-axis
def dual_axis_plot(df, x, y1, y2=None, title="", y1_label="", y2_label=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[x], y=df[y1], name=y1_label or y1, line=dict(color='blue')))

    if y2:
        fig.add_trace(go.Scatter(x=df[x], y=df[y2], name=y2_label or y2, yaxis='y2', line=dict(color='red')))
        fig.update_layout(
            yaxis2=dict(
                title=y2_label or y2,
                overlaying='y',
                side='right'
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y1_label or y1,
        legend=dict(x=0, y=1),
        margin=dict(l=40, r=40, t=40, b=40),
        height=400
    )
    return fig

# --- 2. Single Line Plot
def single_line_plot(df, x, y, title="", y_label=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[x], y=df[y], name=y, line=dict(color='blue')))
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label or y,
        height=400,
        margin=dict(l=40, r=