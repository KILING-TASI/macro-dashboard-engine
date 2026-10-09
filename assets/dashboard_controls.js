/* Original view controls. MIT applies to this file; embedded data keeps its own rights. */
const MacroView = (() => {
  const VERSION = '1.0.0';
  function monthNumber(value) {
    const text = String(value || '');
    let match = /^(\d{4})-?Q([1-4])$/.exec(text);
    if (match) return Number(match[1]) * 12 + (Number(match[2]) - 1) * 3;
    match = /^(\d{4})-(\d{2})(?:-\d{2})?$/.exec(text);
    if (!match || Number(match[2]) < 1 || Number(match[2]) > 12) return null;
    return Number(match[1]) * 12 + Number(match[2]) - 1;
  }
  function monthText(number) {
    return `${Math.floor(number / 12)}-${String(number % 12 + 1).padStart(2, '0')}`;
  }
  function rangeFor(mode, from, to, anchor) {
    if (mode === 'all') return {from: null, to: null};
    if (mode === 'custom') {
      const lo = monthNumber(from), hi = monthNumber(to);
      if ((from && lo === null) || (to && hi === null) || (lo !== null && hi !== null && lo > hi))
        throw new Error('起止月份无效，请检查窗口。');
      return {from: from || null, to: to || null};
    }
    if (!['12', '36'].includes(mode) || monthNumber(anchor) === null)
      throw new Error('没有可用于该窗口的日期观测。');
    return {from: monthText(monthNumber(anchor) - Number(mode) + 1), to: anchor};
  }
  function indicesInWindow(dates, range) {
    const lo = monthNumber(range.from), hi = monthNumber(range.to);
    return dates.reduce((indices, date, index) => {
      const month = monthNumber(date);
      if (month !== null && (lo === null || month >= lo) && (hi === null || month <= hi)) indices.push(index);
      return indices;
    }, []);
  }
  function sourceName(row) {
    if (row.missing) return '未取得';
    if (row.source_url && /^https?:\/\//.test(row.source_url)) {
      try { return new URL(row.source_url).hostname; } catch (_) { /* keep provider */ }
    }
    return row.provider || '未登记';
  }
  function states(row) {
    if (row.missing) return ['missing'];
    const result = [row.sample ? 'sample' : 'acquired'];
    if (row.stale) result.push('stale');
    if (!row.sample) result.push(row.verification_status === '原文已核验' ? 'verified' : 'unverified');
    return result;
  }
  function filterRows(rows, params) {
    const query = (params.query || '').trim().toLocaleLowerCase();
    return rows.filter(row => (!query || [row.key, row.name, row.producer, row.stage, row.note]
      .some(value => String(value || '').toLocaleLowerCase().includes(query)))
      && (!params.source || sourceName(row) === params.source)
      && (!params.state || states(row).includes(params.state)));
  }
  function sortContributions(rows, mode) {
    const result = rows.map(row => ({...row}));
    if (mode === 'absolute') result.sort((a, b) => {
      const av = Number.isFinite(a.contribution) ? Math.abs(a.contribution) : -Infinity;
      const bv = Number.isFinite(b.contribution) ? Math.abs(b.contribution) : -Infinity;
      return bv - av;
    });
    else result.sort((a, b) => String(a.indicator).localeCompare(String(b.indicator)));
    return result;
  }
  function scenarioObservations(sensitivity, mode) {
    const baseline = sensitivity['1.0'] === undefined ? sensitivity['1'] : sensitivity['1.0'];
    const rows = Object.entries(sensitivity).map(([scale,score])=>({scale,score,
      change:Number.isFinite(score) && Number.isFinite(baseline) ? score-baseline : null}));
    if (mode === 'absolute') rows.sort((a,b)=>(Number.isFinite(b.change)?Math.abs(b.change):-Infinity)
      -(Number.isFinite(a.change)?Math.abs(a.change):-Infinity));
    else rows.sort((a,b)=>Number(a.scale)-Number(b.scale));
    return rows;
  }
  return {VERSION, monthNumber, monthText, rangeFor, indicesInWindow, sourceName, states, filterRows, sortContributions, scenarioObservations};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = MacroView;

if (typeof document !== 'undefined' && document.getElementById('viewControls')) (() => {
  const byId = id => document.getElementById(id);
  const esc = value => String(value == null ? '未取得' : value).replace(/[&<>"']/g,
    c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const sourceLink = row => /^https?:\/\//.test(row.source_url || '')
    ? `<a href="${esc(row.source_url)}" target="_blank" rel="noopener">${esc(MacroView.sourceName(row))}</a>`
    : esc(MacroView.sourceName(row));
  const credit = DATA.credit || {rows: [], gaps: []};
  const creditMap = new Map((credit.rows || []).map(row => [row.key, row]));
  const records = (DATA.evidence.rows || []).map(row => ({...row, stale: Boolean((creditMap.get(row.key) || {}).stale)}));
  const gaps = (credit.gaps || []).map(row => ({...row, missing: true, provider: null,
    producer: null, observed_through: null, source_url: null, sample: false,
    definition_status: '缺失，不补值', verification_status: '未取得'}));
  const allRows = [...records, ...gaps];
  const sourceOptions = [...new Set(allRows.map(MacroView.sourceName))].sort();
  sourceOptions.forEach(source => {
    const option = document.createElement('option'); option.value = source; option.textContent = source;
    byId('viewSource').appendChild(option);
  });
  const charts = [];
  document.querySelectorAll('.chart').forEach(element => {
    const instance = echarts.getInstanceByDom(element);
    if (!instance) return;
    const option = instance.getOption(), axis = (option.xAxis || [])[0];
    if (!axis) return;
    if (axis.type === 'category' && axis.data && axis.data.some(value => MacroView.monthNumber(value) !== null))
      charts.push({element, instance, type: 'category', dates: axis.data.slice()});
    else if (axis.type === 'time') {
      const dates = (option.series || []).flatMap(series => (series.data || []).map(point => Array.isArray(point) ? point[0] : null)).filter(Boolean);
      if (dates.length) charts.push({element, instance, type: 'time', dates});
    }
  });
  const months = charts.flatMap(chart => chart.dates.map(MacroView.monthNumber)).filter(value => value !== null);
  const anchor = months.length ? MacroView.monthText(Math.max(...months)) : null;
  let params = {query: '', source: '', state: '', window: 'all', from: '', to: '', sort: 'name'};
  let activeRange = {from: null, to: null};
  let exportUrl = null;
  let exportCount = 0;
  function readParams() {
    return {query: byId('viewQuery').value, source: byId('viewSource').value, state: byId('viewState').value,
      window: byId('viewWindow').value, from: byId('viewFrom').value, to: byId('viewTo').value, sort: byId('viewSort').value};
  }
  function renderTables() {
    const shown = MacroView.filterRows(allRows, params);
    const names = {sample:'教学样本', acquired:'已取得', missing:'未取得', stale:'滞后', verified:'原文已核验', unverified:'原文未核验'};
    byId('evidenceTable').innerHTML = '<thead><tr>'+['指标','生产机构','获取平台/来源','观测截至','发布日期','获取时间','口径状态','原文核验','数据状态'].map(v=>'<th>'+v+'</th>').join('')+'</tr></thead><tbody>'
      + shown.map(row => '<tr>'+[esc(row.name), esc(row.producer), sourceLink(row), esc(row.observed_through), esc(row.release_date),
        esc(row.fetched_at), esc(row.definition_status), esc(row.sample ? '教学样本' : row.verification_status),
        esc(MacroView.states(row).map(state=>names[state]).join(' / '))].map(value=>'<td>'+value+'</td>').join('')+'</tr>').join('')+'</tbody>';
    const shownKeys = new Set(shown.filter(row=>!row.missing).map(row=>row.key));
    const visibleCredit = (credit.rows || []).filter(row=>shownKeys.has(row.key));
    byId('creditTable').innerHTML = '<thead><tr><th>环节</th><th>指标</th><th>最新值</th><th>日期/频率</th><th>状态</th><th>口径/来源</th></tr></thead><tbody>'
      + visibleCredit.map(row=>'<tr>'+[esc(row.stage),esc(row.name),esc(`${row.value} ${row.unit}`),esc(`${row.date} / ${row.frequency}`),
        row.stale?'滞后':'已取得',esc(row.note)+' '+sourceLink(row)].map(value=>'<td>'+value+'</td>').join('')+'</tr>').join('')+'</tbody>';
    byId('creditGaps').innerHTML = shown.filter(row=>row.missing).map(row=>'<li>'+esc(row.stage)+'：'+esc(row.note)+'（未取得）</li>').join('');
    const components = (((DATA.cycle || {}).merrill_clock || {}).growth_diagnostics || {}).components || [];
    byId('viewContributions').innerHTML = '<thead><tr><th>已有增长维度</th><th>原生频率/连续期数</th><th>归一化分数</th><th>权重</th><th>贡献</th></tr></thead><tbody>'
      + MacroView.sortContributions(components,params.sort).map(row=>'<tr>'+[row.indicator,`${row.frequency} / ${row.n}`,
        row.score,row.weight,row.contribution].map((value,index)=>'<td>'+esc(index>=2 && Number.isFinite(value) ? value.toFixed(4) : value)+'</td>').join('')+'</tr>').join('')+'</tbody>';
    const sensitivity = ((((DATA.cycle || {}).merrill_clock || {}).growth_diagnostics || {}).scale_sensitivity) || {};
    const scenarios = MacroView.scenarioObservations(sensitivity, params.sort);
    byId('viewScenarios').innerHTML = scenarios.length ? '<thead><tr><th>已有尺度假设</th><th>已计算增长分数</th><th>相对1倍尺度的偏移</th></tr></thead><tbody>'
      +scenarios.map(row=>'<tr>'+[row.scale+'倍',row.score,row.change].map(value=>'<td>'+esc(Number.isFinite(value)?value.toFixed(4):value)+'</td>').join('')+'</tr>').join('')+'</tbody>' : '<tbody><tr><td>未取得已有尺度观察；没有新增情景。</td></tr></tbody>';
    byId('viewCount').textContent = `明细显示 ${shown.length}/${allRows.length} 项，其中缺失 ${shown.filter(row=>row.missing).length} 项。排序不构成配置建议。`;
  }
  function updateWindow() {
    charts.forEach(chart => {
      const indices = MacroView.indicesInWindow(chart.dates, activeRange);
      let overlay = chart.element.querySelector('.view-empty');
      if (!indices.length) {
        if (!overlay) { overlay = document.createElement('div'); overlay.className='view-empty'; chart.element.appendChild(overlay); }
        overlay.textContent = '所选窗口内没有观测；未补值。'; return;
      }
      if (overlay) overlay.remove();
      const lo = MacroView.monthNumber(activeRange.from), hi = MacroView.monthNumber(activeRange.to);
      const timestamps = chart.type === 'time' ? chart.dates.map(value=>Date.parse(value)).filter(Number.isFinite) : [];
      const startValue = chart.type === 'category' ? indices[0] : lo === null ? Math.min(...timestamps) : Date.UTC(Math.floor(lo/12),lo%12,1);
      const endValue = chart.type === 'category' ? indices[indices.length-1] : hi === null ? Math.max(...timestamps) : Date.UTC(Math.floor(hi/12),hi%12+1,1)-1;
      chart.instance.setOption({dataZoom:[{id:'macro-view-window', type:'inside', xAxisIndex:0, filterMode:'none',
        rangeMode:['value','value'],startValue,endValue}]},{replaceMerge:['dataZoom']});
    });
    byId('viewWindowNote').textContent = `显示窗口：${activeRange.from || '全部起点'} 至 ${activeRange.to || '全部终点'}；锚点 ${anchor || '未取得'}。只调整日期图表显示，保留原始日期和空值，不重算当前指标或周期结论。`;
  }
  function invalidateExport() {
    if (exportUrl) { URL.revokeObjectURL(exportUrl); exportUrl=null; }
    byId('viewDownload').hidden=true;
    byId('viewArchive').value='';
  }
  byId('viewApply').addEventListener('click',()=> {
    const candidate=readParams();
    try {
      const range=MacroView.rangeFor(candidate.window,candidate.from,candidate.to,anchor);
      params=candidate; activeRange=range; renderTables(); updateWindow(); invalidateExport();
      byId('viewError').textContent='';
    } catch(error) { byId('viewError').textContent=error.message+' 保留上一次有效显示。'; }
  });
  byId('viewReset').addEventListener('click',()=> {
    ['viewQuery','viewSource','viewState','viewFrom','viewTo'].forEach(id=>byId(id).value='');
    byId('viewWindow').value='all'; byId('viewSort').value='name'; byId('viewApply').click();
  });
  byId('viewExport').addEventListener('click', async()=> {
    const payloadText=JSON.stringify(DATA);
    let digest=null;
    if (typeof crypto !== 'undefined' && crypto.subtle) {
      try {
        const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(payloadText));
        digest=Array.from(new Uint8Array(hash)).map(value=>value.toString(16).padStart(2,'0')).join('');
      } catch (_) { /* Keep digest unknown; export the full snapshot anyway. */ }
    }
    const archive={schema_version:'macro-view-1.0.0', controls_version:MacroView.VERSION, saved_at:new Date().toISOString(),
      report_generated_at:byId('reportGeneratedAt').textContent, report_timezone:null, window_anchor:anchor,
      method_version:DATA.cycle.calculation_version || null, observed_through:DATA.cycle.as_of || null,
      data_mode:DATA.offline?'teaching':'formal',
      data_status:DATA.offline?'sample':DATA.data_quality.status==='partial' || credit.status==='partial'?'partial':DATA.data_quality.status,
      parameters:{...params}, resolved_window:{...activeRange},
      chart_views:charts.map(chart=>({id:chart.element.id, window_has_observations:!chart.element.querySelector('.view-empty'),
        data_zoom:chart.element.querySelector('.view-empty') ? null : chart.instance.getOption().dataZoom || [],
        legend:(chart.instance.getOption().legend || []).map(legend=>legend.selected || {})})),
      display_payload_sha256:digest, hash_status:digest?'sha256-of-JSON.stringify-display-payload':'unavailable', display_payload:DATA,
      scope:'Loaded display snapshot and applied view parameters, not raw responses or an online refresh. No rescoring; data rights unchanged.'};
    invalidateExport();
    const text=JSON.stringify(archive,null,2);
    byId('viewArchive').value=text;
    exportUrl=URL.createObjectURL(new Blob([text],{type:'application/json'}));
    byId('viewDownload').href=exportUrl;
    byId('viewDownload').download='macro-view-'+archive.saved_at.replace(/[:.]/g,'-')+'-'+(++exportCount)+'.json';
    byId('viewDownload').hidden=false;
  });
  renderTables(); updateWindow();
})();
