/* ============================================================
   BSIE v2 – Smart Ingestion Platform
   Multi-step wizard: Upload → Detect → Configure → Process → Results
   ============================================================ */

// ── State ──────────────────────────────────────────────────────────────
const S = {
  step: 1,
  jobId: null,
  tempFilePath: null,
  fileName: null,
  detectedBank: null,
  suggestedMapping: {},
  confirmedMapping: {},
  allColumns: [],
  confidenceScores: {},
  sampleRows: [],
  bankKey: '',
  account: '',
  name: '',
  results: null,
  currentTab: 'transactions',
  txnPage: 1,
  txnTotal: 0,
  txnPageSize: 100,
};

// ── Logical field definitions ──────────────────────────────────────────
const FIELDS = [
  { key:'date',                  label:'Date',                  required:true  },
  { key:'time',                  label:'Time',                  required:false },
  { key:'description',           label:'Description',           required:true  },
  { key:'amount',                label:'Amount (signed)',        required:false },
  { key:'debit',                 label:'Debit',                 required:false },
  { key:'credit',                label:'Credit',                required:false },
  { key:'channel',               label:'Channel',               required:false },
  { key:'counterparty_account',  label:'Counterparty Account',  required:false },
  { key:'counterparty_name',     label:'Counterparty Name',     required:false },
];

// ── Step navigation ────────────────────────────────────────────────────
function goStep(n) {
  document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`step-${n}`).classList.add('active');

  document.querySelectorAll('.step-item').forEach(item => {
    const s = +item.dataset.step;
    item.classList.remove('active','done','locked');
    if (s < n)  item.classList.add('done');
    else if (s === n) item.classList.add('active');
    else             item.classList.add('locked');
  });
  S.step = n;
  window.scrollTo(0, 0);
}

// ── Upload ─────────────────────────────────────────────────────────────
const dropZone   = document.getElementById('drop-zone');
const fileInput  = document.getElementById('file-input');
const browseLink = document.getElementById('browse-link');

browseLink.onclick = () => fileInput.click();
dropZone.onclick   = (e) => { if (e.target !== browseLink) fileInput.click(); };
fileInput.onchange = (e) => handleFile(e.target.files[0]);

dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', ()=> dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});

async function handleFile(file) {
  if (!file) return;
  if (!file.name.match(/\.(xlsx|xls)$/i)) { toast('Please upload an Excel file (.xlsx or .xls)', 'error'); return; }

  S.fileName = file.name;
  document.getElementById('upload-progress').style.display = 'block';
  document.getElementById('upload-status').textContent = 'Uploading and analysing…';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res  = await fetch('/api/upload', { method:'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    S.tempFilePath    = data.temp_file_path;
    S.detectedBank    = data.detected_bank;
    S.suggestedMapping = data.suggested_mapping || {};
    S.confirmedMapping = { ...S.suggestedMapping };
    S.allColumns       = data.all_columns || [];
    S.confidenceScores = data.confidence_scores || {};
    S.sampleRows       = data.sample_rows || [];

    renderDetection(data);
    renderMappingTable();
    renderSampleTable();
    populateBankSelect(data.banks || [], data.detected_bank?.config_key || '');

    if (data.memory_match) {
      document.getElementById('memory-notice').style.display = 'block';
      document.getElementById('memory-detail').textContent =
        `Profile "${data.memory_match.profile_id.slice(0,8)}…" matched (bank: ${data.memory_match.bank}, used ${data.memory_match.usage_count} times). Mapping auto-applied.`;
    }

    goStep(2);
    toast('File analysed successfully', 'success');
  } catch (err) {
    document.getElementById('upload-progress').style.display = 'none';
    toast(err.message, 'error');
  }
}

// ── Detection summary ──────────────────────────────────────────────────
function renderDetection(data) {
  const bd   = data.detected_bank || {};
  const conf = Math.round((bd.confidence || 0) * 100);
  document.getElementById('detect-summary').innerHTML = `
    <div class="detect-card">
      <div class="dc-label">Detected Bank</div>
      <div class="dc-value">${bd.bank || 'UNKNOWN'}</div>
      <div class="dc-conf">Confidence: ${conf}%</div>
    </div>
    <div class="detect-card">
      <div class="dc-label">File</div>
      <div class="dc-value" style="font-size:14px;">${data.file_name || ''}</div>
      <div class="dc-conf">${(data.all_columns||[]).length} columns detected</div>
    </div>`;
}

// ── Mapping table ──────────────────────────────────────────────────────
function renderMappingTable() {
  const tbody = document.getElementById('mapping-tbody');
  tbody.innerHTML = '';
  const opts = ['', ...S.allColumns].map(c => `<option value="${esc(c)}" ${c===''?'':''}>${c || '— None —'}</option>`).join('');

  FIELDS.forEach(f => {
    const cur  = S.confirmedMapping[f.key] || '';
    const conf = S.confidenceScores[f.key] || 0;
    const pct  = Math.round(conf * 100);

    tbody.insertAdjacentHTML('beforeend', `
      <tr>
        <td class="field-name">${f.label}${f.required ? ' <span class="field-req">*</span>' : ''}</td>
        <td>
          <select onchange="updateMapping('${f.key}', this.value)" id="map-${f.key}">
            ${S.allColumns.map(c => `<option value="${esc(c)}" ${c===cur?'selected':''}>${c}</option>`).join('')}
            <option value="" ${!cur?'selected':''}>— None —</option>
          </select>
        </td>
        <td>
          <span style="font-size:12px;color:var(--muted);">${pct}%</span>
          <div class="conf-pill"><div class="conf-fill" style="width:${pct}%"></div></div>
        </td>
        <td>${cur ? '<span class="badge badge-green">Mapped</span>' : '<span class="badge badge-gray">Unmapped</span>'}</td>
      </tr>`);
  });
}

function updateMapping(field, value) {
  S.confirmedMapping[field] = value || null;
  // Refresh status badge only
  renderMappingTable();
}

function autoFillMapping() {
  S.confirmedMapping = { ...S.suggestedMapping };
  renderMappingTable();
  toast('Auto-fill applied', 'info');
}

function clearMapping() {
  FIELDS.forEach(f => { S.confirmedMapping[f.key] = null; });
  renderMappingTable();
}

// ── Sample table ───────────────────────────────────────────────────────
function renderSampleTable() {
  const tbl = document.getElementById('sample-table');
  if (!S.sampleRows.length) { tbl.innerHTML = '<tr><td style="color:var(--muted);padding:12px;">No sample data</td></tr>'; return; }
  const cols = Object.keys(S.sampleRows[0]);
  tbl.innerHTML = `<thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead>
    <tbody>${S.sampleRows.map(r=>`<tr>${cols.map(c=>`<td title="${esc(String(r[c]||''))}">${esc(String(r[c]||''))}</td>`).join('')}</tr>`).join('')}</tbody>`;
}

// ── Bank select ────────────────────────────────────────────────────────
function populateBankSelect(banks, detectedKey) {
  const sel = document.getElementById('bank-select');
  sel.innerHTML = banks.map(b =>
    `<option value="${esc(b.key)}" ${b.key===detectedKey?'selected':''}>${b.name}</option>`
  ).join('') || '<option value="">UNKNOWN</option>';
  S.bankKey = sel.value;
}

// ── Confirm mapping → Step 3 ───────────────────────────────────────────
async function confirmMapping() {
  const required = FIELDS.filter(f => f.required);
  const missing  = required.filter(f => !S.confirmedMapping[f.key]);
  if (missing.length) {
    toast('Required fields missing: ' + missing.map(f=>f.label).join(', '), 'error');
    return;
  }

  const bank = document.getElementById('bank-select')?.value ||
               S.detectedBank?.bank || 'UNKNOWN';

  await fetch('/api/mapping/confirm', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ bank, mapping: S.confirmedMapping, columns: S.allColumns }),
  });

  S.bankKey = bank;
  goStep(3);
  toast('Mapping confirmed and saved', 'success');
}

// ── Start processing ───────────────────────────────────────────────────
async function startProcessing() {
  const account = document.getElementById('account-input').value.trim();
  const name    = document.getElementById('name-input').value.trim();
  const bankKey = document.getElementById('bank-select').value;

  if (!account || !/^\d{10}$|^\d{12}$/.test(account)) {
    toast('Account must be exactly 10 or 12 digits', 'error'); return;
  }

  S.account = account;
  S.name    = name;
  S.bankKey = bankKey;

  goStep(4);
  document.getElementById('log-box').innerHTML = '';
  document.getElementById('proc-status').textContent = 'Starting pipeline…';

  try {
    const res  = await fetch('/api/process', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        temp_file_path:    S.tempFilePath,
        bank_key:          S.bankKey,
        account:           S.account,
        name:              S.name,
        confirmed_mapping: S.confirmedMapping,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to start');
    S.jobId = data.job_id;
    pollJob();
  } catch(err) { toast(err.message, 'error'); goStep(3); }
}

// ── Job polling ────────────────────────────────────────────────────────
let _pollTimer = null;
function pollJob() {
  if (_pollTimer) clearTimeout(_pollTimer);
  _pollTimer = setTimeout(async () => {
    try {
      const res  = await fetch(`/api/job/${S.jobId}`);
      const data = await res.json();
      renderLog(data.log || []);

      if (data.status === 'done') {
        document.getElementById('proc-status').textContent = '✅ Pipeline complete!';
        document.getElementById('processing-spinner').querySelector('.spinner').style.display='none';
        S.results = data.result;
        await renderResults();
        goStep(5);
        toast('Processing complete!', 'success');
      } else if (data.status === 'error') {
        document.getElementById('proc-status').textContent = '❌ Error: ' + (data.error || 'unknown');
        toast(data.error || 'Pipeline failed', 'error');
      } else {
        pollJob();
      }
    } catch(e) { pollJob(); }
  }, 1200);
}

function renderLog(lines) {
  const box = document.getElementById('log-box');
  box.innerHTML = lines.map(l => {
    let cls = 'll';
    if (l.includes('WARNING')) cls += ' WARN';
    if (l.includes('ERROR'))   cls += ' ERROR';
    return `<div class="${cls}">${esc(l)}</div>`;
  }).join('');
  box.scrollTop = box.scrollHeight;
}

// ── Results ────────────────────────────────────────────────────────────
async function renderResults() {
  const r    = S.results;
  const meta = r?.meta || {};

  document.getElementById('results-subtitle').textContent =
    `Account: ${meta.account_number || S.account} | Bank: ${meta.bank || ''}  |  ${meta.num_transactions || 0} transactions`;

  // Stats
  const inAmt  = (meta.total_in  || 0).toLocaleString('th-TH', {minimumFractionDigits:2});
  const outAmt = Math.abs(meta.total_out || 0).toLocaleString('th-TH', {minimumFractionDigits:2});
  const circAmt = (meta.total_circulation || 0).toLocaleString('th-TH', {minimumFractionDigits:2});
  document.getElementById('stats-bar').innerHTML = `
    <div class="stat-card"><div class="sc-label">Transactions</div><div class="sc-value blue">${meta.num_transactions||0}</div></div>
    <div class="stat-card"><div class="sc-label">Total IN</div><div class="sc-value green">฿${inAmt}</div></div>
    <div class="stat-card"><div class="sc-label">Total OUT</div><div class="sc-value red">฿${outAmt}</div></div>
    <div class="stat-card"><div class="sc-label">เงินหมุนเวียนรวม</div><div class="sc-value" style="color:var(--primary);">฿${circAmt}</div></div>
    <div class="stat-card"><div class="sc-label">Date Range</div><div class="sc-value" style="font-size:13px;">${meta.date_range||'—'}</div></div>
    <div class="stat-card"><div class="sc-label">Unknown CP</div><div class="sc-value">${meta.num_unknown||0}</div></div>
    <div class="stat-card"><div class="sc-label">Partial Accts</div><div class="sc-value">${meta.num_partial_accounts||0}</div></div>`;

  S.txnPage = 1;
  renderTxnTable(r.transactions || []);
  renderGenericTable('ent', r.entities || []);
  renderGenericTable('lnk', r.links || []);
  renderDownloads(meta.account_number || S.account);
}

// Transaction table with pagination
function renderTxnTable(rows) {
  const COLS = ['transaction_id','date','amount','direction','transaction_type',
                'confidence','counterparty_account','counterparty_name',
                'description','from_account','to_account','is_overridden'];

  const thead = document.getElementById('txn-thead');
  const tbody = document.getElementById('txn-tbody');

  thead.innerHTML = `<tr>${COLS.map(c=>`<th>${c.replace(/_/g,' ')}</th>`).join('')}<th>Action</th></tr>`;

  tbody.innerHTML = rows.map(row => {
    const amt     = parseFloat(row.amount || 0);
    const amtCls  = amt >= 0 ? 'amt-in' : 'amt-out';
    const amtStr  = amt.toLocaleString('th-TH', {minimumFractionDigits:2});
    const isOv    = row.is_overridden === 'True' || row.is_overridden === true;
    const trCls   = isOv ? 'overridden' : '';
    const ovBadge = isOv ? ' <span class="badge badge-green">OV</span>' : '';

    const cells = COLS.map(c => {
      if (c === 'amount')    return `<td class="${amtCls}">${amtStr}</td>`;
      if (c === 'direction') return `<td>${row[c]==='IN'?'<span class="badge badge-green">IN</span>':'<span class="badge badge-red">OUT</span>'}</td>`;
      if (c === 'transaction_type') return `<td><span class="badge badge-blue">${esc(row[c]||'')}</span></td>`;
      if (c === 'is_overridden') return `<td>${isOv ? '<span class="badge badge-green">Yes</span>' : ''}</td>`;
      if (c === 'transaction_id') return `<td class="mono">${esc(row[c]||'')}${ovBadge}</td>`;
      return `<td>${esc(String(row[c]||''))}</td>`;
    }).join('');

    return `<tr class="${trCls}">${cells}
      <td><button class="btn btn-ghost btn-sm" onclick="openOverride('${esc(row.transaction_id||'')}','${esc(row.from_account||'')}','${esc(row.to_account||'')}')">🔗 Override</button></td>
    </tr>`;
  }).join('');
}

function renderGenericTable(prefix, rows) {
  if (!rows.length) return;
  const cols  = Object.keys(rows[0]);
  const thead = document.getElementById(`${prefix}-thead`);
  const tbody = document.getElementById(`${prefix}-tbody`);
  thead.innerHTML = `<tr>${cols.map(c=>`<th>${c.replace(/_/g,' ')}</th>`).join('')}</tr>`;
  tbody.innerHTML = rows.map(r =>
    `<tr>${cols.map(c=>`<td>${esc(String(r[c]||''))}</td>`).join('')}</tr>`
  ).join('');
}

function renderDownloads(account) {
  const meta = S.results?.meta || {};
  const reportFile = meta.report_filename || 'report.xlsx';
  const files = [
    [`processed/${reportFile}`,      `📊 ${reportFile}`],
    ['processed/transactions.csv',   '📄 transactions.csv'],
    ['processed/entities.csv',       '📄 entities.csv'],
    ['processed/entities.xlsx',      '📊 entities.xlsx'],
    ['processed/links.csv',         '📄 links.csv'],
    ['raw/original.xlsx',           '📁 original.xlsx'],
    ['meta.json',                   '🗂 meta.json'],
  ];
  document.getElementById('download-links').innerHTML = files.map(([path, label]) =>
    `<a class="dl-btn" href="/api/download/${account}/${encodeURI(path)}" download>⬇ ${label}</a>`
  ).join('');
}

// ── Tab switching ──────────────────────────────────────────────────────
function switchTab(tab) {
  ['transactions','entities','links'].forEach(t => {
    document.getElementById(`tab-${t}`).style.display = t===tab ? 'block' : 'none';
    document.getElementById(`tab-${t.slice(0,3)}`).className =
      t===tab ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm';
  });
  S.currentTab = tab;
}

// ── Override modal ─────────────────────────────────────────────────────
function openOverride(tid, fromAcc, toAcc) {
  document.getElementById('ov-tid').value        = tid;
  document.getElementById('ov-tid-display').value = tid;
  document.getElementById('ov-from').value        = fromAcc;
  document.getElementById('ov-to').value          = toAcc;
  document.getElementById('ov-reason').value      = '';
  document.getElementById('override-modal').classList.add('open');
}

function closeOverride() {
  document.getElementById('override-modal').classList.remove('open');
}

async function saveOverride() {
  const tid    = document.getElementById('ov-tid').value;
  const frm    = document.getElementById('ov-from').value.trim();
  const to     = document.getElementById('ov-to').value.trim();
  const reason = document.getElementById('ov-reason').value.trim();
  const by     = document.getElementById('ov-by').value.trim() || 'analyst';

  if (!frm || !to) { toast('FROM and TO accounts are required', 'error'); return; }

  try {
    const res  = await fetch('/api/override', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ transaction_id:tid, from_account:frm, to_account:to, reason, override_by:by }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Override failed');

    closeOverride();
    toast('Override saved', 'success');

    // Refresh transaction table from server
    await refreshResults();
  } catch(e) { toast(e.message,'error'); }
}

async function refreshResults() {
  if (!S.results?.meta?.account_number && !S.account) return;
  const acct = S.results?.meta?.account_number || S.account;
  try {
    const res  = await fetch(`/api/results/${acct}?page=1&page_size=500`);
    const data = await res.json();
    renderTxnTable(data.rows || []);
    toast('Results refreshed', 'info');
  } catch(e) {}
}

// ── Reset ──────────────────────────────────────────────────────────────
function resetAll() {
  S.step=1; S.jobId=null; S.tempFilePath=null; S.results=null;
  S.suggestedMapping={}; S.confirmedMapping={}; S.allColumns=[];
  document.getElementById('file-input').value='';
  document.getElementById('upload-progress').style.display='none';
  document.getElementById('memory-notice').style.display='none';
  document.getElementById('log-box').innerHTML='';
  goStep(1);
}

// ── Utilities ──────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function toast(msg, type='info', ms=3500) {
  const wrap = document.getElementById('toast-wrap');
  const div  = document.createElement('div');
  div.className = `toast ${type}`;
  div.textContent = msg;
  wrap.appendChild(div);
  setTimeout(() => div.remove(), ms);
}

// Close modal on overlay click
document.getElementById('override-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeOverride();
});

// Initial bank list load
fetch('/api/banks').then(r=>r.json()).then(banks => {
  populateBankSelect(banks, '');
}).catch(()=>{});
