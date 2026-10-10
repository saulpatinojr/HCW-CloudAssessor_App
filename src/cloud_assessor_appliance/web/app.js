/* Cloud assessment pane. Vanilla, no storage, no analytics; every dynamic string goes through text nodes.
 * Posts {type:'hcw-addon', id:'cloud-assessment', state} to each site origin from /api/health.siteOrigins when framed.
 * States: loading (on load) -> ready (health ok) | unavailable (health failed); working during an upload, then ready.
 * Copied from HCW-CloudAssessor_AddOn (main, d552c6c) on 2026-10-10. Edition switch: when /api/health reports
 * edition "appliance" the pane renders the current assessment of the scope (mode "current": no upload, no delete,
 * a Refresh button posting /api/refresh); otherwise the upload flow of the lab (mode "upload"). */
(function () {
  'use strict';
  var ADDON_ID = 'cloud-assessment';
  var UNAVAILABLE = "This tool isn't available right now.";
  var ACTION = 'cloud-assessment-upload';
  var VERIFICATION_SCRIPT = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

  var state = {
    mode: 'upload',        // 'upload' (lab) | 'current' (appliance), from /api/health.edition
    siteOrigins: [],
    health: null,
    file: null,            // { name, text, format }
    verificationToken: null,
    verificationWidget: null,
    assessment: null,      // { id, ownerToken, expiresAt, summary, scorecards }
    detail: null,          // full assessment document
    reportMd: '',
    selected: null
  };

  var $ = function (id) { return document.getElementById(id); };
  var text = function (el, value) { el.textContent = value == null ? '' : String(value); return el; };
  var el = function (tag, cls, value) { var n = document.createElement(tag); if (cls) n.className = cls; if (value != null) n.textContent = String(value); return n; };
  var clear = function (node) { while (node.firstChild) node.removeChild(node.firstChild); };

  // ----- theme: ?theme=dark|light on the frame URL wins; otherwise prefers-color-scheme through theme.css -----
  (function theme() {
    var params = new URLSearchParams(window.location.search);
    var t = params.get('theme');
    if (t === 'dark') document.documentElement.classList.add('dark');
    if (t === 'light') document.documentElement.classList.add('light');
  })();

  // ----- pane protocol -----
  var framed = window.parent && window.parent !== window;
  function post(paneState) {
    if (!framed) return;
    state.siteOrigins.forEach(function (origin) {
      try { window.parent.postMessage({ type: 'hcw-addon', id: ADDON_ID, state: paneState }, origin); } catch (e) { /* ignore */ }
    });
  }

  function setStatus(words) { text($('status'), words); }
  function unavailable() {
    setStatus('Unavailable');
    $('unavailable').hidden = false;
    $('step-upload').hidden = true;
    $('step-current').hidden = true;
    post('unavailable');
  }

  // ----- edition switch: the appliance reads its own scope; the lab assesses an upload -----
  function applyEdition(health) {
    state.mode = health.edition === 'appliance' ? 'current' : 'upload';
    if (state.mode !== 'current') return;
    text($('edition-badge'), 'Appliance edition · reads your own scope with a managed identity');
    $('not-production').hidden = true;
    text($('notice'), 'This deployment assesses the Azure scope it was granted read access to, on a timer. Nothing is uploaded and no credential is ever asked for; results are held in memory and replaced on every refresh.');
    $('step-upload').hidden = true;
    $('step-current').hidden = false;
    $('delete').hidden = true;
    text($('h-scorecard'), '2. Scorecard');
    renderCurrentSummary(health);
  }
  function renderCurrentSummary(health) {
    var scope = health.scope && typeof health.scope.count === 'number' ? health.scope.count : 0;
    var last = health.lastRun ? new Date(health.lastRun).toLocaleString() : 'not yet';
    text($('current-summary'), scope + ' subscription' + (scope === 1 ? '' : 's') + ' in scope. Last run: ' + last + '.' + (health.publicResults === false ? ' Results are not published for this deployment yet.' : ''));
  }
  function loadCurrent() {
    setStatus('Loading…');
    post('working');
    var status = 0;
    api('/api/assessments/current')
      .then(function (r) { status = r.status; return r.json().catch(function () { return null; }); })
      .then(function (json) {
        if (status !== 200) throw new Error(errorMessage(json, status));
        state.detail = json.assessment;
        state.assessment = { id: 'current', ownerToken: null, expiresAt: null, summary: json.assessment.summary, scorecards: json.assessment.scorecards, warnings: json.assessment.ingestion_warnings || [] };
        return api('/api/assessments/current/report.md').then(function (r) { return r.text(); });
      })
      .then(function (md) { state.reportMd = md; render(); text($('refresh-note'), ''); setStatus('Ready'); post('ready'); })
      .catch(function (err) { text($('refresh-note'), err && err.message ? err.message : 'The request could not be completed.'); setStatus('Ready'); post('ready'); });
  }
  function requestRefresh() {
    $('refresh').disabled = true;
    var headers = {};
    if (state.verificationToken) headers['x-turnstile-token'] = state.verificationToken;
    var status = 0;
    api('/api/refresh', { method: 'POST', headers: headers })
      .then(function (r) { status = r.status; return r.json().catch(function () { return null; }); })
      .then(function (json) {
        if (status !== 202) throw new Error(errorMessage(json, status));
        text($('refresh-note'), json && json.running ? 'A collection is already running; results update when it completes.' : 'Refresh queued; results update when the collection completes.');
        setTimeout(function () { fetch('/api/health', { credentials: 'omit' }).then(function (r) { return r.json(); }).then(function (h) { renderCurrentSummary(h); loadCurrent(); }).catch(function () { /* ignore */ }); }, 15000);
      })
      .catch(function (err) { text($('refresh-note'), err && err.message ? err.message : 'The request could not be completed.'); })
      .finally(function () { resetVerification(); $('refresh').disabled = false; });
  }

  // ----- API -----
  function api(path, options) {
    options = options || {};
    var headers = options.headers || {};
    if (state.mode === 'upload' && state.assessment && state.assessment.ownerToken && !headers['x-owner-token']) headers['x-owner-token'] = state.assessment.ownerToken;
    return fetch(path, { method: options.method || 'GET', headers: headers, body: options.body, credentials: 'omit' });
  }
  function errorMessage(body, status) {
    if (body && body.error && typeof body.error.message === 'string') return body.error.message;
    if (status === 413) return 'The upload is larger than the limit.';
    return 'The request could not be completed.';
  }

  // ----- human verification (widget renders only when the API publishes a site key) -----
  function setupVerification(health) {
    var container = $('verification');
    clear(container);
    if (!health.turnstile || !health.turnstile.required) { text($('run-note'), ''); return; }
    if (!health.turnstile.siteKey) { text($('run-note'), 'Uploads are not available until human verification is configured.'); return; }
    var script = document.createElement('script');
    script.src = VERIFICATION_SCRIPT;
    script.async = true;
    script.onload = function () {
      if (!window.turnstile) return;
      state.verificationWidget = window.turnstile.render(container, {
        sitekey: health.turnstile.siteKey,
        action: ACTION,
        callback: function (token) { state.verificationToken = token; updateRunButton(); },
        'expired-callback': function () { state.verificationToken = null; updateRunButton(); },
        'error-callback': function () { state.verificationToken = null; updateRunButton(); }
      });
    };
    script.onerror = function () { text($('run-note'), 'Human verification could not load; reload to try again.'); };
    document.head.appendChild(script);
  }
  function verificationNeeded() {
    return !!(state.health && state.health.turnstile && state.health.turnstile.required);
  }
  function resetVerification() {
    state.verificationToken = null;
    if (state.verificationWidget != null && window.turnstile) { try { window.turnstile.reset(state.verificationWidget); } catch (e) { /* ignore */ } }
  }
  function updateRunButton() {
    var ready = !!state.file && (!verificationNeeded() || !!state.verificationToken);
    $('run').disabled = !ready;
    if (state.file && verificationNeeded() && !state.verificationToken) text($('run-note'), 'Complete the human verification to run the assessment.');
    else if (state.file) text($('run-note'), 'Ready: ' + state.file.name + ' (' + state.file.format + ').');
  }

  // ----- upload and preview -----
  function detectFormat(name, content) {
    var trimmed = content.replace(/^﻿/, '').trimStart();
    if (/\.json$/i.test(name) || trimmed[0] === '[' || trimmed[0] === '{') return 'arg-json';
    return 'arg-csv';
  }
  function previewRows(format, content) {
    var rows = [], columns = [];
    try {
      if (format === 'arg-json') {
        var doc = JSON.parse(content.replace(/^﻿/, ''));
        var data = Array.isArray(doc) ? doc : (doc && Array.isArray(doc.data) ? doc.data : []);
        rows = data.slice(0, 5).filter(function (r) { return r && typeof r === 'object'; });
        var seen = {};
        rows.forEach(function (r) { Object.keys(r).forEach(function (k) { if (!seen[k] && columns.length < 8) { seen[k] = 1; columns.push(k); } }); });
        return { total: data.length, columns: columns, rows: rows.map(function (r) { return columns.map(function (c) { var v = r[c]; return v == null ? '' : (typeof v === 'object' ? JSON.stringify(v) : String(v)); }); }) };
      }
      var lines = content.replace(/^﻿/, '').split(/\r?\n/).filter(function (l) { return l.trim() !== ''; });
      var delim = [',', ';', '\t'].sort(function (a, b) { return lines[0].split(b).length - lines[0].split(a).length; })[0];
      columns = lines[0].split(delim).slice(0, 8).map(function (c) { return c.replace(/^"|"$/g, ''); });
      rows = lines.slice(1, 6).map(function (l) { return l.split(delim).slice(0, 8).map(function (c) { return c.replace(/^"|"$/g, '').slice(0, 60); }); });
      return { total: Math.max(0, lines.length - 1), columns: columns, rows: rows };
    } catch (e) {
      return { total: 0, columns: [], rows: [], error: 'The file could not be previewed; the server will report what is wrong.' };
    }
  }
  function acceptFile(name, content) {
    var format = detectFormat(name, content);
    state.file = { name: name, text: content, format: format };
    var p = previewRows(format, content);
    var wrap = $('preview-wrap');
    wrap.hidden = false;
    text($('preview-summary'), p.error ? p.error : (p.total + ' rows detected; first ' + p.rows.length + ' shown (' + format + ').'));
    var thead = $('preview').querySelector('thead'), tbody = $('preview').querySelector('tbody');
    clear(thead); clear(tbody);
    var tr = el('tr'); p.columns.forEach(function (c) { tr.appendChild(el('th', null, c)); }); thead.appendChild(tr);
    p.rows.forEach(function (r) { var row = el('tr'); r.forEach(function (c) { row.appendChild(el('td', null, c.length > 80 ? c.slice(0, 80) + '…' : c)); }); tbody.appendChild(row); });
    var warnings = $('preview-warnings'); clear(warnings);
    if (format === 'arg-csv' && !/properties/i.test(p.columns.join(','))) warnings.appendChild(el('li', null, 'No properties column: most criteria will be reported as unknown from this file.'));
    if (content.length > 5 * 1024 * 1024) warnings.appendChild(el('li', null, 'This file is larger than 5 MB and will be refused.'));
    updateRunButton();
  }
  function readFile(file) {
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () { acceptFile(file.name, String(reader.result || '')); };
    reader.readAsText(file);
  }

  // ----- run -----
  function run() {
    if (!state.file) return;
    $('run').disabled = true;
    setStatus('Assessing…');
    post('working');
    var headers = { 'content-type': 'application/json' };
    if (state.verificationToken) headers['x-turnstile-token'] = state.verificationToken;
    var body = JSON.stringify({ format: state.file.format, content: state.file.text, fileName: /^[\w .()-]{1,120}\.(json|csv)$/.test(state.file.name) ? state.file.name : undefined });
    var status = 0;
    api('/api/assessments', { method: 'POST', headers: headers, body: body })
      .then(function (r) { status = r.status; return r.json().catch(function () { return null; }); })
      .then(function (json) {
        if (status !== 201) throw new Error(errorMessage(json, status));
        state.assessment = { id: json.assessmentId, ownerToken: json.ownerToken, expiresAt: json.expiresAt, summary: json.summary, scorecards: json.scorecards, warnings: json.ingestionWarnings || [] };
        return api('/api/assessments/' + encodeURIComponent(json.assessmentId)).then(function (r) { return r.json(); });
      })
      .then(function (full) {
        state.detail = full.assessment;
        return api('/api/assessments/' + encodeURIComponent(state.assessment.id) + '/report.md').then(function (r) { return r.text(); });
      })
      .then(function (md) {
        state.reportMd = md;
        render();
        setStatus('Ready');
        post('ready');
      })
      .catch(function (err) {
        text($('run-note'), err && err.message ? err.message : 'The request could not be completed.');
        setStatus('Ready');
        post('ready');
      })
      .finally(function () { resetVerification(); updateRunButton(); });
  }

  // ----- render results -----
  var FRAMEWORK_LABELS = { 'finops': 'FinOps', 'waf-cost': 'Well-Architected cost', 'zero-trust': 'Zero Trust' };
  function pct(v) { return v == null ? 'n/a' : (Math.round(v * 10) / 10) + ''; }
  function render() {
    var a = state.assessment, d = state.detail;
    $('step-scorecard').hidden = false; $('step-findings').hidden = false; $('step-unknown').hidden = false; $('step-actions').hidden = false;
    var s = a.summary;
    text($('scorecard-summary'), s.resourceCount + ' resources, ' + s.criteriaCount + ' criteria, ' + s.findingsCount + ' findings: ' + s.pass + ' pass, ' + s.fail + ' fail, ' + s.unknown + ' unknown, ' + s.notApplicable + ' not applicable.');
    var cards = $('cards'); clear(cards);
    a.scorecards.filter(function (c) { return c.pillar == null; }).forEach(function (total) {
      var card = el('div', 'card');
      card.appendChild(el('h3', null, FRAMEWORK_LABELS[total.framework] || total.framework));
      card.appendChild(el('div', 'score', total.score == null ? 'n/a' : pct(total.score)));
      var assessed = total.observed + total.unknown;
      card.appendChild(el('div', 'small', 'Coverage ' + (total.coverage == null ? 'n/a' : Math.round(total.coverage * 100) + '%') + '. Score covers ' + total.observed + ' of ' + assessed + ' checks; ' + total.unknown + ' could not be assessed from an export.'));
      var list = el('ul', 'pillars');
      a.scorecards.filter(function (c) { return c.framework === total.framework && c.pillar != null; }).forEach(function (c) {
        var li = el('li'); li.appendChild(el('span', null, c.pillar)); li.appendChild(el('span', 'mono', (c.score == null ? 'n/a' : pct(c.score)) + ' · ' + c.pass + '/' + c.fail + '/' + c.unknown)); list.appendChild(li);
      });
      card.appendChild(list);
      cards.appendChild(card);
    });
    var warn = $('ingestion-warnings'); clear(warn);
    (a.warnings || []).forEach(function (w) { warn.appendChild(el('li', null, w)); });
    var fw = $('f-framework'); clear(fw); fw.appendChild(el('option', null, 'All')).value = '';
    Object.keys(FRAMEWORK_LABELS).forEach(function (k) { var o = el('option', null, FRAMEWORK_LABELS[k]); o.value = k; fw.appendChild(o); });
    renderFindings();
    var ul = $('unknown-list'); clear(ul);
    (d.unknown_by_design || []).forEach(function (u) { var li = el('li'); li.appendChild(el('strong', null, u.topic + ': ')); li.appendChild(document.createTextNode(u.reason + (u.criteria && u.criteria.length ? ' (' + u.criteria.join(', ') + ')' : ''))); ul.appendChild(li); });
    text($('expiry'), state.mode === 'current' ? 'Replaced on every refresh; nothing is stored beyond memory.' : 'Expires ' + new Date(a.expiresAt).toLocaleString() + ' or when you delete it.');
    text($('report'), state.reportMd);
    text($('copy-note'), '');
  }
  function findingState(f) { return f.state === 'observed' ? f.result : f.state; }
  function renderFindings() {
    var d = state.detail; if (!d) return;
    var fw = $('f-framework').value, sev = $('f-severity').value, st = $('f-state').value, q = $('f-search').value.trim().toLowerCase();
    var tbody = $('findings').querySelector('tbody'); clear(tbody);
    var shown = 0;
    d.findings.forEach(function (f, i) {
      if (fw && f.framework !== fw) return;
      if (sev && f.severity !== sev) return;
      if (st && findingState(f) !== st) return;
      if (q && ((f.resourceName || '') + ' ' + f.criterionId + ' ' + (f.resourceType || '')).toLowerCase().indexOf(q) < 0) return;
      shown++;
      var tr = el('tr', 'finding' + (state.selected === i ? ' selected' : ''));
      tr.setAttribute('tabindex', '0');
      tr.appendChild(el('td', 'mono', f.criterionId));
      tr.appendChild(el('td', null, f.severity));
      tr.appendChild(el('td', null, f.resourceName || '(estate)'));
      tr.appendChild(el('td', 'small', f.resourceType || ''));
      var fs = findingState(f);
      tr.appendChild(el('td', 'state state-' + fs, fs));
      tr.appendChild(el('td', 'small', f.reason));
      var open = function () { state.selected = i; renderDetail(f); renderFindings(); };
      tr.addEventListener('click', open);
      tr.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      tbody.appendChild(tr);
    });
    text($('findings-count'), shown + ' of ' + d.findings.length + ' findings');
  }
  function renderDetail(f) {
    var dl = $('detail-list'); clear(dl);
    var add = function (k, v) { dl.appendChild(el('dt', null, k)); var dd = el('dd'); if (v && v.href) { var a = el('a', null, v.href); a.href = v.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; dd.appendChild(a); } else text(dd, v); dl.appendChild(dd); };
    add('Criterion', f.criterionId + ' (' + f.framework + ' / ' + f.pillar + ', ' + f.severity + ')');
    add('Resource', (f.resourceName || '(estate)') + (f.resourceId ? ' — ' + f.resourceId : ''));
    add('State', findingState(f));
    add('Reason', f.reason);
    add('Evidence path', f.evidence && f.evidence.path ? f.evidence.path : '—');
    add('Observed', f.evidence && f.evidence.observed != null ? JSON.stringify(f.evidence.observed) : '—');
    add('Expected', f.evidence && f.evidence.expected != null ? JSON.stringify(f.evidence.expected) : '—');
    add('Remediation', f.remediation);
    if (/^https:\/\/(learn\.microsoft\.com|www\.finops\.org)\//.test(f.learnUrl)) add('Learn more', { href: f.learnUrl });
    $('detail').hidden = false;
  }

  // ----- actions -----
  function bundlePath() {
    return state.mode === 'current' ? '/api/assessments/current/bundle.zip' : '/api/assessments/' + encodeURIComponent(state.assessment.id) + '/bundle.zip';
  }
  function downloadBundle() {
    api(bundlePath())
      .then(function (r) { if (!r.ok) throw new Error('download'); return r.blob(); })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a'); a.href = url; a.download = 'assessment-' + (state.mode === 'current' ? 'current' : state.assessment.id.slice(0, 8)) + '.zip';
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
        text($('copy-note'), 'If the download did not start, use Copy report: downloads can be blocked inside an embedded pane.');
      })
      .catch(function () { text($('copy-note'), 'The bundle could not be downloaded here; use Copy report instead.'); });
  }
  function copyReport() {
    var done = function () { text($('copy-note'), 'Report copied to the clipboard as Markdown.'); };
    var fallback = function () {
      try {
        var pre = $('report'); var range = document.createRange(); range.selectNodeContents(pre);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
        var ok = document.execCommand('copy'); sel.removeAllRanges();
        text($('copy-note'), ok ? 'Report copied to the clipboard as Markdown.' : 'Select the report text below and copy it.');
      } catch (e) { text($('copy-note'), 'Select the report text below and copy it.'); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(state.reportMd).then(done, fallback); else fallback();
  }
  function deleteNow() {
    if (!state.assessment) return;
    if (!window.confirm('Delete this assessment and its files now?')) return;
    api('/api/assessments/' + encodeURIComponent(state.assessment.id), { method: 'DELETE' })
      .finally(function () {
        state.assessment = null; state.detail = null; state.reportMd = ''; state.selected = null;
        ['step-scorecard', 'step-findings', 'step-unknown', 'step-actions'].forEach(function (id) { $(id).hidden = true; });
        $('detail').hidden = true;
        updateRunButton();
        text($('run-note'), 'Your data was deleted.');
      });
  }

  // ----- wiring -----
  function wire() {
    var dz = $('dropzone');
    ['dragenter', 'dragover'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('active'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('active'); }); });
    dz.addEventListener('drop', function (e) { if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) readFile(e.dataTransfer.files[0]); });
    dz.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('file').click(); } });
    $('file').addEventListener('change', function () { readFile($('file').files[0]); });
    $('use-sample').addEventListener('click', function () {
      fetch('/api/sample.json', { credentials: 'omit' }).then(function (r) { return r.text(); }).then(function (t) { acceptFile('sample-resource-graph.json', t); });
    });
    $('run').addEventListener('click', run);
    ['f-framework', 'f-severity', 'f-state'].forEach(function (id) { $(id).addEventListener('change', renderFindings); });
    $('f-search').addEventListener('input', renderFindings);
    $('download-bundle').addEventListener('click', downloadBundle);
    $('copy-report').addEventListener('click', copyReport);
    $('delete').addEventListener('click', deleteNow);
    $('refresh').addEventListener('click', requestRefresh);
  }

  function boot() {
    wire();
    setStatus('Checking…');
    fetch('/api/health', { credentials: 'omit', headers: { accept: 'application/json' } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        var h = res.body || {};
        state.siteOrigins = Array.isArray(h.siteOrigins) ? h.siteOrigins.filter(function (o) { return typeof o === 'string' && /^https?:\/\/[^\s/]+$/.test(o); }) : [];
        post('loading');
        if (!res.ok || h.ok !== true || h.id !== ADDON_ID) { unavailable(); return; }
        state.health = h;
        applyEdition(h);
        setupVerification(h);
        setStatus('Ready');
        post('ready');
        if (state.mode === 'current') loadCurrent();
      })
      .catch(function () { unavailable(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
