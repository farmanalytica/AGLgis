# -*- coding: utf-8 -*-
"""
SAR timeseries chart renderer for the AGLgis plugin.

Two rendering modes:
- ``render_plugin_html`` — interactive SVG/JS chart with hover tooltips.
  Zero external dependencies; works in any QWebView.
- ``render_browser_html`` — full interactive Plotly page for an external browser.
"""

import json

import plotly.express as px


_CONFIG_BROWSER = {
    "displaylogo": False,
    "responsive": True,
}


def render_plugin_html(dataframe):
    """Return an interactive SVG chart embedded in HTML (no external JS/CSS)."""
    dates = dataframe["dates"].tolist()
    values = [round(float(v), 6) for v in dataframe["AOI_average"].tolist()]
    sorted_pairs = sorted(zip(dates, values), key=lambda x: x[0])
    dates = [p[0] for p in sorted_pairs]
    values = [p[1] for p in sorted_pairs]

    dates_js = json.dumps(dates)
    values_js = json.dumps(values)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100%;background:#fff;font-family:Arial,sans-serif;overflow:hidden}}
#wrap{{position:relative;width:100%;height:100%}}
svg{{position:absolute;top:0;left:0;width:100%;height:100%}}
#tip{{position:fixed;pointer-events:none;display:none;background:rgba(33,33,33,.88);
      color:#fff;border-radius:5px;padding:5px 10px;font-size:12px;white-space:nowrap;z-index:100}}
</style>
</head><body>
<div id="wrap"><svg id="svg"></svg><div id="tip"></div></div>
<script>
(function(){{
var dates={dates_js}, vals={values_js};
var ML=64,MR=18,MT=32,MB=64;

function fmtDate(s){{
    var m=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var p=s.split('-'); return m[parseInt(p[1])-1]+' '+p[0];
}}

function draw(){{
    var W=window.innerWidth||document.documentElement.clientWidth||620;
    var H=Math.max((window.innerHeight||document.documentElement.clientHeight||230)-8,160);
    var cW=W-ML-MR, cH=H-MT-MB, n=vals.length;

    // Y: 0-based, ticks every 0.1 (same intervals as Plotly browser)
    var rawMax=Math.max.apply(0,vals);
    var mx=Math.ceil(rawMax*10+0.5)/10;
    var nT=Math.round(mx/0.1);

    function xi(i){{return ML+i/(n-1)*cW;}}
    function yv(v){{return MT+(1-v/mx)*cH;}}

    var path='',dots='',hits='';
    for(var i=0;i<n;i++){{
        var x=xi(i).toFixed(1),y=yv(vals[i]).toFixed(1);
        path+=(i?'L':'M')+x+' '+y;
        dots+='<circle cx="'+x+'" cy="'+y+'" r="3.5" fill="#1b6b39" stroke="#fff" stroke-width="1.5" class="dot" data-i="'+i+'"/>';
        hits+='<rect x="'+(xi(i)-cW/n/2).toFixed(1)+'" y="'+MT+'" width="'+(cW/n).toFixed(1)+'" height="'+cH+'" fill="transparent" class="hit" data-i="'+i+'"/>';
    }}

    // Y ticks: 0.000, 0.100, ... mx
    var yg='',yt='';
    for(var t=0;t<=nT;t++){{
        var v=+(t*0.1).toFixed(3),y=yv(v).toFixed(1);
        yg+='<line x1="'+ML+'" y1="'+y+'" x2="'+(ML+cW)+'" y2="'+y+'" stroke="#eeeeee"/>';
        yt+='<text x="'+(ML-6)+'" y="'+(parseFloat(y)+4).toFixed(1)+'" text-anchor="end" font-size="10" fill="#616161">'+v.toFixed(3)+'</text>';
    }}

    // X ticks: "Mon YYYY", first date of each month, every 2 months if >10 months
    var xt='',seen={{}},mCount=0;
    for(var i=0;i<n;i++){{var p=dates[i].split('-'),my=p[0]+'-'+p[1];if(!seen[my]){{seen[my]=true;mCount++;}}}}
    var mStep=mCount>10?2:1,mc=0,lastMY='';
    for(var i=0;i<n;i++){{
        var p=dates[i].split('-'),my=p[0]+'-'+p[1];
        if(my!==lastMY){{lastMY=my;mc++;
            if(mc%mStep===1||mStep===1){{
                var x=xi(i).toFixed(1),ty=(MT+cH+16).toFixed(1);
                xt+='<text x="'+x+'" y="'+ty+'" text-anchor="end" font-size="9" fill="#888"'
                   +' transform="rotate(-35,'+x+','+ty+')">'+fmtDate(dates[i])+'</text>';
            }}
        }}
    }}

    var svg=document.getElementById('svg');
    svg.setAttribute('viewBox','0 0 '+W+' '+H);
    svg.setAttribute('width',W); svg.setAttribute('height',H);
    svg.innerHTML=
        '<rect width="'+W+'" height="'+H+'" fill="#fff"/>'+yg
        +'<line x1="'+ML+'" y1="'+MT+'" x2="'+ML+'" y2="'+(MT+cH)+'" stroke="#d0d0d0"/>'
        +'<line x1="'+ML+'" y1="'+(MT+cH)+'" x2="'+(ML+cW)+'" y2="'+(MT+cH)+'" stroke="#d0d0d0"/>'
        +'<path d="'+path+'" fill="none" stroke="#1b6b39" stroke-width="2"/>'
        +dots+yt+xt
        +'<text x="'+(W/2).toFixed(0)+'" y="22" text-anchor="middle" font-size="13" font-weight="bold" fill="#212121">VV/VH Ratio Mean Time Series</text>'
        +'<text x="'+(W/2).toFixed(0)+'" y="'+(H-6)+'" text-anchor="middle" font-size="10" fill="#616161">Date</text>'
        +'<text x="12" y="'+(MT+cH/2).toFixed(0)+'" text-anchor="middle" font-size="10" fill="#616161"'
        +' transform="rotate(-90,12,'+(MT+cH/2).toFixed(0)+')">VV/VH Ratio Mean</text>'
        +'<g>'+hits+'</g>';

    var tip=document.getElementById('tip');
    svg.querySelectorAll('.hit').forEach(function(el){{
        el.addEventListener('mousemove',function(e){{
            var i=+this.getAttribute('data-i');
            tip.innerHTML='<b>'+dates[i]+'</b><br>AOI_average: '+vals[i].toFixed(4);
            tip.style.display='block';
            var tx=e.clientX+14, ty=e.clientY-44;
            if(tx+160>window.innerWidth)tx=e.clientX-170;
            if(ty<0)ty=4;
            tip.style.left=tx+'px'; tip.style.top=ty+'px';
            svg.querySelectorAll('.dot').forEach(function(d,j){{
                d.setAttribute('r',j===i?'5.5':'3.5');
                d.setAttribute('fill',j===i?'#155a2f':'#1b6b39');
            }});
        }});
        el.addEventListener('mouseleave',function(){{
            tip.style.display='none';
            svg.querySelectorAll('.dot').forEach(function(d){{
                d.setAttribute('r','3.5');d.setAttribute('fill','#1b6b39');
            }});
        }});
    }});
}}
draw();
window.addEventListener('resize',draw);
}})();
</script>
</body></html>"""


def render_browser_html(dataframe):
    """Return a standalone interactive Plotly page for an external browser."""
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
    return fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config=_CONFIG_BROWSER,
    )
