'use strict';

// ==================== Link definitions ====================
let links = [
  {source:1,target:2},{source:2,target:1},{source:1,target:3},{source:3,target:1},
  {source:1,target:4},{source:4,target:1},{source:1,target:9},{source:9,target:1},
  {source:2,target:4},{source:4,target:2},{source:2,target:9},{source:9,target:2},
  {source:3,target:4},{source:4,target:3},{source:3,target:9},{source:9,target:3},
  {source:4,target:5},{source:5,target:4},{source:4,target:6},{source:6,target:4},
  {source:4,target:7},{source:7,target:4},{source:4,target:8},{source:8,target:4},
  {source:4,target:9},{source:9,target:4},{source:4,target:10},{source:10,target:4},
  {source:4,target:11},{source:11,target:4},{source:4,target:15},{source:15,target:4},
  {source:5,target:9},{source:9,target:5},{source:6,target:15},{source:15,target:6},
  {source:7,target:9},{source:9,target:7},{source:8,target:9},{source:9,target:8},
  {source:9,target:10},{source:10,target:9},{source:9,target:15},{source:15,target:9},
  {source:10,target:12},{source:12,target:10},{source:10,target:13},{source:13,target:10},
  {source:10,target:14},{source:14,target:10},{source:10,target:16},{source:16,target:10},
  {source:10,target:17},{source:17,target:10},{source:11,target:15},{source:15,target:11},
  {source:12,target:15},{source:15,target:12},{source:13,target:15},{source:15,target:13},
  {source:14,target:15},{source:15,target:14},{source:15,target:16},{source:16,target:15},
  {source:15,target:17},{source:17,target:15}
].map(l => ({...l, value: 0}));

const linkSet = new Set();
links.forEach(l => linkSet.add(`${l.source}-${l.target}`));

// Track which links are currently shut down
let shutdownLinks = new Set();
// Track links suggested by Reason stage
let pendingLinks = [];

// ==================== Matrix Table ====================
createMatrixTable(17);

function createMatrixTable(N) {
  const thead = document.querySelector('#matrix-table thead');
  const tbody = document.querySelector('#matrix-table tbody');
  thead.innerHTML = ''; tbody.innerHTML = '';

  const hr = document.createElement('tr');
  hr.appendChild(document.createElement('th'));
  for (let i = 1; i <= N; i++) { const th = document.createElement('th'); th.textContent = `S${i}`; hr.appendChild(th); }
  thead.appendChild(hr);

  for (let i = 1; i <= N; i++) {
    const row = document.createElement('tr');
    const rh = document.createElement('th'); rh.textContent = `S${i}`; row.appendChild(rh);
    for (let j = 1; j <= N; j++) {
      const td = document.createElement('td');
      const input = document.createElement('input'); input.type = 'number';
      if (i === j) { input.value = '0'; input.disabled = true; }
      else if (linkSet.has(`${i}-${j}`)) { input.value = Math.floor(Math.random() * 900 + 100); }
      else { input.value = ''; input.disabled = true; }
      td.appendChild(input); row.appendChild(td);
    }
    tbody.appendChild(row);
  }
}

// ==================== Fixed Topology Layout ====================
// Positions roughly matching TANET geography (Taiwan backbone)
const nodePositions = {
  1:  {x: 250, y: 60},   // Taipei area
  2:  {x: 420, y: 80},   // Taipei area
  3:  {x: 100, y: 120},  // Taoyuan/Hsinchu
  9:  {x: 450, y: 230},  // Central hub (east)
  4:  {x: 250, y: 250},  // Central hub (west)
  5:  {x: 580, y: 120},  // East coast
  7:  {x: 620, y: 260},  // East coast
  8:  {x: 620, y: 370},  // East coast
  6:  {x: 80,  y: 350},  // West coast
  11: {x: 80,  y: 480},  // West coast
  15: {x: 300, y: 460},  // South hub (west)
  10: {x: 550, y: 460},  // South hub (east)
  12: {x: 680, y: 540},  // Southeast
  13: {x: 550, y: 580},  // South
  14: {x: 400, y: 600},  // South
  16: {x: 700, y: 650},  // Taitung
  17: {x: 250, y: 680},  // Pingtung/Kaohsiung
};

const nodes = Object.keys(nodePositions).map(id => ({
  id: +id,
  x: nodePositions[id].x,
  y: nodePositions[id].y
}));

// ==================== D3 Topology Rendering ====================
const svg = d3.select('#topo-svg');
const defs = svg.append('defs');

// Gradient for links
const grad = defs.append('linearGradient').attr('id', 'link-grad').attr('gradientUnits', 'userSpaceOnUse');
grad.append('stop').attr('offset', '0%').attr('stop-color', '#3b82f6');
grad.append('stop').attr('offset', '100%').attr('stop-color', '#8b5cf6');

// Glow filter
const glow = defs.append('filter').attr('id', 'glow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
glow.append('feGaussianBlur').attr('stdDeviation', 3).attr('result', 'blur');
const fm = glow.append('feMerge');
fm.append('feMergeNode').attr('in', 'blur');
fm.append('feMergeNode').attr('in', 'SourceGraphic');

const root = svg.append('g').attr('class', 'root');

// Zoom
svg.call(d3.zoom().scaleExtent([0.5, 3]).on('zoom', e => root.attr('transform', e.transform))).on('dblclick.zoom', null);

// Color scale for traffic
const trafficColor = d3.scaleSequential(d3.interpolateRdYlGn).domain([1, 0]); // reversed: high=red, low=green

// Build a map for quick bidirectional link lookup
function biKey(s, t) { return `${Math.min(s,t)}-${Math.max(s,t)}`; }

// Merge bidirectional links for drawing (draw one line per physical link)
function getPhysicalLinks() {
  const seen = new Map();
  links.forEach(l => {
    const key = biKey(l.source, l.target);
    if (!seen.has(key)) seen.set(key, { source: Math.min(l.source, l.target), target: Math.max(l.source, l.target), fwd: 0, rev: 0 });
    const entry = seen.get(key);
    if (l.source < l.target) entry.fwd = l.value; else entry.rev = l.value;
  });
  return Array.from(seen.values());
}

function getNodeById(id) { return nodes.find(n => n.id === id); }

// Draw links
function renderLinks() {
  const pLinks = getPhysicalLinks();
  const maxVal = Math.max(1, d3.max(pLinks, d => Math.max(d.fwd, d.rev)) || 1);

  root.selectAll('.topo-link').remove();
  root.selectAll('.topo-link-label').remove();

  pLinks.forEach(pl => {
    const s = getNodeById(pl.source), t = getNodeById(pl.target);
    if (!s || !t) return;
    const avgTraffic = (pl.fwd + pl.rev) / 2;
    const util = avgTraffic / maxVal;
    const isShutdown = shutdownLinks.has(`S${pl.source}-S${pl.target}`) || shutdownLinks.has(`S${pl.target}-S${pl.source}`);

    const color = isShutdown ? '#475569' : trafficColor(util);
    const width = isShutdown ? 1 : Math.max(1.5, util * 6);
    const dash = isShutdown ? '4,4' : 'none';

    root.append('line')
      .attr('class', 'topo-link')
      .attr('x1', s.x).attr('y1', s.y)
      .attr('x2', t.x).attr('y2', t.y)
      .attr('stroke', color).attr('stroke-width', width)
      .attr('stroke-dasharray', dash).attr('stroke-opacity', isShutdown ? 0.4 : 0.8);

    // Traffic label on the midpoint
    if (!isShutdown && avgTraffic > 0) {
      const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
      root.append('text')
        .attr('class', 'topo-link-label')
        .attr('x', mx).attr('y', my - 4)
        .attr('text-anchor', 'middle')
        .attr('font-size', '9px').attr('fill', '#94a3b8')
        .text(Math.round(avgTraffic));
    }
  });
}

// Draw nodes
function renderNodes() {
  root.selectAll('.topo-node').remove();
  root.selectAll('.topo-node-label').remove();

  nodes.forEach(n => {
    // Determine if this is a hub node
    const degree = links.filter(l => l.source === n.id || l.target === n.id).length / 2;
    const r = Math.max(16, Math.min(28, 12 + degree * 1.2));

    root.append('circle')
      .attr('class', 'topo-node')
      .attr('cx', n.x).attr('cy', n.y).attr('r', r)
      .attr('fill', degree >= 8 ? '#f59e0b' : '#3b82f6')
      .attr('stroke', '#e2e8f0').attr('stroke-width', 2)
      .attr('filter', 'url(#glow)')
      .style('cursor', 'grab')
      .call(d3.drag()
        .on('start', function() { d3.select(this).style('cursor', 'grabbing'); })
        .on('drag', function(event) {
          n.x = event.x; n.y = event.y;
          d3.select(this).attr('cx', n.x).attr('cy', n.y);
          renderLinks(); renderNodeLabels();
        })
        .on('end', function() { d3.select(this).style('cursor', 'grab'); })
      );
  });
  renderNodeLabels();
}

function renderNodeLabels() {
  root.selectAll('.topo-node-label').remove();
  nodes.forEach(n => {
    root.append('text')
      .attr('class', 'topo-node-label')
      .attr('x', n.x).attr('y', n.y + 4)
      .attr('text-anchor', 'middle')
      .attr('font-size', '12px').attr('font-weight', 'bold').attr('fill', '#fff')
      .style('pointer-events', 'none')
      .text(`S${n.id}`);
  });
}

function renderTopology() {
  renderLinks();
  renderNodes();
}
renderTopology();

// ==================== Data Fetching ====================
async function fetchLatestTraffic() {
  const overlay = document.getElementById('graph-loading');
  try {
    if (overlay) overlay.style.display = 'flex';
    const resp = await fetch('/api/fetch', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    const result = await resp.json();
    if (!result.success) { console.error('Fetch failed:', result.message); return; }
    const raw = result.data;

    // Update matrix table
    const rows = document.querySelector('#matrix-table tbody').getElementsByTagName('tr');
    for (let i = 0; i < rows.length; i++) {
      const cells = rows[i].getElementsByTagName('td');
      for (let j = 0; j < cells.length; j++) {
        const input = cells[j].querySelector('input');
        const key = `S${i+1}-S${j+1}`;
        if (input && !input.disabled && raw[key] !== undefined) input.value = raw[key];
      }
    }

    // Update link values
    links.forEach(l => {
      const key = `S${l.source}-S${l.target}`;
      l.value = raw[key] || 0;
    });

    renderTopology();
  } catch (e) { console.error('Fetch error:', e); }
  finally { if (overlay) overlay.style.display = 'none'; }
}

// ==================== Stage 1: Reason (get strategy) ====================
function submitMatrix() {
  const rows = document.querySelector('#matrix-table tbody').getElementsByTagName('tr');
  const matrix = [];
  const hostNames = Array.from({ length: 17 }, (_, i) => `h${i + 1}`);

  for (let i = 0; i < rows.length; i++) {
    const cells = rows[i].getElementsByTagName('td');
    const rv = [];
    for (let j = 0; j < cells.length; j++) {
      const input = cells[j].querySelector('input');
      rv.push(input ? parseInt(input.value, 10) || 0 : 0);
    }
    matrix.push(rv);
  }

  const userNote = document.getElementById('user-note')?.value?.trim() || '';
  const payload = { hosts: hostNames, matrix, user_note: userNote };

  const loading = document.getElementById('loading');
  const resultEl = document.getElementById('evaluation-result');
  const actPanel = document.getElementById('act-panel');
  if (loading) loading.style.display = 'block';
  if (resultEl) resultEl.textContent = '';
  if (actPanel) actPanel.style.display = 'none';

  fetch('/api/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    .then(r => { if (!r.ok) throw new Error('Submit failed'); return r.json(); })
    .then(data => {
      const evalResult = data['evaluation_result'] || 'No result';
      if (resultEl) resultEl.textContent = evalResult;

      // Extract links to close from the result text (parse "S\d+-S\d+" patterns from commands)
      const linkPattern = /S\d+-S\d+/g;
      const foundLinks = evalResult.match(linkPattern) || [];
      // Deduplicate and pair bidirectional
      const linkPairs = new Set();
      foundLinks.forEach(l => {
        linkPairs.add(l);
        const [s, t] = l.split('-');
        linkPairs.add(`${t}-${s}`);
      });
      pendingLinks = Array.from(linkPairs);

      // Show Act panel (HOTL Stage 2)
      if (pendingLinks.length > 0) {
        const preview = document.getElementById('act-links-preview');
        const uniquePhysical = new Set();
        pendingLinks.forEach(l => {
          const [s, t] = l.split('-');
          uniquePhysical.add(`${Math.min(+s.slice(1), +t.slice(1))}-${Math.max(+s.slice(1), +t.slice(1))}`);
        });
        preview.innerHTML = `<b>Suggested ${uniquePhysical.size} physical links to shutdown:</b><br>` +
          pendingLinks.filter((_, i) => i % 2 === 0).map(l => `  ${l} (bidirectional)`).join('<br>');
        actPanel.style.display = 'block';
        document.getElementById('act-result').textContent = '';
      }

      if (historyModalOpen) fetchHistory(historyState.page, historyState.pageSize);
    })
    .catch(err => { console.error(err); alert('Error: ' + err.message); })
    .finally(() => { if (loading) loading.style.display = 'none'; });
}

// ==================== Stage 2: Act (HOTL execute) ====================
async function executeAct(dryRun) {
  const actResult = document.getElementById('act-result');
  actResult.className = 'act-result';
  actResult.textContent = dryRun ? 'Simulating (dry run)...' : 'Executing shutdown...';

  try {
    const resp = await fetch('/api/act', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ links: pendingLinks, dry_run: dryRun })
    });
    const data = await resp.json();

    const lines = [];
    lines.push(dryRun ? '=== DRY RUN RESULT ===' : '=== EXECUTION RESULT ===');
    lines.push(`Status: ${data.status}`);
    lines.push(`Total: ${data.summary?.total}, Success: ${data.summary?.success}, Error: ${data.summary?.error}`);
    lines.push('');
    (data.act_results || []).forEach(r => {
      lines.push(`  ${r.link}: ${r.status} - ${r.detail}`);
    });

    actResult.textContent = lines.join('\n');
    actResult.className = 'act-result ' + (data.summary?.error > 0 ? 'error' : 'success');

    // Update topology visualization
    if (!dryRun && data.summary?.success > 0) {
      pendingLinks.forEach(l => shutdownLinks.add(l));
      renderTopology();
    }
  } catch (e) {
    actResult.textContent = 'Error: ' + e.message;
    actResult.className = 'act-result error';
  }
}

async function restoreLinks() {
  if (shutdownLinks.size === 0 && pendingLinks.length === 0) {
    alert('No links to restore'); return;
  }
  const linksToRestore = Array.from(new Set([...shutdownLinks, ...pendingLinks]));
  const actResult = document.getElementById('act-result');
  actResult.textContent = 'Restoring links...';

  try {
    const resp = await fetch('/api/act/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ links: linksToRestore })
    });
    const data = await resp.json();
    actResult.textContent = `Restored: ${data.summary?.success}/${data.summary?.total} links`;
    actResult.className = 'act-result success';
    shutdownLinks.clear();
    renderTopology();
  } catch (e) {
    actResult.textContent = 'Restore error: ' + e.message;
    actResult.className = 'act-result error';
  }
}

// ==================== History Modal ====================
let historyModalOpen = false;
const historyState = { page: 1, pageSize: 10, total: 0 };

function openHistoryModal() {
  historyModalOpen = true;
  document.getElementById('history-modal').style.display = 'flex';
  document.getElementById('prev-page').onclick = () => { if (historyState.page > 1) fetchHistory(historyState.page - 1, historyState.pageSize); };
  document.getElementById('next-page').onclick = () => { const tp = Math.max(1, Math.ceil(historyState.total / historyState.pageSize)); if (historyState.page < tp) fetchHistory(historyState.page + 1, historyState.pageSize); };
  document.getElementById('page-size').onchange = e => fetchHistory(1, parseInt(e.target.value, 10) || 10);
  fetchHistory(1, historyState.pageSize);
}
function closeHistoryModal() { historyModalOpen = false; document.getElementById('history-modal').style.display = 'none'; }

async function fetchHistory(page = 1, pageSize = 10) {
  const list = document.getElementById('history-list');
  const detail = document.getElementById('history-detail');
  try {
    list.textContent = 'Loading...';
    const res = await fetch(`/api/history?page=${page}&page_size=${pageSize}`);
    const data = await res.json();
    if (data.status !== 'ok') { list.textContent = 'Load failed'; return; }
    historyState.page = data.page; historyState.pageSize = data.page_size; historyState.total = data.total;
    const items = data.items || [];
    if (!items.length) { list.textContent = 'No records'; detail.textContent = ''; updatePager(); return; }
    list.innerHTML = '';
    items.forEach(item => {
      const row = document.createElement('div'); row.className = 'history-row';
      row.innerHTML = `<div><b>#${item.id}</b> <small>${item.created_at}</small></div><div style="color:#64748b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(item.user_note || '(no note)')}</div>`;
      row.addEventListener('click', () => fetchHistoryOne(item.id));
      list.appendChild(row);
    });
    fetchHistoryOne(items[0].id);
    updatePager();
  } catch (e) { console.error(e); list.textContent = 'Error'; }
}

function updatePager() {
  const tp = Math.max(1, Math.ceil(historyState.total / historyState.pageSize));
  document.getElementById('page-info').textContent = `Page ${historyState.page}/${tp} (${historyState.total} total)`;
  document.getElementById('prev-page').disabled = historyState.page <= 1;
  document.getElementById('next-page').disabled = historyState.page >= tp;
}

async function fetchHistoryOne(id) {
  const detail = document.getElementById('history-detail');
  detail.textContent = 'Loading...';
  try {
    const res = await fetch(`/api/history/${id}`);
    const data = await res.json();
    if (data.status !== 'ok') { detail.textContent = 'Load failed'; return; }
    const it = data.item;
    detail.textContent = [`#${it.id}  @ ${it.created_at}`, '', 'User Note:', it.user_note || '(none)', '', 'Result:', it.evaluation_result || '(none)'].join('\n');
  } catch (e) { detail.textContent = 'Error'; }
}

function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

// Expose to HTML onclick
window.fetchLatestTraffic = fetchLatestTraffic;
window.submitMatrix = submitMatrix;
window.executeAct = executeAct;
window.restoreLinks = restoreLinks;
window.openHistoryModal = openHistoryModal;
window.closeHistoryModal = closeHistoryModal;
