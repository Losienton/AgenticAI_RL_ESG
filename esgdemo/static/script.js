'use strict';

// ---------- Link list (initial edges with zero traffic) ----------
let links = [
  { source: 1, target: 2, value: 0 }, { source: 2, target: 1, value: 0 },
  { source: 1, target: 3, value: 0 }, { source: 3, target: 1, value: 0 },
  { source: 1, target: 4, value: 0 }, { source: 4, target: 1, value: 0 },
  { source: 1, target: 9, value: 0 }, { source: 9, target: 1, value: 0 },
  { source: 2, target: 4, value: 0 }, { source: 4, target: 2, value: 0 },
  { source: 2, target: 9, value: 0 }, { source: 9, target: 2, value: 0 },
  { source: 3, target: 4, value: 0 }, { source: 4, target: 3, value: 0 },
  { source: 3, target: 9, value: 0 }, { source: 9, target: 3, value: 0 },
  { source: 4, target: 5, value: 0 }, { source: 5, target: 4, value: 0 },
  { source: 4, target: 6, value: 0 }, { source: 6, target: 4, value: 0 },
  { source: 4, target: 7, value: 0 }, { source: 7, target: 4, value: 0 },
  { source: 4, target: 8, value: 0 }, { source: 8, target: 4, value: 0 },
  { source: 4, target: 9, value: 0 }, { source: 9, target: 4, value: 0 },
  { source: 4, target: 10, value: 0 }, { source: 10, target: 4, value: 0 },
  { source: 4, target: 11, value: 0 }, { source: 11, target: 4, value: 0 },
  { source: 4, target: 15, value: 0 }, { source: 15, target: 4, value: 0 },
  { source: 5, target: 9, value: 0 },  { source: 9, target: 5, value: 0 },
  { source: 6, target: 15, value: 0 }, { source: 15, target: 6, value: 0 },
  { source: 7, target: 9, value: 0 },  { source: 9, target: 7, value: 0 },
  { source: 8, target: 9, value: 0 },  { source: 9, target: 8, value: 0 },
  { source: 9, target: 10, value: 0 }, { source: 10, target: 9, value: 0 },
  { source: 9, target: 15, value: 0 }, { source: 15, target: 9, value: 0 },
  { source: 10, target: 12, value: 0 }, { source: 12, target: 10, value: 0 },
  { source: 10, target: 13, value: 0 }, { source: 13, target: 10, value: 0 },
  { source: 10, target: 14, value: 0 }, { source: 14, target: 10, value: 0 },
  { source: 10, target: 15, value: 0 }, { source: 15, target: 10, value: 0 },
  { source: 10, target: 16, value: 0 }, { source: 16, target: 10, value: 0 },
  { source: 10, target: 17, value: 0 }, { source: 17, target: 10, value: 0 },
  { source: 11, target: 15, value: 0 }, { source: 15, target: 11, value: 0 },
  { source: 12, target: 15, value: 0 }, { source: 15, target: 12, value: 0 },
  { source: 13, target: 15, value: 0 }, { source: 15, target: 13, value: 0 },
  { source: 14, target: 15, value: 0 }, { source: 15, target: 14, value: 0 },
  { source: 15, target: 16, value: 0 }, { source: 16, target: 15, value: 0 },
  { source: 15, target: 17, value: 0 }, { source: 17, target: 15, value: 0 }
];

// 快速檢查某對節點是否為可用邊
const linkSet = new Set();
links.forEach(link => linkSet.add(`${link.source}-${link.target}`));

// 建好 17x17 的矩陣表
createMatrixTable(17);

function createMatrixTable(N) {
  const table = document.getElementById('matrix-table');
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');

  thead.innerHTML = '';
  tbody.innerHTML = '';

  const headerRow = document.createElement('tr');
  headerRow.appendChild(document.createElement('th'));
  for (let i = 1; i <= N; i++) {
    const th = document.createElement('th');
    th.textContent = `S${i}`;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);

  for (let i = 1; i <= N; i++) {
    const row = document.createElement('tr');
    const rowHeader = document.createElement('th');
    rowHeader.textContent = `S${i}`;
    row.appendChild(rowHeader);

    for (let j = 1; j <= N; j++) {
      const td = document.createElement('td');
      const input = document.createElement('input');
      input.type = 'number';

      if (i === j) {
        input.value = '0';
        input.disabled = true;
      } else {
        const hasLink = linkSet.has(`${i}-${j}`);
        if (hasLink) {
          const randomNumber = Math.floor(Math.random() * (1000 - 100 + 1)) + 100;
          input.value = randomNumber;
          input.disabled = false;
        } else {
          input.value = '';
          input.disabled = true;
        }
      }
      td.appendChild(input);
      row.appendChild(td);
    }
    tbody.appendChild(row);
  }
}

// ---------- D3 Graph (animated) ----------
const svg = d3.select('svg');
const { width, height } = svg.node().getBoundingClientRect();

// Root group for zoom/pan
const root = svg.append('g').attr('class', 'root');

// Defs: arrow + glow
const defs = svg.append('defs');

// Arrow: red (from smaller id to larger id)
defs.append('marker')
  .attr('id', 'arrow-red')
  .attr('viewBox', '0 -5 10 10')
  .attr('refX', 22)
  .attr('refY', 0)
  .attr('markerWidth', 6)
  .attr('markerHeight', 6)
  .attr('orient', 'auto')
  .append('path')
  .attr('d', 'M0,-5L10,0L0,5')
  .attr('fill', 'red');

// Arrow: black (from larger id to smaller id)
defs.append('marker')
  .attr('id', 'arrow-black')
  .attr('viewBox', '0 -5 10 10')
  .attr('refX', 22)
  .attr('refY', 0)
  .attr('markerWidth', 6)
  .attr('markerHeight', 6)
  .attr('orient', 'auto')
  .append('path')
  .attr('d', 'M0,-5L10,0L0,5')
  .attr('fill', 'black');

// Glow
const glow = defs.append('filter').attr('id', 'glow');
glow.append('feGaussianBlur').attr('stdDeviation', 3).attr('result', 'coloredBlur');
const feMerge = glow.append('feMerge');
feMerge.append('feMergeNode').attr('in', 'coloredBlur');
feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

// Zoom/pan
svg.call(
  d3.zoom()
    .scaleExtent([0.4, 2.5])
    .on('zoom', (event) => root.attr('transform', event.transform))
).on('dblclick.zoom', null);

// Groups
let linkGroup = root.append('g').attr('class', 'links');
let labelGroup = root.append('g').attr('class', 'labels');
const nodeGroup = root.append('g').attr('class', 'nodes');
const ringGroup = root.append('g').attr('class', 'rings');

// Nodes from link endpoints
const nodes = Array.from(new Set(links.flatMap(l => [l.source, l.target]))).map(id => ({ id }));

// Scales for link width/color by traffic
function currentMaxValue() {
  const m = d3.max(links, d => +d.value || 0);
  return Math.max(1, m || 1);
}
let widthScale = d3.scaleSqrt().domain([0, currentMaxValue()]).range([1.5, 10]);
let colorScale = d3.scaleSequential(d3.interpolateTurbo).domain([0, currentMaxValue()]);

// Force layout
const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink().id(d => d.id).distance(320))
  .force('charge', d3.forceManyBody().strength(-2000))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide().radius(60))
  .velocityDecay(0.35);

// Node circles
const node = nodeGroup.selectAll('circle.node')
  .data(nodes)
  .join('circle')
  .attr('class', 'node')
  .attr('r', 40)
  .attr('fill', 'lightblue')
  .call(drag(simulation));

// Node labels (larger font)
const nodeLabels = nodeGroup.selectAll('text.node-label')
  .data(nodes)
  .join('text')
  .attr('class', 'node-label')
  .attr('dy', 5)
  .attr('text-anchor', 'middle')
  .style('font-weight', 'bold')
  .style('font-size', '32px')
  .text(d => d.id);

// Node pulse rings
const nodeRings = ringGroup.selectAll('circle.node-ring')
  .data(nodes)
  .join('circle')
  .attr('class', 'node-ring')
  .attr('r', 46);

// Links and labels selections
let linkSel = linkGroup.selectAll('path.link');
let labelSel = labelGroup.selectAll('text.link-label');

function linkKey(d) {
  const s = (typeof d.source === 'object') ? d.source.id : d.source;
  const t = (typeof d.target === 'object') ? d.target.id : d.target;
  return `${s}-${t}`;
}

function curvedPath(d) {
  const sx = d.source.x, sy = d.source.y;
  const tx = d.target.x, ty = d.target.y;
  const dx = tx - sx, dy = ty - sy;
  const dr = Math.sqrt(dx*dx + dy*dy);
  const normX = -dy / (dr || 1);
  const normY = dx / (dr || 1);
  const curve = Math.min(60, dr * 0.2);
  const cx = (sx + tx) / 2 + normX * curve;
  const cy = (sy + ty) / 2 + normY * curve;
  return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`;
}

function animateFlow(path, speed = 1200) {
  const length = path.getTotalLength();
  d3.select(path)
    .attr('stroke-dasharray', `${length / 8} ${length / 8}`)
    .attr('stroke-dashoffset', length)
    .transition()
    .duration(speed)
    .ease(d3.easeLinear)
    .attr('stroke-dashoffset', 0)
    .on('end', () => animateFlow(path, speed));
}

function tweenText(sel, newVal) {
  sel.transition().duration(500).tween('text', function() {
    const el = d3.select(this);
    const v0 = +el.text() || 0;
    const i = d3.interpolateNumber(v0, +newVal || 0);
    return t => el.text(Math.round(i(t)));
  });
}

function pulseNode(d) {
  const r = d3.select(this);
  r.raise()
   .attr('opacity', 0.35)
   .transition().duration(700)
     .attr('r', 80)
     .attr('opacity', 0.0)
   .transition().duration(0)
     .attr('r', 46);
}

function styleLinks() {
  const m = currentMaxValue();
  widthScale.domain([0, m]);
  colorScale.domain([0, m]);

  linkSel
    .attr('stroke-width', d => widthScale(+d.value || 0))
    .attr('stroke', d => {
      const s = (typeof d.source === 'object') ? d.source.id : d.source;
      const t = (typeof d.target === 'object') ? d.target.id : d.target;
      return s < t ? 'red' : 'black';
    });

  labelSel
    .style('fill', d => {
      const s = (typeof d.source === 'object') ? d.source.id : d.source;
      const t = (typeof d.target === 'object') ? d.target.id : d.target;
      return s < t ? 'red' : 'black';
    })
    .attr('dy', d => {
      const s = (typeof d.source === 'object') ? d.source.id : d.source;
      const t = (typeof d.target === 'object') ? d.target.id : d.target;
      // 調整文字在曲線上方/下方，避免看起來上下顛倒
      return s < t ? -10 : 16;
    });
}

// --- Hide/show isolated nodes ---
function getActiveNodeIds() {
  const active = new Set();
  links.forEach(l => {
    const s = (typeof l.source === 'object') ? l.source.id : l.source;
    const t = (typeof l.target === 'object') ? l.target.id : l.target;
    active.add(s); active.add(t);
  });
  return active;
}

function updateNodeVisibility() {
  const active = getActiveNodeIds();
  node.style('display', d => active.has(d.id) ? null : 'none');
  nodeLabels.style('display', d => active.has(d.id) ? null : 'none');
  nodeRings.style('display', d => active.has(d.id) ? null : 'none');
}

function idFor(d){
  const s = (typeof d.source === 'object') ? d.source.id : d.source;
  const t = (typeof d.target === 'object') ? d.target.id : d.target;
  return `link-${s}-${t}`;
}

function refreshLinks() {
  linkSel = linkSel
    .data(links, d => linkKey(d))
    .join(
      enter => enter.append('path')
        .attr('class', 'link')
        .attr('id', d => idFor(d))
        .attr('fill', 'none')
        .attr('stroke-linecap', 'round')
        .attr('d', d => `M${d.source.x || width/2},${d.source.y || height/2} L${d.target.x || width/2},${d.target.y || height/2}`)
        .each(function() { animateFlow(this, 2000); }),
      update => update,
      exit => exit.transition().duration(250).style('opacity', 0).remove()
    );

  labelSel = labelSel
    .data(links, d => linkKey(d))
    .join(
      enter => {
        const t = enter.append('text')
          .attr('class', 'link-label')
          .attr('text-anchor', 'middle')
          .style('font-size', '24px')
          .style('font-weight', '700')
          .style('pointer-events', 'none');

        t.append('textPath')
          .attr('href', d => `#${idFor(d)}`)
          .attr('startOffset', '50%')
          .attr('dominant-baseline', 'middle')
          .text(d => Math.round(+d.value || 0));

        return t;
      },
      update => update,
      exit => exit.remove()
    );

  styleLinks();
  simulation.force('link').links(links);
  simulation.alpha(0.8).restart();
  updateNodeVisibility();
}

refreshLinks();

simulation.on('tick', () => {
  const radius = 15;
  const padding = 20;

  node
    .attr('cx', d => d.x = Math.max(radius + padding, Math.min(width - radius - padding, d.x)))
    .attr('cy', d => d.y = Math.max(radius + padding, Math.min(height - radius - padding, d.y)));

  nodeLabels
    .attr('x', d => d.x)
    .attr('y', d => d.y);

  nodeRings
    .attr('cx', d => d.x)
    .attr('cy', d => d.y);

  linkSel.attr('d', d => curvedPath(d));
});

function drag(simulation) {
  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x; d.fy = d.y;
  }
  function dragged(event, d) {
    d.fx = event.x; d.fy = event.y;
  }
  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null; d.fy = null;
  }
  return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
}

// ---------- Data fetching & submission ----------
async function fetchLatestTraffic() {
  const N = 17;
  const overlay = document.getElementById('graph-loading');
  try {
    if (overlay) overlay.style.display = 'flex';

    const response = await fetch('/api/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const result = await response.json();
    if (!result.success) {
      console.error('🚨 Fetch failed:', result.message);
      return;
    }
    const rawData = result.data;

    const latestTraffic = Array.from({ length: N }, () => Array(N).fill(0));
    for (const key in rawData) {
      const match = key.match(/^S(\d+)-S(\d+)$/);
      if (match) {
        const i = parseInt(match[1]) - 1;
        const j = parseInt(match[2]) - 1;
        if (linkSet.has(`${i + 1}-${j + 1}`)) {
          latestTraffic[i][j] = rawData[key];
        }
      }
    }

    const table = document.getElementById('matrix-table');
    const rows = table.querySelector('tbody').getElementsByTagName('tr');
    for (let i = 0; i < rows.length; i++) {
      const cells = rows[i].getElementsByTagName('td');
      for (let j = 0; j < cells.length; j++) {
        const input = cells[j].querySelector('input');
        if (input && !input.disabled) input.value = latestTraffic[i][j];
      }
    }

    links.forEach(link => {
      const s = (typeof link.source === 'object') ? link.source.id : link.source;
      const t = (typeof link.target === 'object') ? link.target.id : link.target;
      link.value = latestTraffic[s - 1][t - 1];
    });

    // 移除零流量邊，避免畫面雜訊
    links = links.filter(l => l.value !== 0);

    refreshLinks();
    labelSel.select('textPath').each(function(d){tweenText(d3.select(this), d.value);});
  } catch (error) {
    console.error('Error fetching telemetry:', error);
  } finally {
    if (overlay) overlay.style.display = 'none';
  }
}

function submitMatrix() {
  const table = document.getElementById('matrix-table');
  const rows = table.querySelector('tbody').getElementsByTagName('tr');
  const matrix = [];
  const hostNames = Array.from({ length: 17 }, (_, i) => `h${i + 1}`);

  for (let i = 0; i < rows.length; i++) {
    const cells = rows[i].getElementsByTagName('td');
    const rowValues = [];
    for (let j = 0; j < cells.length; j++) {
      const input = cells[j].querySelector('input');
      let inputVal = input ? parseInt(input.value, 10) : 0;
      if (isNaN(inputVal)) inputVal = 0;
      rowValues.push(inputVal);
    }
    matrix.push(rowValues);
  }

  const userNote = document.getElementById('user-note')?.value?.trim() || '';
  const payload = { hosts: hostNames, matrix, user_note: userNote };

  const loading = document.getElementById('loading');
  const resultContainer = document.getElementById('evaluation-result');
  if (loading) loading.style.display = 'block';
  if (resultContainer) resultContainer.textContent = '';

  fetch('/api/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (!response.ok) throw new Error('提交失敗');
    return response.json();
  })
  .then(data => {
    const evaluationResult = data['evaluation_result'] || '無法取得評估結果';
    if (resultContainer) resultContainer.textContent = evaluationResult;

    const updated_links = data['str_updated_links'] || {};
    for (const key in updated_links) {
      const stripped = key.replace(/[()]/g, '');
      const [s, t] = stripped.split(',').map(x => parseInt(x.trim(), 10));
      const newValue = updated_links[key];

      const theLink = links.find(l => {
        const sid = (typeof l.source === 'object') ? l.source.id : l.source;
        const tid = (typeof l.target === 'object') ? l.target.id : l.target;
        return sid === s && tid === t;
      });
      if (theLink) theLink.value = newValue;

      const targetNode = nodes.find(n => n.id === t);
      if (targetNode) {
        nodeRings.filter(d => d.id === targetNode.id).each(pulseNode);
      }
    }

    links = links.filter(l => l.value !== 0);
    refreshLinks();
    labelSel.select('textPath').each(function(d){tweenText(d3.select(this), d.value);});

    // 若歷史彈窗開著，就刷新目前頁面
    if (historyModalOpen) {
      fetchHistory(historyState.page, historyState.pageSize);
    }
  })
  .catch(err => {
    console.error(err);
    alert('提交發生錯誤: ' + err.message);
  })
  .finally(() => {
    if (loading) loading.style.display = 'none';
  });
}

// ---------- 歷史紀錄（Modal + 分頁） ----------
let historyModalOpen = false;
const historyState = { page: 1, pageSize: 10, total: 0 };

function openHistoryModal() {
  historyModalOpen = true;
  const modal = document.getElementById('history-modal');
  modal.style.display = 'flex';
  // 綁定分頁控制
  document.getElementById('prev-page').onclick = () => {
    if (historyState.page > 1) fetchHistory(historyState.page - 1, historyState.pageSize);
  };
  document.getElementById('next-page').onclick = () => {
    const totalPages = Math.max(1, Math.ceil(historyState.total / historyState.pageSize));
    if (historyState.page < totalPages) fetchHistory(historyState.page + 1, historyState.pageSize);
  };
  document.getElementById('page-size').onchange = (e) => {
    const ps = parseInt(e.target.value, 10) || 10;
    fetchHistory(1, ps);
  };
  // 初次載入
  fetchHistory(1, historyState.pageSize);
}

function closeHistoryModal() {
  historyModalOpen = false;
  const modal = document.getElementById('history-modal');
  modal.style.display = 'none';
}

async function fetchHistory(page = 1, pageSize = 10) {
  const list = document.getElementById('history-list');
  const detail = document.getElementById('history-detail');
  try {
    list.textContent = '載入中…';
    const res = await fetch(`/api/history?page=${page}&page_size=${pageSize}`);
    const data = await res.json();
    if (data.status !== 'ok') {
      list.textContent = '讀取歷史失敗';
      return;
    }

    historyState.page = data.page;
    historyState.pageSize = data.page_size;
    historyState.total = data.total;

    const items = data.items || [];
    if (!items.length) {
      list.textContent = '尚無紀錄';
      detail.textContent = '（沒有可顯示的紀錄）';
      updatePager();
      return;
    }

    // 渲染列表
    list.innerHTML = '';
    items.forEach(item => {
      const row = document.createElement('div');
      row.className = 'history-row';
      row.innerHTML = `
        <div><b>#${item.id}</b> <small>${item.created_at}</small></div>
        <div style="color:#666; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;">
          ${escapeHtml(item.user_note || '(無備註)')}
        </div>
        <div style="color:#888; font-size:12px; margin-top:4px;">${escapeHtml(item.preview || '')}</div>
      `;
      row.addEventListener('click', () => fetchHistoryOne(item.id));
      list.appendChild(row);
    });

    // 預設顯示第一筆詳細
    fetchHistoryOne(items[0].id);
    updatePager();
  } catch (e) {
    console.error(e);
    list.textContent = '讀取歷史發生錯誤';
  }
}

function updatePager() {
  const totalPages = Math.max(1, Math.ceil(historyState.total / historyState.pageSize));
  document.getElementById('page-info').textContent = `第 ${historyState.page} / ${totalPages} 頁（共 ${historyState.total} 筆）`;
  document.getElementById('prev-page').disabled = historyState.page <= 1;
  document.getElementById('next-page').disabled = historyState.page >= totalPages;

  const sel = document.getElementById('page-size');
  if (sel && +sel.value !== historyState.pageSize) sel.value = String(historyState.pageSize);
}

async function fetchHistoryOne(id) {
  const detail = document.getElementById('history-detail');
  detail.textContent = '讀取中...';
  try {
    const res = await fetch(`/api/history/${id}`);
    const data = await res.json();
    if (data.status !== 'ok') {
      detail.textContent = '讀取失敗';
      return;
    }
    const it = data.item;
    const pretty = [
      `#${it.id}  @ ${it.created_at}`,
      ``,
      `【使用者備註】`,
      it.user_note || '(無)',
      ``,
      `【分析結果】`,
      it.evaluation_result || '(無)',
      ``,
      `【Hosts】`,
      it.hosts_json,
      ``,
      `【Matrix】`,
      it.matrix_json
    ].join('\n');
    detail.textContent = pretty;
  } catch (e) {
    console.error(e);
    detail.textContent = '讀取單筆發生錯誤';
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

// 將函式暴露給按鈕（index.html 的 onclick）
window.fetchLatestTraffic = fetchLatestTraffic;
window.submitMatrix = submitMatrix;
window.openHistoryModal = openHistoryModal;
window.closeHistoryModal = closeHistoryModal;
