# -*- coding: utf-8 -*-
"""
SAR timeseries chart renderer for the AGLgis plugin.

A single ``render_chart_html`` builds a self-contained page (plotly.js embedded
inline) used for BOTH the in-plugin QWebView and the "open in browser" action,
so the chart is byte-for-byte identical in both. Load it from a ``file://`` URL.
"""

import json
import os

import plotly.express as px


# QtWebKit (the only web engine in this QGIS) can't run plotly 6.x's plotly.js
# (v3). We vendor the last v1 release, which does run there, and inline it.
_PLOTLY_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "plotly-1.58.5.min.js",
)
_plotly_js_cache = None


def _plotly_js():
    global _plotly_js_cache
    if _plotly_js_cache is None:
        with open(_PLOTLY_JS_PATH, "r", encoding="utf-8") as f:
            _plotly_js_cache = f.read()
    return _plotly_js_cache


def _build_figure(dataframe):
    """Build the shared VV/VH-ratio time-series figure."""
    fig = px.line(
        dataframe,
        x="dates",
        y="AOI_average",
        markers=True,
        title="VV/VH Ratio Mean Time Series",
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="VV/VH Ratio Mean",
        yaxis=dict(rangemode="tozero", tickformat=".3f"),
        margin=dict(l=80, r=20, t=40, b=40),
    )
    return fig


def render_chart_html(dataframe):
    """Return a self-contained page that renders the figure with the vendored
    plotly.js v1.58 (QtWebKit-compatible), fed the figure JSON via Plotly.newPlot.

    Used for both the embedded view and the browser export so they are identical.
    The default v6 template is dropped so the JSON stays within what the old
    engine understands. Intended to be written to a temp file and loaded from a
    ``file://`` URL.
    """
    fig = _build_figure(dataframe)
    fig.update_layout(template="none")
    # plotly 6.x encodes numeric arrays as base64 typed-arrays ("bdata"), even in
    # to_dict(); plotly.js v1.58 can't decode that, so the y values render as
    # garbage. Rebuild the single trace's coordinates as plain lists from the
    # source dataframe and serialize with the stdlib json encoder.
    fig_dict = fig.to_dict()
    x = dataframe["dates"].tolist()
    y = [float(v) for v in dataframe["AOI_average"].tolist()]
    for trace in fig_dict.get("data", []):
        trace["x"] = x
        trace["y"] = y
    fig_json = json.dumps(fig_dict)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>html,body{{height:100%;width:100%;margin:0;padding:0}}#chart{{width:100%;height:100%}}</style>
<script>{_plotly_js()}</script>
</head><body>
<div id="chart"></div>
<script>
var fig = {fig_json};
Plotly.newPlot('chart', fig.data, fig.layout, {{displaylogo:false, responsive:true}});
window.addEventListener('resize', function(){{ Plotly.Plots.resize('chart'); }});
</script>
</body></html>"""
