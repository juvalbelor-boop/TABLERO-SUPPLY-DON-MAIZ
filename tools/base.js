// Tablero Supply Chain Don Maíz · código base sacado de index.html el 27-nov-2026 (sin cambios) para liberar espacio en la página.
document.addEventListener('click', (e) => {
const btn = e.target.closest && e.target.closest('.dm-ms-btn'); if (!btn) return;
const box = btn.closest('.dm-ms'), list = box && box.querySelector('.dm-ms-list'), f = list && window.DMms && window.DMms[list.dataset.draw];
if (f) { try { f(list); } catch (err) { console.error(err); } }
}, true);
const DM_LIM_CRIT = 3;
dash.calc('puntos', {
inputs: ['inventario'],
title: 'Estado por bodega y referencia',
description: 'Cada fila del archivo con inventario + tránsito, días y estado: crítico (menos de 3 días, o sea 2,9 o menos), estable (3 a 13), sobrestock (más de 13) o sin demanda.',
fn: (inventario) => inventario.map((r) => {
const inv = r.ex + r.tr;
const dias = r.dem > 0 ? inv / r.dem : null;
const estado = r.dem > 0 ? (dias < DM_LIM_CRIT ? 'CRITICO' : dias <= 13 ? 'ESTABLE' : 'SOBRESTOCK') : (inv > 0 ? 'SIN DEMANDA' : null);
return { id: r.corte + '|' + r.bod + '-' + r.ref, corte: r.corte, cat: r.cat, bod: r.bod, ciudad: r.ciudad, ref: r.ref, desc: r.desc, seg: r.seg, fam: r.fam, abc: r.abc, ex: r.ex, tr: r.tr, inv, fcd: r.fcd, dem: r.dem, dias, estado };
}),
});
