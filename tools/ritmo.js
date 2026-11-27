// Tablero Supply Chain Don Maíz · subpestaña Ritmo de venta (Nivel de servicio). Forecast del mes vs cantidad facturada (dataset ritmo). 27-nov-2026.
window.RT = (() => {
const D = () => { const d = dash.data('ritmo'); return d.status === 'ok' && Array.isArray(d.data) ? d.data : null; };
const meses = () => [...new Set((D() || []).map((r) => r.mes))].sort();
const sel = () => { const R = D(); if (!R) return null; const ms = meses(), p = dash.params(), cr = ms.filter((m) => R.some((r) => r.mes === m && r.real > 0));
const mes = ms.includes(p.rt_mes) ? p.rt_mes : cr[cr.length - 1] || ms[0], cs = [...new Set(R.filter((r) => r.mes === mes).map((r) => r.canal))].sort(), canal = cs.includes(p.rt_canal) ? p.rt_canal : '';
return { mes, canal, cs, R: R.filter((r) => r.mes === mes && (!canal || r.canal === canal)) }; };
const sum = (v) => ({ fc: d3.sum(v, (r) => r.fc), real: d3.sum(v, (r) => r.real) });
const pct = (o) => (o.fc > 0 ? o.real / o.fc : null);
const u = (v) => DM.f0.format(Math.round(v)), sg = (v) => (Math.round(v) > 0 ? '+' : Math.round(v) < 0 ? '−' : '') + u(Math.abs(v));
const pt = (v) => (v == null ? 'Sin forecast' : DM.f1.format(v * 100) + ' %');
const col = (v) => (v == null ? 'var(--color-fg-muted)' : v >= 0.95 ? 'var(--dm-ok)' : v >= 0.85 ? 'var(--dm-sob)' : 'var(--dm-crit)');
const mesL = (k) => NS.MES[+k.slice(4) - 1] + ' ' + k.slice(0, 4);
const grp = (R, key) => d3.rollups(R, sum, (r) => r[key]).map(([k, o]) => ({ k, ...o })).sort((a, b) => b.fc - a.fc || b.real - a.real);
const filas = () => { const s = sel(); if (!s) return null;
return d3.rollups(s.R, (v) => ({ ref: v[0].ref, desc: v[0].desc, seg: v[0].seg, ...sum(v), canales: v.slice().sort((a, b) => b.fc - a.fc || b.real - a.real) }), (r) => r.ref).map(([, o]) => o).sort((a, b) => b.fc - a.fc || b.real - a.real); };
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
const celdas = (tr, o, pre) => { const c = (t, k, st) => { const td = document.createElement('td'); if (k) td.className = k; td.textContent = t; if (st) td.style.color = st; tr.append(td); return td; };
pre(c); const p = pct(o), dv = Math.round(o.real - o.fc); c(u(o.fc), 'lc-n'); c(u(o.real), 'lc-n'); c(pt(p), 'lc-n', col(p)); c(sg(dv), 'lc-n', dv < 0 ? 'var(--dm-crit)' : dv > 0 ? 'var(--dm-ok)' : null); };
return { D, meses, sel, sum, pct, u, sg, pt, col, mesL, grp, filas, bars, celdas };
})();
dash.draw('rt-sel-mes', (el) => { const s = RT.sel(); if (!s) { el.replaceChildren(); return; } el.replaceChildren(...RT.meses().map((k) => new Option(RT.mesL(k), k))); el.value = s.mes; el.onchange = () => dash.setParams({ rt_mes: el.value }); });
dash.draw('rt-sel-canal', (el) => { const s = RT.sel(); if (!s) { el.replaceChildren(); return; } el.replaceChildren(new Option('Todos', ''), ...s.cs.map((c) => new Option(NS.nom(c), c))); el.value = s.canal; el.onchange = () => dash.setParams({ rt_canal: el.value || null }); });
dash.draw('rt-kpis', (el) => {
const s = RT.sel(); if (!s) { DM.fail(el, dash.data('ritmo').status); return; }
const t = RT.sum(s.R), p = RT.pct(t), e = NS.est(), g = e && e.guardado && e.guardado.slice(0, 7).replace('-', '') === s.mes ? e.guardado : null, can = s.canal ? ' · ' + NS.nom(s.canal) : '';
const tile = (l, v, d, c) => { const w = document.createElement('div'); w.className = 'dm-tile'; [[l, 'dm-tile-l'], [v, 'dm-tile-v'], [d, 'dm-tile-d']].forEach(([x, k]) => { const sp = document.createElement('span'); sp.className = k; sp.textContent = x; if (c && k === 'dm-tile-v') sp.style.color = c; w.append(sp); }); return w; };
el.replaceChildren(tile('Total forecast del mes', RT.u(t.fc), 'Paquetes · ' + RT.mesL(s.mes) + can), tile('Cantidad facturada', RT.u(t.real), g ? 'Paquetes facturados al ' + DM.fDate(g) : 'Paquetes facturados' + can),
tile('Cumplimiento del mes', RT.pt(p), 'Desviación: ' + RT.sg(t.real - t.fc) + ' paquetes', RT.col(p)));
});
dash.draw('rt-canal', (el) => { const s = RT.sel(); if (!s) { DM.fail(el, dash.data('ritmo').status); return; } RT.bars(el, RT.grp(s.R, 'canal'), 'Forecast vs real por canal'); });
dash.draw('rt-seg', (el) => { const s = RT.sel(); if (!s) { DM.fail(el, dash.data('ritmo').status); return; } RT.bars(el, RT.grp(s.R, 'seg'), 'Forecast vs real por segmento'); });
window.RTopen = window.RTopen || new Set();
const rtT = (tb) => { tb.replaceChildren(); const F = RT.filas(); if (!F) return;
F.forEach((r) => { const open = window.RTopen.has(r.ref), tr = document.createElement('tr'); tr.className = 'lc-row';
RT.celdas(tr, r, (c) => { const b = c('', 'lc-c'), btn = document.createElement('button'); btn.type = 'button'; btn.className = 'iv-exp'; btn.textContent = open ? '−' : '+';
btn.setAttribute('aria-expanded', String(open)); btn.setAttribute('aria-label', (open ? 'Ocultar' : 'Ver') + ' canales de ' + r.ref);
btn.onclick = () => { if (open) window.RTopen.delete(r.ref); else window.RTopen.add(r.ref); rtT(tb); }; b.append(btn); c(r.ref, 'lc-ref'); c(r.desc).title = r.desc; c(NS.nom(r.seg)); });
tb.append(tr);
if (open) r.canales.forEach((x) => { const ch = document.createElement('tr'); ch.className = 'iv-child'; RT.celdas(ch, x, (c) => { c(''); c(NS.nom(x.canal), 'iv-city').colSpan = 3; }); tb.append(ch); });
}); };
dash.draw('rt-t', rtT);
dash.draw('rt-tot', (tf) => { tf.replaceChildren(); const s = RT.sel(); if (!s) return; const tr = document.createElement('tr'); RT.celdas(tr, RT.sum(s.R), (c) => { c(''); c('Total · ' + RT.filas().length + ' referencias').colSpan = 3; }); tf.append(tr); });
