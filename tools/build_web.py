"""Versión web pública del Tablero Supply Chain Don Maíz (fuera de Claude).
Uso: python -I build_web.py PAGINA.html CARPETA_DATOS CARPETA_SALIDA
  PAGINA.html     el texto de files/index.html del tablero (la misma página que se ve en Claude)
  CARPETA_DATOS   los JSON de cada dataset, con el nombre del dataset: inventario.json, produccion.json, mps.json, mps_estado.json,
                  agotados.json, agotados_estado.json, venta_mensual.json, ns.json, ns_estado.json, gasto.json, gasto_estado.json,
                  d3.min.js (d3 v7) y las fuentes poppins-400.woff, poppins-500.woff, poppins-700.woff
Genera CARPETA_SALIDA/index.html + data/*.json + fonts/*.woff. La página usa d3 (copia local en lib/) y un pequeño motor 'dash'
que replica el del tablero (datos, cálculos, filtros y dibujos), así se ve igual que en Claude."""
import sys, os, re, json, shutil, datetime as dt
page_path, data_dir, out = sys.argv[1:4]
OPCIONALES = ['ventas']
DATASETS = ['inventario', 'produccion', 'mps', 'mps_estado', 'agotados', 'agotados_estado', 'venta_mensual', 'ns', 'ns_estado', 'gasto', 'gasto_estado', 'presupuesto', 'presupuesto_estado', 'ventas', 'ventas_estado']
PARAMS0 = {'bods': [], 'cat': 'Nacional', 'ciudades': [], 'corte': None, 'segs': []}
page = open(page_path, encoding='utf-8').read()
page = page.replace('<meta name="dash-one-writer">', '')
# fuentes: de /_blob/<id> (dentro de Claude) a archivos locales
fonts = {'400': 'fonts/poppins-400.woff', '500': 'fonts/poppins-500.woff', '600 800': 'fonts/poppins-700.woff'}
def font_sub(m):
    w = m.group(1); return m.group(0).replace(m.group(2), fonts.get(w, fonts['400']))
page = re.sub(r"font-weight: ([0-9 ]+); font-display: swap; src: url\((/_blob/[0-9a-f]+)\)", font_sub, page)
if '/_blob/' in page: sys.exit('La página aún referencia /_blob/: revisar')
missing = [d for d in DATASETS if not os.path.exists(os.path.join(data_dir, d + '.json'))]
if missing: sys.exit('Faltan datos: ' + ', '.join(missing))
os.makedirs(os.path.join(out, 'data'), exist_ok=True); os.makedirs(os.path.join(out, 'fonts'), exist_ok=True)
for d in DATASETS: shutil.copy(os.path.join(data_dir, d + '.json'), os.path.join(out, 'data', d + '.json'))
os.makedirs(os.path.join(out, 'lib'), exist_ok=True)
# d3 y las fuentes: se copian si vienen en la carpeta de datos; si no, se dejan las que ya están en el sitio.
for src, dst in [('d3.min.js', 'lib/d3.min.js')] + [(f'poppins-{w}.woff', f'fonts/poppins-{w}.woff') for w in ('400', '500', '700')]:
    if os.path.exists(os.path.join(data_dir, src)): shutil.copy(os.path.join(data_dir, src), os.path.join(out, dst))
    elif not os.path.exists(os.path.join(out, dst)): sys.exit('Falta ' + dst)
stamp = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).strftime('%d/%m/%Y %I:%M %p')

TOKENS = """
:root { color-scheme: light;
  --color-fg: #1F1F1F; --color-fg-muted: #6B6B6B; --color-bg: #F6F6F4; --color-panel: #FFFFFF; --color-border-line: #E3E3DE;
  --color-ok: #149A3A; --color-warn: #F7941D; --color-bad: #D93B3B; --dm-bg-soft: #F1F7F2;
  --cds-border: #E3E3DE; --cds-chart-axis: #BDBDB6; --cds-chart-grid: #EDEDE8; --cds-chart-muted: #BDBDBD; --cds-chart-reference: #8A8A85;
  --cds-chart-status-critical: #D93B3B; --cds-dur-slow: 300ms; --cds-text-secondary: #6B6B6B;
  --cds-font-size-caption: 12px; --cds-font-size-body: 14px; --cds-font-size-heading: 16px; --cds-font-size-title: 26px; --cds-font-weight-medium: 500;
  --cds-gap-xs: 4px; --cds-gap-sm: 8px; --cds-gap-md: 12px; --cds-gap-lg: 16px; --cds-gap-xl: 24px;
  --cds-pad-xs: 4px; --cds-pad-sm: 8px; --cds-pad-md: 12px; --cds-pad-lg: 16px; --cds-pad-xl: 24px;
  --cds-radius: 10px; --cds-shadow-popover: 0 6px 24px rgba(0,0,0,.14); --cds-surface-popover: #FFFFFF;
  --font-anthropic-sans: 'Poppins', system-ui, -apple-system, 'Segoe UI', Arial, sans-serif; }
[hidden] { display: none !important; }
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 14px; }
#dash-root { max-width: 1500px; margin: 0 auto; padding: 16px; box-sizing: border-box; }
.web-foot { max-width: 1500px; margin: 0 auto; padding: 4px 16px 24px; color: var(--color-fg-muted); font-size: 12px; }
@media (max-width: 600px) { #dash-root { padding: 8px; } }
"""

SHIM = r"""
// Motor mínimo que replica el del tablero en Claude: datos (data/*.json), cálculos, filtros y dibujos marcados con data-draw.
window.dash = (() => {
  const DS = %DATASETS%, data = {}, calcs = {}, draws = {}, onDatas = [], cache = {};
  let params = %PARAMS%, loaded = false, queued = false;
  const ok = (rows) => ({ status: 'ok', data: rows, columns: rows && rows[0] ? Object.keys(rows[0]) : [], meta: [], refreshing: false });
  const api = {
    colors: ['#149A3A', '#F7941D', '#2F6FB0', '#F15A29', '#7B2A78', '#0B6B2B', '#C9A100', '#5E8C9A'],
    data(id) {
      if (calcs[id]) {
        if (!loaded) return { status: 'loading', data: [] };
        if (!(id in cache)) { const c = calcs[id]; try { cache[id] = ok(c.fn(...c.inputs.map((i) => api.data(i).data))); } catch (e) { console.error(e); cache[id] = { status: 'error', data: [], message: String(e) }; } }
        return cache[id];
      }
      if (!loaded) return { status: 'loading', data: [] };
      return data[id] ? ok(data[id]) : { status: 'missing', data: [] };
    },
    calc(id, o) { calcs[id] = o; },
    loader() {},
    draw(name, fn) { if (fn === undefined) { schedule(); return; } draws[name] = fn; },
    onData(fn) { onDatas.push(fn); },
    params() { return params; },
    setParams(p) { const n = { ...params }; Object.entries(p).forEach(([k, v]) => { if (v === null) delete n[k]; else n[k] = v; }); params = n; schedule(); },
    resetParams() { params = %PARAMS%; schedule(); },
    setLink(name) { try { history.replaceState(null, '', '#' + name); } catch (e) {} schedule(); },
    refresh() {},
  };
  const visible = (el) => !el.closest('[hidden]');
  function render() {
    queued = false;
    onDatas.forEach((f) => { try { f(); } catch (e) { console.error(e); } });
    Object.entries(draws).forEach(([name, fn]) => {
      document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => {
        if (!visible(el)) return;
        try { if (typeof fn === 'function') fn(el); else if (fn && fn.update) { if (!el.__m) el.__m = fn.mount ? fn.mount(el) : null; fn.update(el, el.__m); } } catch (e) { console.error(name, e); }
      });
    });
  }
  function schedule() { if (!queued) { queued = true; requestAnimationFrame(render); } }
  window.addEventListener('resize', schedule);
  window.addEventListener('DOMContentLoaded', () => {
    Promise.all(DS.map((d) => fetch('data/' + d + '.json', { cache: 'no-cache' }).then((r) => r.json()).then((j) => { data[d] = Array.isArray(j) ? j : (j && (j.rows || j.data || j.results)) || [j]; }).catch(() => {})))
      .then(() => { loaded = true; schedule(); });
    schedule();
  });
  return api;
})();
"""
SHIM = SHIM.replace('%DATASETS%', json.dumps(DATASETS)).replace('%PARAMS%', json.dumps(PARAMS0))
html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Tablero Supply Chain Don Maíz</title>
<style>{TOKENS}</style>
<script src="lib/d3.min.js"></script>
<script>{SHIM}</script>
</head>
<body>
<div id="dash-root">
{page}
</div>
<p class="web-foot">Versión web del tablero. Datos actualizados: {stamp}.</p>
</body>
</html>
"""
open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(html)
open(os.path.join(out, '.nojekyll'), 'w').write('')
print('ok', os.path.join(out, 'index.html'), len(html.encode()), 'bytes')
