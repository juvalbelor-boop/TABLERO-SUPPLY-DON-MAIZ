"""Extrae los datos de la pestaña Almacén del tablero Don Maíz.
Uso: python -I extraer_almacen.py MP.xlsx CAVAS.xlsx CARPETA_SALIDA
Genera almacen_mp.json, almacen_cavas.json y almacen_estado.json. Toma los valores tal como los calcula el Excel."""
import sys, os, json, datetime as dt, openpyxl
mp_path, cv_path, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
avisos, errores = [], []
num = lambda v: float(v) if isinstance(v, (int, float)) else 0.0
# ---------- Materia prima ----------
wb = openpyxl.load_workbook(mp_path, data_only=True, read_only=True)
res = wb['Resumen por Almacen']
par = {r[1]: r[2] for r in wb['Parametros'].iter_rows(min_row=6, max_row=30, values_only=True) if r[1]}
TV = next(v for k, v in par.items() if str(k).startswith('Semaforo: tope VERDE')); TA = next(v for k, v in par.items() if str(k).startswith('Semaforo: tope AMARILLO'))
sem_xl = lambda f: 'SOBRECAPACIDAD' if f > 1 else 'ROJO' if f > TA else 'AMARILLO' if f > TV else 'VERDE'
TV_GER = 0.85  # pedido del gerente (25-nov-2026): verde hasta 85 % (el Excel trae 70 %); rojo sigue > 90 %
sem = lambda f: 'SOBRECAPACIDAD' if f > 1 else 'ROJO' if f > TA else 'AMARILLO' if f > TV_GER else 'VERDE'
xl, xl_total = [], None   # tabla OCUPACION CONSOLIDADA tal como viene en el Excel
for r in res.iter_rows(min_row=7, max_row=20, values_only=True):
    if not r[1]: continue
    if r[1] == 'TOTAL GENERAL':
        xl_total = dict(alm='TOTAL', refs=r[2], cap=r[3], inv=r[4], pct=r[5], disp=r[6], costo=r[7], estado=r[8]); break
    if isinstance(r[2], (int, float)):
        xl.append(dict(alm=r[1], refs=r[2], cap=r[3], inv=r[4], pct=r[5], disp=r[6], costo=r[7], estado=r[8]))
if not xl_total or not xl: errores.append('No encontré la tabla OCUPACION CONSOLIDADA en "Resumen por Almacen"')
base = [r for r in wb['Base de datos'].iter_rows(min_row=2, values_only=True) if r[0]]
# Mismas fórmulas del Excel: COUNTIF / SUMIFS sobre "Base de datos" (D capacidad, E existencia, H costo) y % = E/D.
def resumen(filas):
    out = []
    for a in xl:
        f = [r for r in filas if r[5] == a['alm']]
        cap_, inv_, cos_ = sum(num(r[3]) for r in f), sum(num(r[4]) for r in f), sum(num(r[7]) for r in f)
        pct_ = inv_ / cap_ if cap_ else 0
        out.append(dict(alm=a['alm'], refs=len(f), cap=cap_, inv=inv_, pct=pct_, disp=cap_ - inv_, costo=cos_, estado=sem(pct_)))
    cap_, inv_ = sum(o['cap'] for o in out), sum(o['inv'] for o in out); pct_ = inv_ / cap_ if cap_ else 0
    return out, dict(alm='TOTAL', refs=sum(o['refs'] for o in out), cap=cap_, inv=inv_, pct=pct_, disp=cap_ - inv_, costo=sum(o['costo'] for o in out), estado=sem(pct_))
# 1) con todas las filas debe dar exactamente lo del Excel (si no, no se publica)
chk, chk_t = resumen(base)
for a, b in zip(chk + [chk_t], xl + [xl_total]):
    for k in ('refs', 'cap', 'inv', 'costo'):
        if abs(a[k] - b[k]) > 0.5: errores.append(f"{b['alm']}: {k} recalculado {a[k]} y en el Excel {b[k]}")
    if sem_xl(a['pct']) != b['estado']: errores.append(f"{b['alm']}: semáforo recalculado {a['estado']} y en el Excel {b['estado']}")
# 2) quitar filas repetidas (mismo código): se deja la primera
from collections import Counter
dup = sorted(k for k, v in Counter(str(r[0]).strip() for r in base).items() if v > 1)
vistos, unicos = set(), []
for r in base:
    k = str(r[0]).strip()
    if k in vistos: continue
    vistos.add(k); unicos.append(r)
alm, total = resumen(unicos)
if dup: avisos.append(f'Se quitaron {len(base) - len(unicos)} filas repetidas de "Base de datos": ' + ', '.join(dup))
refs, vistos = [], set()
for r in wb['KPI Detalle'].iter_rows(min_row=7, values_only=True):
    if not r[1] or not r[3]: continue
    cod = str(r[1]).strip()
    if cod in vistos: continue
    vistos.add(cod)
    refs.append(dict(cod=cod, desc=str(r[2] or '').strip(), alm=r[3], um=str(r[4] or '').strip(), cap=num(r[5]), inv=num(r[6]),
                     pct=r[7] if isinstance(r[7], (int, float)) else None, disp=num(r[8]), costo=num(r[10]), salidas=num(r[11]),
                     dias=r[12] if isinstance(r[12], (int, float)) else None, estado=str(r[13] or '')))
    e_ = refs[-1]; e_['estado'] = e_['estado'] if e_['estado'] in ('SIN INVENTARIO', 'SOBRECAPACIDAD') else sem(e_['pct'] or 0)
faltan = sorted(set(str(r[0]).strip() for r in unicos) - vistos)
if faltan: errores.append('Referencias de "Base de datos" que no están en "KPI Detalle": ' + ', '.join(faltan))
sincap = sorted(r['cod'] for r in refs if not r['cap'])
if sincap: avisos.append(f'{len(sincap)} referencias sin capacidad máxima (0 o vacía): ' + ', '.join(sincap))
for a in alm:
    s_ = sum(r['inv'] for r in refs if r['alm'] == a['alm'])
    if abs(s_ - a['inv']) > 0.5: errores.append(f"{a['alm']}: el resumen sin repetidos suma {a['inv']:,.2f} y el detalle {s_:,.2f}")
# ---------- Cavas ----------
wc = openpyxl.load_workbook(cv_path, data_only=True, read_only=True)
k = wc['KPI Final']; kv = {r[1]: r[2:5] for r in k.iter_rows(min_row=7, max_row=16, values_only=True) if r[1]}
def fila(prefijo):
    for key, v in kv.items():
        if str(key).startswith(prefijo): return v
    errores.append('No encontré la fila "' + prefijo + '" en KPI Final'); return (None, None, None)
cavas = []
for i, (nombre, bod) in enumerate([('Refrigeración', 'DESE1'), ('Congelación', 'DEPT6')]):
    g = lambda p: fila(p)[i]
    cavas.append(dict(cava=nombre, bod=bod, cap=g('Capacidad máxima'), und=g('Inventario actual'), eq=g('Estibas equivalentes'), fis=g('Estibas ocupadas'),
                      disp=g('Estibas disponibles'), pct=g('% Ocupación'), kg=g('Peso total'), costo=g('Costo total'), estado=g('Semáforo')))
fecha = wc['Inventario Diario '].cell(6, 2).value
calc = wc['Calculo_KPI']; det = []
for rng, nombre in [((7, 54), 'Refrigeración'), ((59, 120), 'Congelación')]:
    for r in calc.iter_rows(min_row=rng[0], max_row=rng[1], values_only=True):
        if r[1] in (None, ''): continue
        det.append(dict(cava=nombre, ref=str(r[1]), desc=str(r[2] or '').strip(), und=num(r[3]), emb=r[4], und_estiba=num(r[7]), eq=num(r[9]), fis=num(r[10]), kg=num(r[12]), costo=num(r[14])))
for c in cavas:
    s = sum(d['eq'] for d in det if d['cava'] == c['cava'])
    if abs(s - (c['eq'] or 0)) > 1e-6: errores.append(f"{c['cava']}: estibas equivalentes del resumen {c['eq']} y del detalle {s}")
# histórico: estibas equivalentes por día y cava
emb = {}
for r in wc['Base de Datos Embalajes'].iter_rows(min_row=7, values_only=True):
    if r[1] not in (None, ''): emb[(str(r[1]), str(r[3]).lower()[:5])] = num(r[7])
und_calc = {(d['cava'], d['ref']): d['und_estiba'] for d in det}
h = list(wc['Histórico Diario'].iter_rows(min_row=6, values_only=True))
cols = [(j, v) for j, v in enumerate(h[0]) if isinstance(v, dt.datetime)]
hist = []
for j, d in cols:
    tot = {'Refrigeración': 0.0, 'Congelación': 0.0}; hay = False
    for r in h[1:]:
        if r[1] in (None, '') or not isinstance(r[j], (int, float)): continue
        hay = True; cv = 'Refrigeración' if str(r[3]).lower().startswith('refri') else 'Congelación'
        ue = und_calc.get((cv, str(r[1]))) or emb.get((str(r[1]), str(r[3]).lower()[:5]))
        if emb.get((str(r[1]), str(r[3]).lower()[:5])) and und_calc.get((cv, str(r[1]))) and und_calc[(cv, str(r[1]))] != emb[(str(r[1]), str(r[3]).lower()[:5])] and j == cols[-1][0]: avisos.append(f"{r[1]} ({cv}): Base de Datos Embalajes dice {emb[(str(r[1]), str(r[3]).lower()[:5])]:g} und/estiba y Calculo_KPI usa {und_calc[(cv, str(r[1]))]:g}")
        if ue: tot[cv] += r[j] / ue
    if hay: hist.append(dict(fecha=d.date().isoformat(), refrig=round(tot['Refrigeración'], 4), congel=round(tot['Congelación'], 4)))
if hist and fecha:
    u = hist[-1]
    if u['fecha'] == fecha.date().isoformat():
        for c, kk in [(cavas[0], 'refrig'), (cavas[1], 'congel')]:
            if abs(u[kk] - c['eq']) > 0.01: avisos.append(f"Histórico del {u['fecha']}: {c['cava']} da {u[kk]:.2f} estibas y el KPI {c['eq']:.2f}")
def plano(filas):  # filas planas con las mismas columnas (el tablero lee filas, no objetos anidados)
    cols = []
    for f in filas:
        for k in f:
            if k not in cols: cols.append(k)
    return [{k: f.get(k) for k in cols} for f in filas]
mp_rows = [dict(tipo='alm', **a) for a in alm] + [dict(tipo='total', **total)] + [dict(tipo='ref', **r) for r in refs] \
    + [dict(tipo='excel', **a) for a in xl + [xl_total]] + [dict(tipo='info', repetidos=','.join(dup))]
json.dump(plano(mp_rows), open(os.path.join(out, 'almacen_mp.json'), 'w'), ensure_ascii=False)
cv_rows = [dict(tipo='cava', **c) for c in cavas] + [dict(tipo='det', **d) for d in det] + [dict(tipo='hist', **h_) for h_ in hist] \
    + [dict(tipo='info', fecha=fecha.date().isoformat() if fecha else None)]
json.dump(plano(cv_rows), open(os.path.join(out, 'almacen_cavas.json'), 'w'), ensure_ascii=False)
json.dump([dict(mp_archivo=os.path.basename(mp_path), cavas_archivo=os.path.basename(cv_path), cavas_fecha=fecha.date().isoformat() if fecha else None, avisos=' | '.join(avisos), errores=' | '.join(errores))], open(os.path.join(out, 'almacen_estado.json'), 'w'), ensure_ascii=False)
print('ERRORES:' if errores else 'OK', *errores, sep='\n  ')
print('Avisos:', *avisos, sep='\n  ')
for a, b in zip(alm + [total], xl + [xl_total]): print(f"  Excel {b['pct']*100:6.1f} % ({b['refs']} refs) →", end=''); print(f"  {a['alm']:<18} {a['pct']*100:6.1f} %  inv {a['inv']:>14,.2f}  cap {a['cap']:>12,.0f}  ${a['costo']:,.0f}  {a['estado']}")
for c in cavas: print(f"  {c['cava']:<14} cap {c['cap']}  eq {c['eq']:.2f}  fis {c['fis']}  {c['pct']*100:.1f} %  {c['estado']}")
print('  histórico:', len(hist), 'días', hist[0]['fecha'], '→', hist[-1], ' detalle cavas:', len(det), ' refs MP:', len(refs))
