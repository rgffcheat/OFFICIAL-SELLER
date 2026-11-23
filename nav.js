/* v18 - no more full page refresh: forms inside the page content are sent in the background and only the content is replaced */
(function () {
  if (window.__rgAjax) return; window.__rgAjax = 1;
  var busy = false, st = document.createElement('style');
  st.textContent = '.rgtoast{position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:99999;display:flex;flex-direction:column;gap:8px;width:min(92vw,460px);pointer-events:none}' +
    '.rgtoast div{pointer-events:auto;padding:12px 16px;border-radius:12px;font-size:14px;font-weight:600;color:#fff;background:#111827e6;border:1px solid #ffffff22;box-shadow:0 8px 30px #0008;backdrop-filter:blur(10px);animation:rgin .18s ease}' +
    '.rgtoast .ok{border-color:#34d399;background:#064e3bf0}.rgtoast .err{border-color:#f87171;background:#7f1d1df0}' +
    '@keyframes rgin{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}' +
    '.rgbusy{opacity:.6;pointer-events:none;transition:opacity .15s}';
  document.head.appendChild(st);
  var tb = document.createElement('div'); tb.className = 'rgtoast'; document.body.appendChild(tb);
  function toast(msg, cls) {
    var d = document.createElement('div'); d.className = cls || ''; d.textContent = msg; tb.appendChild(d);
    setTimeout(function () { d.style.transition = 'opacity .3s'; d.style.opacity = 0; setTimeout(function () { d.remove(); }, 320); }, 3800);
  }
  window.rgToast = toast;
  function runScripts(root) {
    root.querySelectorAll('script').forEach(function (o) {
      var n = document.createElement('script');
      if (o.src) { n.src = o.src; }
      else { n.text = o.textContent.replace(/(^|[;\n])(\s*)(?:const|let)\s/g, '$1$2var '); }  /* re-running a page script must not fail on "already declared" */
      o.parentNode.replaceChild(n, o);
    });
  }
  function fileName(res) {
    var m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(res.headers.get('Content-Disposition') || '');
    return m ? decodeURIComponent(m[1]) : 'download';
  }
  function swap(html, url, same) {
    var d = new DOMParser().parseFromString(html, 'text/html');
    var nw = d.querySelector('.wrap'), ow = document.querySelector('.wrap');
    if (!nw || !ow) { location.reload(); return; }
    var y = window.scrollY, scripts = Array.prototype.slice.call(nw.querySelectorAll('script'));
    var flashes = Array.prototype.slice.call(nw.querySelectorAll(':scope > .flash'));
    flashes.forEach(function (f) { toast(f.textContent.trim(), /err/.test(f.className) ? 'err' : 'ok'); f.remove(); });
    ow.innerHTML = nw.innerHTML;
    runScripts(ow);
    if (d.title) document.title = d.title;
    var sb = d.getElementById('sbal'), ob = document.getElementById('sbal'); if (sb && ob) ob.textContent = sb.textContent;
    var na = d.body.querySelectorAll('a[href]'), oa = document.body.querySelectorAll('a[href]');
    if (na.length === oa.length) { for (var i = 0; i < na.length; i++) { if (!ow.contains(oa[i]) && oa[i].className !== na[i].className) oa[i].className = na[i].className; } }
    if (same) window.scrollTo(0, y); else window.scrollTo(0, 0);
  }
  function go(url, opts, btn) {
    return fetch(url, opts).then(function (res) {
      var ct = res.headers.get('Content-Type') || '';
      if (res.headers.get('Content-Disposition') || !/text\/html/i.test(ct)) {
        return res.blob().then(function (b) {
          var a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = fileName(res);
          document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 4000);
          toast('Downloaded', 'ok');
        });
      }
      var here = location.pathname, there = new URL(res.url).pathname;
      return res.text().then(function (html) {
        if (!res.ok) {                                                   /* error page (404 / 500): keep the current page, just tell the user */
          if (res.status === 404 || res.status === 401 || res.status === 403) { toast('Page not found - opening Products', 'err'); setTimeout(function () { location.assign('/admin/products'); }, 900); }
          else { toast('Server error (' + res.status + ') - please try again', 'err'); }
          return;
        }
        if (res.redirected && there !== here) { location.assign(res.url); return; }       /* went to another page: open it normally */
        if (res.redirected) history.replaceState(null, '', res.url);
        swap(html, res.url, true);
      });
    });
  }
  window.rgReload = function () { return go(location.href, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } }).catch(function () { location.reload(); }); };
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (e.defaultPrevented || !(f instanceof HTMLFormElement) || busy) { if (busy && f instanceof HTMLFormElement && !e.defaultPrevented && f.closest('.wrap')) e.preventDefault(); return; }
    /* v18.6: read attributes with getAttribute - a form that has a field named "action" (every admin form does) made f.action the <input> element, so the background POST went to /admin/[object HTMLInputElement] = Not Found and nothing was saved */
    if ((f.getAttribute('method') || 'get').toLowerCase() !== 'post' || f.getAttribute('target') || f.hasAttribute('data-noajax') || !f.closest('.wrap')) return;
    var act = new URL(f.getAttribute('action') || location.href, location.href);
    if (act.origin !== location.origin) return;
    e.preventDefault();
    var fd; try { fd = new FormData(f, e.submitter || undefined); } catch (x) { fd = new FormData(f); if (e.submitter && e.submitter.name) fd.append(e.submitter.name, e.submitter.value); }
    var btn = e.submitter, old = btn ? btn.innerHTML : '';
    busy = true; f.classList.add('rgbusy'); if (btn) { btn.disabled = true; btn.innerHTML = '...'; }
    go(act.href, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .catch(function () { toast('Network problem - please try again', 'err'); })
      .then(function () { busy = false; f.classList.remove('rgbusy'); if (btn && document.contains(btn)) { btn.disabled = false; btn.innerHTML = old; } });
  }, false);
})();
