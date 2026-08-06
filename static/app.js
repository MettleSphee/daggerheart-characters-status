/* Shared helpers for the Daggerheart live status app */

let CONDITIONS = [];

function setConditions(list) {
  CONDITIONS = list || [];
}

function getCondition(name) {
  for (let i = 0; i < CONDITIONS.length; i++) {
    if (CONDITIONS[i].name === name) return CONDITIONS[i];
  }
  return null;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function hashColors(name) {
  let h = 0;
  const s = String(name || '');
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  const hue = h % 360;
  return { light: 'hsl(' + hue + ', 55%, 42%)', dark: 'hsl(' + hue + ', 55%, 25%)' };
}

function conditionColors(name) {
  const cond = getCondition(name);
  if (cond && cond.color_light && cond.color_dark) {
    return { light: cond.color_light, dark: cond.color_dark };
  }
  return hashColors(name);
}

function buildBadgeHTML(name, cond, extraClass) {
  const colors = (cond && cond.color_light && cond.color_dark)
    ? { light: cond.color_light, dark: cond.color_dark }
    : hashColors(name);
  const icon = cond && cond.icon_available && cond.icon ? cond.icon : null;
  const iconHTML = icon
    ? '<img class="badge-icon" src="/static/icons/' + encodeURI(icon) + '" alt="" onerror="this.style.display=\'none\'">'
    : '';
  return '<span class="badge' + (extraClass ? ' ' + extraClass : '') + '" title="' + escapeHtml(cond ? cond.description : name) + '" style="background:radial-gradient(circle at 30% 30%,' + colors.light + ',' + colors.dark + ')">' +
    iconHTML +
    '<span class="badge-name">' + escapeHtml(name) + '</span></span>';
}

function badgeHTML(name, extraClass) {
  return buildBadgeHTML(name, getCondition(name), extraClass);
}

function marksStatusHTML(marked, total, scarred) {
  let html = '<div class="marks">';
  for (let i = 0; i < total; i++) {
    const isScarred = scarred > 0 && i >= total - scarred;
    const on = marked[i] && !isScarred;
    let cls = 'mark';
    if (on) cls += ' mark-on';
    else if (isScarred) cls += ' mark-scar';
    html += '<span class="' + cls + '">' + (on ? '&#10003;' : isScarred ? '&#10007;' : '') + '</span>';
  }
  return html + '</div>';
}

function trackHTML(label, marked, total, scarred) {
  return '<div class="track"><div class="track-label"><span>' + escapeHtml(label) + '</span><span>' + marked.length + '/' + total + '</span></div>' +
    marksStatusHTML(marked, total, scarred) + '</div>';
}

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function showToast(message, isError) {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.toggle('error', !!isError);
  toast.classList.add('show');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(function () { toast.classList.remove('show'); }, 2600);
}

/* ---------- SSE client ---------- */

function connectStream(onUpdate) {
  const es = new EventSource('/api/stream');
  es.addEventListener('update', function (e) {
    let msg = null;
    try {
      msg = JSON.parse(e.data);
    } catch (err) { /* ignore */ }
    if (msg && msg.client_id === CLIENT_ID) return;
    if (onUpdate) onUpdate();
  });
  es.onopen = function () {
    const dot = document.querySelector('.conn-dot');
    if (dot) dot.classList.add('on');
  };
  es.onerror = function () {
    const dot = document.querySelector('.conn-dot');
    if (dot) dot.classList.remove('on');
  };
  return es;
}

/* Refresh immediately, or once the user stops editing a focused field. */
function scheduleRefresh(renderFn) {
  const ae = document.activeElement;
  if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.tagName === 'TEXTAREA')) {
    const done = function () {
      ae.removeEventListener('blur', done);
      renderFn();
    };
    ae.addEventListener('blur', done, { once: true });
    return;
  }
  renderFn();
}

function fetchJSON(url) {
  return fetch(url).then(function (r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  });
}

function postJSON(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(function (r) {
    if (!r.ok) return r.json().then(function (d) { throw new Error(d.message || 'HTTP ' + r.status); });
    return r.json();
  });
}

function deleteJSON(url, body) {
  return fetch(url, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  }).then(function (r) {
    if (!r.ok) return r.json().then(function (d) { throw new Error(d.message || 'HTTP ' + r.status); });
    return r.json();
  });
}

/* A short-lived client id so we can ignore our own broadcasts. */
const CLIENT_ID = Math.random().toString(36).slice(2) + Date.now().toString(36);
