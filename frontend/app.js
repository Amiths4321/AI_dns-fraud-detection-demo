const apiBaseInput = document.getElementById('apiBase');
const connStatus = document.getElementById('connStatus');
const pulseRail = document.getElementById('pulseRail');
const feedBody = document.getElementById('feedBody');
const breakdownEl = document.getElementById('breakdown');

const statTotal = document.getElementById('statTotal');
const statHigh = document.getElementById('statHigh');
const statMedium = document.getElementById('statMedium');
const statValue = document.getElementById('statValue');

let selectedTxnId = null;
let knownIds = new Set();
let scoreHistory = []; // {label, score}
let reasonCounts = {};

function apiBase() {
  return apiBaseInput.value.replace(/\/+$/, '');
}

function fmtINR(n) {
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function setConn(ok) {
  connStatus.classList.remove('ok', 'err');
  connStatus.classList.add(ok ? 'ok' : 'err');
  connStatus.innerHTML = `<i class="dot"></i> ${ok ? 'connected' : 'unreachable'}`;
}

function flashPulse() {
  pulseRail.classList.remove('alert');
  // restart animation
  void pulseRail.offsetWidth;
  pulseRail.classList.add('alert');
}

async function fetchJSON(path, opts) {
  const res = await fetch(apiBase() + path, opts);
  if (!res.ok) throw new Error('Request failed: ' + path);
  return res.json();
}

function renderStats(stats) {
  statTotal.textContent = stats.total.toLocaleString('en-IN');
  statHigh.textContent = stats.high.toLocaleString('en-IN');
  statMedium.textContent = stats.medium.toLocaleString('en-IN');
  statValue.textContent = fmtINR(stats.value_flagged);
}

function rowHTML(txn) {
  return `
    <tr data-id="${txn.txn_id}" class="${txn.risk_level === 'HIGH' ? 'flash-high' : ''}">
      <td class="mono">${fmtTime(txn.timestamp)}</td>
      <td>${txn.customer_name}</td>
      <td class="mono">${txn.account_no}</td>
      <td class="amount">${fmtINR(txn.amount)}</td>
      <td>${txn.city}</td>
      <td><span class="risk-badge ${txn.risk_level}">${txn.risk_level} · ${txn.risk_score}</span></td>
    </tr>`;
}

function renderFeed(items) {
  // items are newest-first already
  const newOnes = items.filter(t => !knownIds.has(t.txn_id));
  newOnes.forEach(t => knownIds.add(t.txn_id));

  feedBody.innerHTML = items.map(rowHTML).join('');

  if (selectedTxnId) {
    const row = feedBody.querySelector(`tr[data-id="${selectedTxnId}"]`);
    if (row) row.classList.add('selected');
  }

  // attach click handlers
  feedBody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', () => {
      const id = tr.getAttribute('data-id');
      const txn = items.find(t => t.txn_id === id);
      if (txn) selectTxn(txn);
    });
  });

  if (newOnes.some(t => t.risk_level === 'HIGH')) {
    flashPulse();
  }

  // update chart history with newest items (cap 40)
  newOnes.slice().reverse().forEach(t => {
    scoreHistory.push({ label: fmtTime(t.timestamp), score: t.risk_score, level: t.risk_level });
    t.reasons.forEach(r => {
      reasonCounts[r.label] = (reasonCounts[r.label] || 0) + 1;
    });
  });
  if (scoreHistory.length > 40) scoreHistory = scoreHistory.slice(-40);
  updateCharts();
}

function selectTxn(txn) {
  selectedTxnId = txn.txn_id;
  feedBody.querySelectorAll('tr').forEach(tr => {
    tr.classList.toggle('selected', tr.getAttribute('data-id') === txn.txn_id);
  });

  if (!txn.reasons.length) {
    breakdownEl.innerHTML = `
      <div class="bd-head">
        <span class="bd-score" style="color:var(--risk-low)">${txn.risk_score}</span>
        <span class="risk-badge LOW">LOW</span>
      </div>
      <div class="bd-meta">${txn.customer_name} · ${txn.account_no} · ${fmtINR(txn.amount)}</div>
      <div class="bd-clean">No risk signals fired. This transaction matched the customer's normal behavioral profile.</div>
    `;
    return;
  }

  const color = txn.risk_level === 'HIGH' ? 'var(--risk-high)' : txn.risk_level === 'MEDIUM' ? 'var(--risk-medium)' : 'var(--risk-low)';

  breakdownEl.innerHTML = `
    <div class="bd-head">
      <span class="bd-score" style="color:${color}">${txn.risk_score}</span>
      <span class="risk-badge ${txn.risk_level}">${txn.risk_level}</span>
    </div>
    <div class="bd-meta">${txn.customer_name} · ${txn.account_no} · ${fmtINR(txn.amount)} · ${txn.city}</div>
    ${txn.reasons.map(r => `
      <div class="bd-reason">
        <div class="bd-reason-top">
          <span class="bd-reason-label">${r.label}</span>
          <span class="bd-reason-points">+${r.points}</span>
        </div>
        <div class="bd-reason-detail">${r.detail}</div>
      </div>
    `).join('')}
  `;
}

// ---------- Charts ----------
let scoreChart, reasonChart;

function initCharts() {
  const scoreCtx = document.getElementById('scoreChart');
  scoreChart = new Chart(scoreCtx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Risk score',
        data: [],
        borderColor: '#3D6FE0',
        backgroundColor: 'rgba(61,111,224,0.08)',
        tension: 0.25,
        fill: true,
        pointRadius: 2,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, grid: { color: '#EFF2F6' } },
        x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
      }
    }
  });

  const reasonCtx = document.getElementById('reasonChart');
  reasonChart = new Chart(reasonCtx, {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Occurrences', data: [], backgroundColor: '#3D6FE0' }] },
    options: {
      responsive: true,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: { x: { grid: { color: '#EFF2F6' } }, y: { grid: { display: false } } }
    }
  });
}

function updateCharts() {
  scoreChart.data.labels = scoreHistory.map(h => h.label);
  scoreChart.data.datasets[0].data = scoreHistory.map(h => h.score);
  scoreChart.update();

  const sorted = Object.entries(reasonCounts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  reasonChart.data.labels = sorted.map(s => s[0]);
  reasonChart.data.datasets[0].data = sorted.map(s => s[1]);
  reasonChart.update();
}

// ---------- Polling loop ----------
async function refresh() {
  try {
    const [feedRes, statsRes] = await Promise.all([
      fetchJSON('/api/transactions?limit=50'),
      fetchJSON('/api/stats'),
    ]);
    setConn(true);
    renderFeed(feedRes.items);
    renderStats(statsRes);
  } catch (e) {
    setConn(false);
  }
}

async function tick() {
  try {
    await fetchJSON('/api/tick', { method: 'POST' });
  } catch (e) {
    // surfaced via refresh()'s connection status
  }
}

document.getElementById('simButtons').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-kind]');
  if (!btn) return;
  btn.disabled = true;
  try {
    await fetchJSON('/api/simulate/' + btn.getAttribute('data-kind'), { method: 'POST' });
    await refresh();
  } catch (err) {
    setConn(false);
  } finally {
    btn.disabled = false;
  }
});

initCharts();
refresh();
setInterval(tick, 2200);
setInterval(refresh, 1500);
