"""交互式HTML可视化报告生成器。

生成自包含的单文件HTML报告，包含：
- 大盘指数仪表盘
- 策略通过率统计条
- 筛选结果表格（可排序/筛选）
- K线迷你图（CSS柱状图模拟）
- 行业分布热力图

数据源：基于策略判定结果，无外部依赖。
"""

import os
import sys
from datetime import datetime
import json
from html import escape

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config  # noqa: E402


def generate_html_report(
    results: list[dict],
    output_dir: str,
    market_env: dict = None,
    strategy_stats: dict = None,
    backtest_data: dict = None,
) -> str:
    """生成交互式HTML可视化选股报告。

    Args:
        results: 筛选结果列表。
        output_dir: 输出目录。
        market_env: 大盘环境数据。
        strategy_stats: 策略统计。
        backtest_data: 回测结果（{market: {strategies: [...]}}，可选）。

    Returns:
        str: HTML文件路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now()
    filename = f"选股报告_{now.strftime('%Y%m%d_%H%M%S')}.html"
    html_path = os.path.join(output_dir, filename)

    # json.dumps 不转义 "</script>"，替换为 "<\/" 防止闭合脚本标签
    results_json = json.dumps(results, ensure_ascii=False).replace("</", "<\\/")
    report_time = now.strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>选股报告 - {report_time}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #f5f6fa; color: #2c3e50; }}
.header {{ background: linear-gradient(135deg, #1a237e, #283593); color: #fff; padding: 24px 32px; }}
.header h1 {{ font-size: 22px; margin-bottom: 4px; }}
.header .sub {{ font-size: 13px; opacity: 0.8; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
.section {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.section h2 {{ font-size: 16px; border-bottom: 2px solid #3f51b5; padding-bottom: 8px; margin-bottom: 14px; color: #1a237e; }}
/* 大盘仪表盘 */
.dashboard {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.index-card {{ flex: 1; min-width: 180px; background: #fafafa; border-radius: 6px; padding: 14px; text-align: center; border-left: 3px solid #3f51b5; }}
.index-card .name {{ font-size: 12px; color: #666; }}
.index-card .price {{ font-size: 22px; font-weight: bold; margin: 4px 0; }}
.index-card .pct {{ font-size: 14px; font-weight: bold; }}
.up {{ color: #e53935; }}
.down {{ color: #43a047; }}
/* 表格 */
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #e8eaf6; padding: 10px 8px; text-align: left; font-weight: 600; cursor: pointer; user-select: none; border-bottom: 2px solid #c5cae9; }}
th:hover {{ background: #c5cae9; }}
td {{ padding: 8px; border-bottom: 1px solid #eee; }}
tr:hover {{ background: #f5f5f5; }}
.consensus-high {{ background: #e8f5e9; }}
.consensus-mid {{ background: #fff8e1; }}
.tag {{ display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin: 1px; }}
.tag-pass {{ background: #c8e6c9; color: #2e7d32; }}
.tag-fail {{ background: #ffcdd2; color: #c62828; }}
/* K线迷你图 */
.mini-chart {{ display: flex; align-items: flex-end; gap: 1px; height: 30px; }}
.mini-bar {{ flex: 1; min-width: 2px; border-radius: 1px; }}
.mini-bar-up {{ background: #e53935; }}
.mini-bar-down {{ background: #43a047; }}
/* 行业热力 */
.heatmap {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.heat-cell {{ padding: 4px 10px; border-radius: 4px; font-size: 12px; }}
/* 排序控件 */
.sort-controls {{ margin-bottom: 12px; }}
.sort-controls button {{ padding: 6px 14px; margin-right: 6px; border: 1px solid #3f51b5; background: #fff; color: #3f51b5; border-radius: 4px; cursor: pointer; font-size: 12px; }}
.sort-controls button.active {{ background: #3f51b5; color: #fff; }}
.filter-input {{ padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; width: 200px; font-size: 12px; }}
/* 风险声明 */
.risk {{ background: #fff3e0; border: 1px solid #ff9800; border-radius: 6px; padding: 16px; color: #e65100; font-size: 12px; line-height: 1.8; }}
.risk strong {{ color: #bf360c; }}
/* 策略统计 */
.strategy-bar {{ display: flex; align-items: center; margin: 6px 0; }}
.strategy-name {{ width: 140px; font-size: 12px; }}
.strategy-track {{ flex: 1; height: 16px; background: #e0e0e0; border-radius: 8px; overflow: hidden; }}
.strategy-fill {{ height: 100%; background: linear-gradient(90deg, #42a5f5, #1e88e5); border-radius: 8px; transition: width 0.5s; }}
.strategy-val {{ width: 60px; text-align: right; font-size: 12px; }}
/* 环境状态徽章 */
.badge {{ display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-right: 8px; }}
.badge-bull {{ background: #c8e6c9; color: #2e7d32; }}
.badge-bear {{ background: #ffcdd2; color: #c62828; }}
.badge-flat {{ background: #fff8e1; color: #f57f17; }}
.env-header {{ margin-bottom: 10px; }}
/* 指数信号表格 */
.sig-table {{ width: 100%; font-size: 12px; margin-top: 10px; }}
.sig-table th {{ background: #f5f5f5; padding: 6px 8px; border-bottom: 1px solid #ddd; }}
.sig-table td {{ padding: 5px 8px; border-bottom: 1px solid #f0f0f0; }}
/* 趋势推演 */
.outlook-item {{ padding: 8px 12px; border-left: 3px solid #3f51b5; background: #f8f9ff; margin-bottom: 8px; border-radius: 0 4px 4px 0; font-size: 12px; line-height: 1.7; }}
.outlook-item .ot-kind {{ font-weight: 600; color: #1a237e; }}
.outlook-note {{ font-size: 11px; color: #888; margin-top: 8px; }}
/* 回测表格 */
.bt-win {{ color: #e53935; font-weight: 600; }}
.bt-lose {{ color: #43a047; }}
.bt-note {{ font-size: 11px; color: #888; line-height: 1.8; margin-top: 8px; }}
</style>
</head>
<body>

<div class="header">
  <h1>Stock-Selecter-Pro v{config.VERSION} 选股报告</h1>
  <div class="sub">生成时间: {report_time} | 数据源: 东方财富公开行情接口（腾讯/新浪K线备选） | 数据通道: {escape((market_env or {}).get('data_channel', '实时主节点'))} | 通过标的: {total} 只</div>
</div>

<div class="container">

  <!-- 大盘环境 -->
  <div class="section">
    <h2>大盘环境与指数仪表盘</h2>
    <div class="env-header">{render_env_badge(market_env)}</div>
    <div class="dashboard" id="dashboard">{render_dashboard(market_env)}</div>
    {render_env_signals(market_env)}
  </div>

  <!-- 市场趋势推演 -->
  <div class="section">
    <h2>市场趋势推演（基于实时真实信号 · 条件式表述 · 非预测承诺）</h2>
    {render_trend_outlook(market_env)}
  </div>

  <!-- 策略历史回测 -->
  <div class="section">
    <h2>策略历史回测（真实K线信号回放）</h2>
    {render_backtest(backtest_data)}
  </div>

  <!-- 策略统计 -->
  <div class="section">
    <h2>策略通过率统计</h2>
    <div id="strategy-stats">
      {render_strategy_stats(strategy_stats, total)}
    </div>
  </div>

  <!-- 筛选结果 -->
  <div class="section">
    <h2>筛选结果</h2>
    <div class="sort-controls">
      <input type="text" class="filter-input" id="stockFilter" placeholder="输入代码/名称筛选..." oninput="filterTable()">
      <button onclick="sortTable('score')" class="active">按评分</button>
      <button onclick="sortTable('consensus')">按共识度</button>
      <button onclick="sortTable('code')">按代码</button>
    </div>
    <table id="resultTable">
      <thead>
        <tr>
          <th>市场</th><th>代码</th><th>名称</th><th>评分</th><th>共识度</th>
          <th>命中策略</th><th>K线预览</th>
        </tr>
      </thead>
      <tbody id="tableBody">
        {render_result_rows(results)}
      </tbody>
    </table>
  </div>

  <!-- 行业分布 -->
  <div class="section">
    <h2>行业分布热力图</h2>
    <div class="heatmap" id="heatmap">
      {render_industry_heatmap(results)}
    </div>
  </div>

  <!-- 风险声明 -->
  <div class="section risk">
    <strong>风险声明</strong><br>
    1. 本报告基于东方财富公开行情接口生成（K线备选腾讯/新浪公开通道），数据可能存在3-5分钟延迟，非Level-2实时数据。<br>
    2. 技术形态筛选仅反映历史量价关系，不代表未来走势。<br>
    3. 本报告不构成任何投资建议，也不构成收益承诺。<br>
    4. 所有策略判定逻辑公开透明、可审计复现，详见 scripts/strategies/ 目录。<br>
    5. 数据时效: {report_time}<br>
    6. 股市有风险，投资需谨慎。请结合基本面与自身风险承受能力独立决策。
  </div>

</div>

<script>
// 结果数据
const resultsData = {results_json};

// 排序
let sortKey = 'score';
let sortAsc = false;
function sortTable(key) {{
  sortAsc = (sortKey === key) ? !sortAsc : false;
  sortKey = key;
  document.querySelectorAll('.sort-controls button').forEach(b => b.classList.remove('active'));
  this.classList.add('active');
  renderTable();
}}

// 筛选
function filterTable() {{
  renderTable();
}}

function renderTable() {{
  const filter = (document.getElementById('stockFilter').value || '').toLowerCase();
  let rows = resultsData.filter(r => {{
    const code = String(r.code || '');
    const name = String(r.name || '');
    return code.includes(filter) || name.includes(filter) || filter === '';
  }});
  rows.sort((a, b) => {{
    let va = a[sortKey] || 0;
    let vb = b[sortKey] || 0;
    if (sortKey === 'score') {{ va = va || 0; vb = vb || 0; }}
    if (sortKey === 'consensus') {{ va = (a.strategy_hits || []).length; vb = (b.strategy_hits || []).length; }}
    return sortAsc ? (va > vb ? 1 : -1) : (vb > va ? 1 : -1);
  }});
  const tbody = document.getElementById('tableBody');
  let html = '';
  rows.forEach(r => {{
    const hits = r.strategy_hits || [];
    const score = r.score != null ? r.score.toFixed(1) : '-';
    const consensus = hits.length >= 3 ? '高共识' : (hits.length >= 2 ? '中共识' : '低共识');
    const cls = hits.length >= 3 ? 'consensus-high' : (hits.length >= 2 ? 'consensus-mid' : '');
    html += '<tr class="' + cls + '">';
    html += '<td>' + (r.market || '-') + '</td>';
    html += '<td>' + (r.code || '-') + '</td>';
    html += '<td>' + (r.name || '-') + '</td>';
    html += '<td><strong>' + score + '</strong></td>';
    html += '<td>' + consensus + '</td>';
    html += '<td>' + hits.map(s => '<span class="tag tag-pass">' + s + '</span>').join('') + '</td>';
    html += '<td>' + renderMiniChart(r) + '</td>';
    html += '</tr>';
  }});
  tbody.innerHTML = html || '<tr><td colspan="7" style="text-align:center;color:#999;">无匹配结果</td></tr>';
}}

function renderMiniChart(r) {{
  if (!r.recent_pcts || !r.recent_pcts.length) return '<span style="font-size:11px;color:#999;">无数据</span>';
  const maxAbs = Math.max(...r.recent_pcts.map(Math.abs), 1);
  return '<div class="mini-chart">' + r.recent_pcts.map(v => {{
    const cls = v >= 0 ? 'mini-bar-up' : 'mini-bar-down';
    const h = Math.max(Math.abs(v) / maxAbs * 25, 2);
    return '<div class="mini-bar ' + cls + '" style="height:' + h + 'px" title="' + v.toFixed(1) + '%"></div>';
  }}).join('') + '</div>';
}}

renderTable();
</script>

</body>
</html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


def render_env_badge(market_env: dict) -> str:
    """渲染大盘环境状态徽章（多头/震荡/空头）。"""
    if not market_env:
        return ""
    env = market_env.get("environment", "未知")
    factor = market_env.get("factor", 1.0)
    cls = {"多头": "badge-bull", "空头": "badge-bear"}.get(env, "badge-flat")
    detail = escape(market_env.get("detail", ""))
    return (
        f'<span class="badge {cls}">市场状态: {env}（系数 {factor:.2f}）</span>'
        f'<span style="font-size:12px;color:#666;">{detail}</span>'
    )


def render_env_signals(market_env: dict) -> str:
    """渲染指数信号表格（均线结构/短期动量/量能）。"""
    if not market_env:
        return ""
    signals = market_env.get("signals", {})
    if not signals:
        return ""
    rows = []
    for code, sig in signals.items():
        mom = sig.get("momentum_5d")
        mom_str = f"{mom:+.2f}%" if mom is not None else "-"
        rows.append(
            f'<tr>'
            f'<td>{escape(sig.get("name", code))}</td>'
            f'<td>MA{sig.get("direction", "-")}</td>'
            f'<td>{mom_str}</td>'
            f'<td>{escape(sig.get("volume_note", "-"))}'
            f'{" (" + str(sig.get("volume_ratio")) + "x)" if sig.get("volume_ratio") is not None else ""}</td>'
            f'</tr>'
        )
    breadth = market_env.get("breadth")
    breadth_html = ""
    if breadth:
        breadth_html = (
            f'<div style="font-size:12px;color:#666;margin-top:8px;">'
            f'市场宽度: 上涨 {breadth["up"]} / 下跌 {breadth["down"]} / 平 {breadth["flat"]}'
            f'（上涨占比 {breadth["ratio"] * 100:.1f}%）</div>'
        )
    return (
        '<table class="sig-table">'
        '<thead><tr><th>指数</th><th>均线结构</th><th>近5日动量</th><th>量能</th></tr></thead>'
        '<tbody>' + "".join(rows) + "</tbody></table>" + breadth_html
    )


def render_trend_outlook(market_env: dict) -> str:
    """渲染市场趋势推演（条件式表述）。"""
    if not market_env:
        return '<div style="font-size:12px;color:#999;">暂无大盘数据，无法推演</div>'
    outlook = market_env.get("outlook", [])
    if not outlook:
        return '<div style="font-size:12px;color:#999;">暂无可用信号，无法推演</div>'
    items = []
    for it in outlook:
        items.append(
            f'<div class="outlook-item">'
            f'<span class="ot-kind">[{escape(it.get("kind", ""))}] {escape(it.get("name", ""))}</span>'
            f' <span style="color:#666;">（{escape(it.get("signal", ""))}）</span><br>'
            f'{escape(it.get("outlook", ""))}'
            f'</div>'
        )
    return (
        "".join(items)
        + '<div class="outlook-note">'
        + "推演基于实时指数信号与板块涨幅排行，为条件式结构描述（若…则…），不构成涨跌承诺与投资建议。</div>"
    )


def render_backtest(backtest_data: dict) -> str:
    """渲染策略历史回测结果（真实K线信号回放）。"""
    if not backtest_data:
        return '<div style="font-size:12px;color:#999;">未启用历史回测（使用 --backtest 参数开启）</div>'

    sections = []
    for market, info in backtest_data.items():
        strategies = info.get("strategies", [])
        rows = []
        for st in strategies:
            h5 = (st.get("hold_days") or {}).get(5)
            h20 = (st.get("hold_days") or {}).get(20)

            def _cell(h):
                if not h:
                    return '<td>-</td><td>-</td>'
                wr = h.get("win_rate")
                wr_html = (
                    f'<span class="bt-win">{wr * 100:.1f}%</span>'
                    if wr is not None and wr >= 0.5
                    else (f'<span class="bt-lose">{wr * 100:.1f}%</span>' if wr is not None else "样本不足")
                )
                avg = f"{h.get('avg_return', 0) * 100:+.2f}%" if h.get("avg_return") is not None else "-"
                return f"<td>{wr_html}</td><td>{avg}</td>"

            src = "当前估值快照" if st.get("snapshot_bias") else "历史重放"
            rows.append(
                f'<tr>'
                f'<td>{escape(st.get("strategy_id", "-"))}</td>'
                f'<td>{escape(st.get("name", "-"))}</td>'
                f'<td>{st.get("stocks_covered", 0)}</td>'
                + _cell(h5) + _cell(h20) +
                f'<td>{src}</td>'
                f'</tr>'
            )
        sections.append(
            f'<h3 style="font-size:14px;color:#1a237e;margin:10px 0 6px;">{escape(market)}</h3>'
            f'<table>'
            f'<thead><tr><th>策略</th><th>名称</th><th>覆盖标的</th>'
            f'<th>5日胜率</th><th>5日均收益</th><th>20日胜率</th><th>20日均收益</th><th>信号来源</th></tr></thead>'
            f'<tbody>{"".join(rows) or "<tr><td colspan=8 style=\'text-align:center;color:#999;\'>无有效回测样本</td></tr>"}'
            f'</tbody></table>'
        )

    return (
        "".join(sections)
        + '<div class="bt-note">'
        + "口径：技术面策略在历史K线上逐日完整重放（无前视偏差）；估值策略使用当前估值快照，不作为历史胜率依据。"
        + "回测基于仍在交易标的的历史K线，存在幸存者偏差；胜率为历史统计，不代表未来收益，不构成投资建议。</div>"
    )


def render_dashboard(market_env: dict) -> str:
    """渲染大盘指数卡片。"""
    if not market_env:
        return '<div class="index-card"><div class="name">暂无大盘数据</div></div>'

    indices = market_env.get("indices", {})
    if not indices:
        return '<div class="index-card"><div class="name">暂无大盘数据</div></div>'

    cards = []
    for code, info in indices.items():
        pct = info.get("pct_change", 0)
        pct_str = f"{pct:+.2f}%"
        pct_cls = "up" if pct > 0 else ("down" if pct < 0 else "")
        cards.append(
            f'<div class="index-card">'
            f'<div class="name">{info.get("name", code)}</div>'
            f'<div class="price">{info.get("price", 0):.2f}</div>'
            f'<div class="pct {pct_cls}">{pct_str}</div>'
            f'</div>'
        )
    return "".join(cards)


def render_strategy_stats(strategy_stats: dict, total: int) -> str:
    """渲染策略通过率统计条。"""
    if not strategy_stats:
        return '<div style="font-size:12px;color:#999;">暂无策略统计数据</div>'

    bars = []
    for name, info in sorted(strategy_stats.items()):
        passed = info.get("passed", 0)
        s_total = info.get("total", total) or 1
        ratio = passed / s_total * 100 if s_total > 0 else 0
        bars.append(
            f'<div class="strategy-bar">'
            f'<div class="strategy-name">{name}</div>'
            f'<div class="strategy-track">'
            f'<div class="strategy-fill" style="width:{ratio:.0f}%"></div>'
            f'</div>'
            f'<div class="strategy-val">{passed}/{s_total} ({ratio:.0f}%)</div>'
            f'</div>'
        )
    return "".join(bars)


def render_result_rows(results: list[dict]) -> str:
    """渲染筛选结果表格行。"""
    if not results:
        return '<tr><td colspan="7" style="text-align:center;color:#999;">暂无标的通过筛选</td></tr>'

    rows = []
    for r in results:
        hits = r.get("strategy_hits", [])
        score = r.get("score", 0)
        consensus = "高共识" if len(hits) >= 3 else ("中共识" if len(hits) >= 2 else "低共识")
        cls = "consensus-high" if len(hits) >= 3 else ("consensus-mid" if len(hits) >= 2 else "")
        tags = "".join(f'<span class="tag tag-pass">{escape(s)}</span>' for s in hits)
        # K线迷你图
        mini = render_mini_chart_html(r)
        rows.append(
            f'<tr class="{cls}">'
            f'<td>{escape(str(r.get("market", "-")))}</td>'
            f'<td>{escape(str(r.get("code", "-")))}</td>'
            f'<td>{escape(str(r.get("name", "-")))}</td>'
            f'<td><strong>{score:.1f}</strong></td>'
            f'<td>{consensus}</td>'
            f'<td>{tags}</td>'
            f'<td>{mini}</td>'
            f'</tr>'
        )
    return "".join(rows)


def render_mini_chart_html(r: dict) -> str:
    """渲染K线迷你柱状图。"""
    pcts = r.get("recent_pcts", [])
    if not pcts:
        return '<span style="font-size:11px;color:#999;">无数据</span>'
    max_abs = max(max(abs(v) for v in pcts), 1)
    bars = []
    for v in pcts[-20:]:  # 最多显示最近20根
        cls = "mini-bar-up" if v >= 0 else "mini-bar-down"
        h = max(abs(v) / max_abs * 25, 2)
        bars.append(f'<div class="mini-bar {cls}" style="height:{h:.0f}px" title="{v:.1f}%"></div>')
    return f'<div class="mini-chart">{"".join(bars)}</div>'


def render_industry_heatmap(results: list[dict]) -> str:
    """渲染行业分布热力图。"""
    if not results:
        return '<div style="font-size:12px;color:#999;">暂无数据</div>'

    industry_map = {}
    for r in results:
        ind = r.get("industry", "未知")
        industry_map[ind] = industry_map.get(ind, 0) + 1

    max_count = max(industry_map.values()) if industry_map else 1
    colors = [
        ("#e3f2fd", "#1565c0"), ("#bbdefb", "#1976d2"), ("#90caf9", "#1e88e5"),
        ("#64b5f6", "#2196f3"), ("#42a5f5", "#1e88e5"), ("#2196f3", "#1565c0"),
    ]

    cells = []
    for i, (ind, cnt) in enumerate(sorted(industry_map.items(), key=lambda x: x[1], reverse=True)):
        ratio = cnt / max_count
        idx = min(int(ratio * (len(colors) - 1)), len(colors) - 1)
        bg, fg = colors[idx]
        cells.append(
            f'<div class="heat-cell" style="background:{bg};color:{fg};">'
            f'{ind}: {cnt}只</div>'
        )

    return "".join(cells)
