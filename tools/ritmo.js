// Tablero Supply Chain Don Maíz · subpestaña Ritmo de venta (Nivel de servicio). Forecast del mes vs cantidad facturada (dataset ritmo).
// 27-nov-2026: filtros con buscador (canal, cliente, bodega, SKU), tablas por canal (con "Cómo vamos" = % de la cuota del canal acumulada hasta ayer),
// por cliente (+ referencia y bodega) y por SKU (+ cliente y bodega).
window.RT = (() => {
const all = () => { const d = dash.data('ritmo'); return d.status === 'ok' && Array.isArray(d.data) ? d.data : null; };
const V = () => { const a = all(); return a ? a.filter((r) => r.tipo !== 'c') : null; };
const meses = () => [...new Set((V() || []).map((r) => r.mes))].sort();
const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
const lab = { canal: (r) => NS.nom(r.canal), cli: (r) => NS.nom(r.cli), bod: (r) => r.bod, ref: (r) => r.ref + ' · ' + r.desc };
const KS = ['canal', 'cli', 'bod', 'ref'];
const pasa = (r, p, sin) => KS.every((k) => { if (k === sin) return true; const q = norm(p['rt_' + k]); if (!q) return true; const t = norm(lab[k](r)); return t === q || t.includes(q); });
const sel = (sin) => { const R = V(); if (!R) return null; const ms = meses(), p = dash.params(), cr = ms.filter((m) => R.some((r) => r.mes === m && r.real > 0));
const mes = ms.includes(p.rt_mes) ? p.rt_mes : cr[cr.length - 1] || ms[0];
return { mes, p, R: R.filter((r) => r.mes === mes && pasa(r, p, sin)) }; };
// Real = solo lo facturado en las líneas del forecast del mes (fl = 1), como el comparativo del gerente; lo demás es 'fuera del forecast'.
const sum = (v) => ({ fc: d3.sum(v, (r) => r.fc), real: d3.sum(v, (r) => (r.fl === 0 ? 0 : r.real)), kg: d3.sum(v, (r) => (r.fl === 0 ? 0 : r.kg || 0)), fuera: d3.sum(v, (r) => (r.fl === 0 ? r.real : 0)) });
const pct = (o) => (o.fc > 0 ? o.real / o.fc : null);
const u = (v) => DM.f0.format(Math.round(v)), sg = (v) => (Math.round(v) > 0 ? '+' : Math.round(v) < 0 ? '−' : '') + u(Math.abs(v));
const pt = (v) => (v == null ? 'Sin forecast' : DM.f1.format(v * 100) + ' %');
const col = (v) => (v == null ? 'var(--color-fg-muted)' : v >= 0.95 ? 'var(--dm-ok)' : v >= 0.85 ? 'var(--dm-sob)' : 'var(--dm-crit)');
const mesL = (k) => NS.MES[+k.slice(4) - 1] + ' ' + k.slice(0, 4);
// "Cómo vamos": % de la cuota del mes acumulada hasta ayer (hora Colombia). Mes ya cerrado = 100 %; mes futuro = 0 %; sin cuota = null.
const ayer = () => { const d = new Date(Date.now() - 5 * 3600e3 - 864e5); return d.toISOString().slice(0, 10); };
const como = (mes, canales) => { const a = all(); if (!a) return null; const c = a.filter((r) => r.tipo === 'c' && r.mes === mes && (!canales || canales.includes(r.canal)));
const t = d3.sum(c, (r) => r.cv); if (!(t > 0)) return null; const y = ayer(), ym = y.slice(0, 7).replace('-', '');
if (mes < ym) return 1; if (mes > ym) return 0; return d3.sum(c.filter((r) => r.fecha <= y), (r) => r.cv) / t; };
const grp = (R, key) => d3.rollups(R, sum, (r) => r[key]).map(([k, o]) => ({ k, ...o })).sort((a, b) => b.fc - a.fc || b.real - a.real);
const bars = (el, items, label) => {
el.replaceChildren(); if (!items.length) return;
const W = el.clientWidth, H = 330, ml = 54, svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', label);
const x0 = d3.scaleBand(items.map((d) => d.k), [ml, W - 8]).padding(0.22), x1 = d3.scaleBand(['fc', 'real'], [0, x0.bandwidth()]).padding(0.06);
const rot = Math.max(...items.map((d) => DM.textW(svg, NS.nom(d.k), 'dm-axis-t'))) + 6 > x0.step(), MB = rot ? 78 : 40;
const y = d3.scaleLinear([0, (d3.max(items, (d) => Math.max(d.fc, d.real)) || 1) * 1.12], [H - MB, 22]).nice();
svg.append('g').attr('transform', `translate(${ml},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W - ml - 8)).tickFormat((v) => DM.fc.format(v))).call(DM.cleanAxis).call((g) => g.select('.domain').remove())
.selectAll('text').style('font-weight', 700).style('fill', 'var(--color-fg)');
const g = svg.append('g').attr('transform', `translate(0,${H - MB})`).call(d3.axisBottom(x0).tickSize(0).tickPadding(8).tickFormat((k) => NS.nom(k))).call(DM.cleanAxis);
g.selectAll('text').style('font-weight', 800).style('font-size', '12px').style('fill', 'var(--color-fg)');
if (rot) g.selectAll('text').attr('text-anchor', 'end').attr('dx', '-0.4em').attr('dy', '0.5em').attr('transform', 'rotate(-30)');
items.forEach((d) => { const gg = svg.append('g').attr('transform', `translate(${x0(d.k)},0)`), p = pct(d);
[['fc', 'var(--dm-orange-2)'], ['real', 'var(--dm-green)']].forEach(([s, c]) => gg.append('rect').attr('x', x1(s)).attr('width', x1.bandwidth()).attr('y', y(d[s])).attr('height', y(0) - y(d[s])).attr('rx', 2).style('fill', c));
gg.append('text').attr('class', 'dm-val dm-halo').attr('text-anchor', 'middle').attr('x', x0.bandwidth() / 2).attr('y', y(Math.max(d.fc, d.real)) - 6).style('font-weight', 800).style('fill', col(p))
.text(p == null ? 'Sin fcst' : DM.f0.format(p * 100) + ' %'); });
const tip = DM.tipFor(el);
svg.append('g').selectAll('rect').data(items).join('rect').attr('x', (d) => x0(d.k)).attr('width', x0.bandwidth()).attr('y', 0).attr('height', H - MB).attr('fill', 'transparent')
.on('mousemove', (e, d) => DM.showTip(tip, el, x0(d.k) + x0.bandwidth() / 2, 30, [NS.nom(d.k), 'Forecast: ' + u(d.fc), 'Real: ' + u(d.real), 'Cumplimiento: ' + pt(pct(d)), 'Desviación: ' + sg(d.real - d.fc)]))
.on('mouseleave', () => { tip.hidden = true; });
};
// Celdas de una fila: pre() pone las primeras columnas; luego forecast, real, kilos, % y (opcional) desviación.
const celdas = (tr, o, pre, desv) => { const c = (t, k, st) => { const td = document.createElement('td'); if (k) td.className = k; td.textContent = t; if (st) td.style.color = st; tr.append(td); return td; };
pre(c); const p = pct(o), fa = Math.round(o.fc - o.real); c(u(o.fc), 'lc-n'); c(u(o.real), 'lc-n'); c(u(o.kg), 'lc-n'); c(pt(p), 'lc-n', col(p));
c(o.fc > 0 ? (fa > 0 ? u(fa) : 'Cumplido') : '—', 'lc-n', o.fc > 0 ? (fa > 0 ? 'var(--dm-crit)' : 'var(--dm-ok)') : null); c(o.fuera ? u(o.fuera) : '—', 'lc-n');
if (desv) { const dv = Math.round(o.real - o.fc); c(sg(dv), 'lc-n', dv < 0 ? 'var(--dm-crit)' : dv > 0 ? 'var(--dm-ok)' : null); } return c; };
const btn = (set, key, txt, redraw) => { const open = set.has(key), b = document.createElement('button'); b.type = 'button'; b.className = 'iv-exp'; b.textContent = open ? '−' : '+';
b.setAttribute('aria-expanded', String(open)); b.setAttribute('aria-label', (open ? 'Ocultar ' : 'Ver ') + txt); b.onclick = () => { if (open) set.delete(key); else set.add(key); redraw(); }; return b; };
return { all, V, meses, sel, sum, pct, u, sg, pt, col, mesL, como, grp, bars, celdas, btn, lab, KS, norm };
})();
if (!window.RTopen || !window.RTopen.cli || !window.RTopen.ref) window.RTopen = { cli: new Set(), ref: new Set() };
// Filtros con buscador: <input type="search" list=…> en la página; aquí se dibujan las opciones (datalist) y se escucha el cambio.
dash.draw('rt-sel-mes', (el) => { const s = RT.sel(); if (!s) { el.replaceChildren(); return; } el.replaceChildren(...RT.meses().map((k) => new Option(RT.mesL(k), k))); el.value = s.mes; el.onchange = () => dash.setParams({ rt_mes: el.value }); });
RT.KS.forEach((k) => dash.draw('rt-l-' + k, (dl) => { const s = RT.sel(k); if (!s) { dl.replaceChildren(); return; }
const ops = [...new Set(s.R.map(RT.lab[k]))].sort((a, b) => a.localeCompare(b, 'es', { numeric: true })); dl.replaceChildren(...ops.map((t) => new Option(t)));
document.querySelectorAll(`input.rt-q[data-k="${k}"]`).forEach((i) => { if (document.activeElement !== i) i.value = s.p['rt_' + k] || ''; }); }));
document.querySelectorAll('input.rt-q').forEach((i) => { const set = () => dash.setParams({ ['rt_' + i.dataset.k]: i.value.trim() || null }); i.addEventListener('change', set); i.addEventListener('search', set); });
dash.draw('rt-kpis', (el) => {
const s = RT.sel(); if (!s) { DM.fail(el, dash.data('ritmo').status); return; }
const t = RT.sum(s.R), p = RT.pct(t), e = NS.est(), g = e && e.guardado && e.guardado.slice(0, 7).replace('-', '') === s.mes ? e.guardado : null;
const tile = (l, v, d, c) => { const w = document.createElement('div'); w.className = 'dm-tile'; [[l, 'dm-tile-l'], [v, 'dm-tile-v'], [d, 'dm-tile-d']].forEach(([x, k]) => { const sp = document.createElement('span'); sp.className = k; sp.textContent = x; if (c && k === 'dm-tile-v') sp.style.color = c; w.append(sp); }); return w; };
el.replaceChildren(tile('Total forecast del mes', RT.u(t.fc), 'Paquetes · ' + RT.mesL(s.mes)), tile('Cantidad facturada', RT.u(t.real), (g ? 'Al ' + DM.fDate(g) + ' · ' : '') + RT.u(t.kg) + ' kg · fuera del forecast: ' + RT.u(t.fuera)),
tile('Cumplimiento del mes', RT.pt(p), 'Desviación: ' + RT.sg(t.real - t.fc) + ' paquetes', RT.col(p)));
});
dash.draw('rt-canal', (el) => { const s = RT.sel(); if (!s) { DM.fail(el, dash.data('ritmo').status); return; } RT.bars(el, RT.grp(s.R, 'canal'), 'Forecast vs real por canal'); });
dash.draw('rt-seg', (el) => { const s = RT.sel(); if (!s) { DM.fail(el, dash.data('ritmo').status); return; } RT.bars(el, RT.grp(s.R, 'seg'), 'Forecast vs real por segmento'); });
// Tabla 1 · por canal, con "Cómo vamos" y brecha (cumplimiento − cómo vamos).
const rtCv = (tr, o, cv, c) => { const p = RT.pct(o); c(cv == null ? '—' : DM.f1.format(cv * 100) + ' %', 'lc-n');
const b = p == null || cv == null ? null : p - cv; c(b == null ? '—' : (b >= 0 ? '+' : '−') + DM.f1.format(Math.abs(b) * 100) + ' pp', 'lc-n', b == null ? null : b >= 0 ? 'var(--dm-ok)' : 'var(--dm-crit)'); };
dash.draw('rt-t1', (tb) => { tb.replaceChildren(); const s = RT.sel(); if (!s) return;
RT.grp(s.R, 'canal').forEach((o) => { const tr = document.createElement('tr'); tr.className = 'lc-row'; const cv = RT.como(s.mes, [o.k]); rtCv(tr, o, cv, RT.celdas(tr, o, (c) => c(NS.nom(o.k), 'lc-ref'))); tb.append(tr); }); });
dash.draw('rt-t1f', (tf) => { tf.replaceChildren(); const s = RT.sel(); if (!s) return; const tr = document.createElement('tr'), cs = [...new Set(s.R.map((r) => r.canal))];
rtCv(tr, RT.sum(s.R), RT.como(s.mes, cs), RT.celdas(tr, RT.sum(s.R), (c) => c('Total'))); tf.append(tr); });
// Tabla 2 · por cliente (en Moderno, la cadena; en los demás, el canal) con + por referencia y bodega.
const rtT2 = (tb) => { tb.replaceChildren(); const s = RT.sel(); if (!s) return; const O = window.RTopen.cli;
d3.rollups(s.R, (v) => v, (r) => RT.lab.cli(r)).map(([k, v]) => ({ k, v, ...RT.sum(v) })).sort((a, b) => b.fc - a.fc || b.real - a.real).forEach((o) => {
const tr = document.createElement('tr'); tr.className = 'lc-row'; RT.celdas(tr, o, (c) => { c('', 'lc-c').append(RT.btn(O, o.k, 'referencias de ' + o.k, () => rtT2(tb))); c(o.k, 'lc-ref'); }); tb.append(tr);
if (O.has(o.k)) o.v.slice().sort((a, b) => b.fc - a.fc || b.real - a.real).forEach((x) => { const ch = document.createElement('tr'); ch.className = 'iv-child';
RT.celdas(ch, x, (c) => { c(''); c(x.ref + ' · ' + x.desc + ' — ' + x.bod, 'iv-city').title = x.desc; }); tb.append(ch); }); }); };
dash.draw('rt-t2', rtT2);
dash.draw('rt-t2f', (tf) => { tf.replaceChildren(); const s = RT.sel(); if (!s) return; const tr = document.createElement('tr'); RT.celdas(tr, RT.sum(s.R), (c) => { c(''); c('Total'); }); tf.append(tr); });
// Tabla 3 · por SKU con + por cliente y bodega.
const rtTq = (s) => { const q = RT.norm(s.p.rt_tq); if (!q) return s.R; const num = /^\d+$/.test(q); return s.R.filter((r) => r.ref.toLowerCase().startsWith(q) || (!num && RT.norm(r.desc).includes(q))); };
document.querySelectorAll('input.rt-qt').forEach((i) => i.addEventListener('input', () => dash.setParams({ rt_tq: i.value.trim() || null })));
const rtT3 = (tb) => { tb.replaceChildren(); const s = RT.sel(); if (!s) return; const O = window.RTopen.ref;
document.querySelectorAll('input.rt-qt').forEach((i) => { if (document.activeElement !== i) i.value = s.p.rt_tq || ''; });
d3.rollups(rtTq(s), (v) => v, (r) => r.ref).map(([k, v]) => ({ k, v, desc: v[0].desc, seg: v[0].seg, ...RT.sum(v) })).sort((a, b) => b.fc - a.fc || b.real - a.real).forEach((o) => {
const tr = document.createElement('tr'); tr.className = 'lc-row';
RT.celdas(tr, o, (c) => { c('', 'lc-c').append(RT.btn(O, o.k, 'clientes y bodegas de ' + o.k, () => rtT3(tb))); c(o.k, 'lc-ref'); c(o.desc).title = o.desc; c(NS.nom(o.seg)); }, true); tb.append(tr);
if (O.has(o.k)) o.v.slice().sort((a, b) => b.fc - a.fc || b.real - a.real).forEach((x) => { const ch = document.createElement('tr'); ch.className = 'iv-child';
RT.celdas(ch, x, (c) => { c(''); c(RT.lab.cli(x) + ' — ' + x.bod, 'iv-city').colSpan = 3; }, true); tb.append(ch); }); }); };
dash.draw('rt-t', rtT3);
dash.draw('rt-tot', (tf) => { tf.replaceChildren(); const s = RT.sel(); if (!s) return; const tr = document.createElement('tr');
const R = rtTq(s); RT.celdas(tr, RT.sum(R), (c) => { c(''); c('Total · ' + new Set(R.map((r) => r.ref)).size + ' referencias').colSpan = 3; }, true); tf.append(tr); });
