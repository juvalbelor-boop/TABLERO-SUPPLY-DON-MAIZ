"""Tablero Supply Chain Don Maíz · Ritmo de venta (forecast del mes vs cantidad facturada), por canal, cliente, bodega y referencia.
Uso: python -I extraer_ritmo.py Forecast.xlsx "Nivel de servicio por canal.xlsx" Maestros.xlsx CARPETA_SALIDA
        [--cuota "Cuota Ventas por día MES.xlsx"] [--pesos pesos.json] [--reparto reparto_AAAAMM.json ...]
Genera ritmo.json con filas planas:
  tipo 'v': mes (AAAAMM), canal, cli, bod, ref, desc, seg, fc (forecast, paquetes), real (Suma de Cant_Facturada), kg (real × peso).
  tipo 'c': mes, canal, fecha (AAAA-MM-DD), cv (cuota del canal ese día, hoja FORMATO TI del archivo de cuota, columnas B:F).
Reglas (27-nov-2026, aprobadas por el usuario):
  - cli = cliente (razón social) en MODERNO; en los demás canales cli = canal (igual que el comparativo del gerente).
  - Forecast: las cadenas (Éxito, Cencosud, Jerónimo Martins, Olímpica, Makro, PriceSmart, Colombiana de Comercio) son canal MODERNO;
    Cheeky Foods y Wouters EXPORTACION; Venta interna OTROS. Un canal que no esté en la lista para el proceso (NO PUBLICAR).
  - Si un mes del forecast trae MODERNO sin cliente (noviembre 2026), se reparte por cliente con --reparto (sacado del comparativo
    del gerente, hoja BASE); el reparto debe sumar exacto el forecast de MODERNO por bodega y referencia.
  - Real por bodega de la hoja 'Hoja2' del archivo de nivel de servicio (con columna Bodega); si no existe, de la primera hoja sin bodega.
    TAT = DISTRIBUIDORES. El total del mes debe ser igual a la primera hoja (la que usa la pestaña Nivel de servicio).
  - Kilos = real × peso por referencia (pesos.json, de la hoja PESO del comparativo). Referencias sin peso: kg 0 y se listan.
Valida por mes: forecast = columna del Excel, real = Cant_Facturada del archivo, cuota del canal = total del archivo. Si no: NO PUBLICAR."""
import sys, os, json, argparse, datetime as dt, pandas as pd, openpyxl
ap = argparse.ArgumentParser(); ap.add_argument('fx'); ap.add_argument('nx'); ap.add_argument('mx'); ap.add_argument('out')
ap.add_argument('--cuota'); ap.add_argument('--pesos'); ap.add_argument('--reparto', nargs='*', default=[])
A = ap.parse_args()
M = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
CANAL_FC = {'ALMACENES EXITO S.A.': 'MODERNO', 'CENCOSUD COLOMBIA S.A.': 'MODERNO', 'JERONIMO MARTINS COLOMBIA S.A.S': 'MODERNO',
            'SUPERTIENDAS Y DROGUERIAS OLIMPICA S A': 'MODERNO', 'MAKRO SUPERMAYORISTA S.A.S.': 'MODERNO', 'PRICESMART COLOMBIA S.A.S': 'MODERNO',
            'COLOMBIANA DE COMERCIO S A': 'MODERNO', 'CHEEKY FOODS': 'EXPORTACION', 'WOUTERS': 'EXPORTACION', 'VENTA INTERNA': 'OTROS'}
BASE = {'ALTERNATIVOS', 'DISTRIBUIDORES', 'EXPORTACION', 'INSTITUCIONAL', 'MODERNO', 'OTROS', 'SUPERETES', 'SIN CANAL'}
def ref(x):
    s = str(x).strip()
    try: return str(int(float(s)))
    except Exception: return s
err, avisos = [], []
# ---------- Forecast
f = pd.read_excel(A.fx, 'Forecast', dtype={'Cod': str}); f.columns = [str(c).strip() for c in f.columns]
cols = [c for c in f.columns if len(c) == 7 and c[4] == '-' and c[:4].isdigit()]
if not cols: sys.exit('NO PUBLICAR: Forecast.xlsx no tiene columnas de mes AAAA-MM')
f['c0'] = f.CANAL.astype(str).str.strip().str.upper()
f['canal'] = f.c0.map(lambda c: CANAL_FC.get(c, c))
nuevos = sorted(set(f.canal) - BASE)
if nuevos: err.append('Canales del forecast sin regla: ' + ', '.join(nuevos))
f['cli'] = [c0 if cn == 'MODERNO' and c0 != 'MODERNO' else cn for c0, cn in zip(f.c0, f.canal)]
f['ref'] = f.Cod.map(ref); f['bod'] = [str(b).strip() if pd.notna(b) and str(b).strip() else ' '.join(str(d).split()).upper() for b, d in zip(f.Bodega, f.DescripcionBodega)]
rep = {}
for p in A.reparto:
    for r in json.load(open(p)): rep.setdefault(r['mes'], []).append(r)
# ---------- Real (nivel de servicio)
hojas = pd.ExcelFile(A.nx).sheet_names
def lee(h):
    n = pd.read_excel(A.nx, sheet_name=h, dtype=object); n.columns = [str(c).strip() for c in n.columns]; return n
n0 = lee(hojas[0])
nb = lee('Hoja2') if 'Hoja2' in hojas else None
if nb is not None and 'Bodega' not in nb.columns: nb = None
if nb is None: avisos.append('El archivo de nivel de servicio no trae la hoja con Bodega (Hoja2): el real queda sin bodega')
def prep(n):
    ca, cm = n.columns[:2]
    cc = next(c for c in n.columns if c.upper() == 'CANAL')
    cf = next(c for c in n.columns if 'CANT_FACTURADA' in c.upper().replace(' ', ''))
    cr = next(c for c in n.columns if c.upper().replace(' ', '') == 'CODREFERENCIA')
    cs = next((c for c in n.columns if 'RASONSOCIAL' in c.upper().replace(' ', '') or 'RAZONSOCIAL' in c.upper().replace(' ', '')), None)
    cd = next((c for c in n.columns if c.upper().replace(' ', '') == 'DESCREFERENCIA'), None)
    n[ca] = n[ca].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    n = n[~n[ca].str.upper().str.startswith('TOTAL') & n[cm].notna()].copy()
    n['mes'] = [f'{a}{M.index(str(m).strip().upper()) + 1:02d}' if str(m).strip().upper() in M else None for a, m in zip(n[ca], n[cm])]
    n['canal'] = n[cc].where(n[cc].notna() & (n[cc].astype(str).str.strip() != '') & (n[cc].astype(str).str.strip().str.upper() != '(EN BLANCO)'), 'SIN CANAL').astype(str).str.strip().str.upper().replace({'TAT': 'DISTRIBUIDORES'})
    n['cli'] = [str(s).strip() if cn == 'MODERNO' and cs and pd.notna(s) else cn for cn, s in zip(n.canal, n[cs] if cs else n.canal)]
    n['ref'] = n[cr].map(ref); n['real'] = pd.to_numeric(n[cf]).fillna(0)
    n['bod'] = [str(b).strip() if pd.notna(b) and str(b).strip() else 'SIN BODEGA' for b in n['Bodega']] if 'Bodega' in n.columns else 'SIN BODEGA'
    n['desc'] = n[cd].map(lambda d: ' '.join(str(d).split())) if cd else ''
    return n
n0 = prep(n0); n = prep(nb) if nb is not None else n0
# ---------- Maestros, pesos, cuota
seg = pd.read_excel(A.mx, 'Segmentos', dtype=str); segm = dict(zip(seg.SKU.map(ref), seg.Segmento.str.strip()))
bm = pd.read_excel(A.mx, 'Bodegas', dtype=str); bnom = dict(zip(bm.Bodega.str.strip(), bm.Nombre.str.strip()))  # bodega: nombre del maestro (PT Bogotá…)
peso = {str(k): float(v) for k, v in json.load(open(A.pesos)).items()} if A.pesos else {}
desc = {}
for r, d in zip(f.ref, f.DescReferencia): desc.setdefault(r, ' '.join(str(d).split()))
for r, d in zip(n.ref, n.desc): desc.setdefault(r, d)
cuota = []
if A.cuota:
    c = pd.read_excel(A.cuota, 'FORMATO TI', header=None, usecols='B:F', skiprows=3); c.columns = ['fecha', 'dia', 'canal', 'pdia', 'cv']
    c = c[c.fecha.notna() & c.canal.notna()].copy(); c['cv'] = pd.to_numeric(c.cv).fillna(0); c['fecha'] = pd.to_datetime(c.fecha)
    tot = openpyxl.load_workbook(A.cuota, read_only=True, data_only=True)['FORMATO TI']['F2'].value
    if tot is None or abs(c.cv.sum() - float(tot)) > 1: err.append(f'Cuota por canal {c.cv.sum():,.0f} ≠ total de FORMATO TI {tot}')
    for r in c.itertuples():
        cuota.append(dict(tipo='c', mes=r.fecha.strftime('%Y%m'), canal=str(r.canal).strip().upper(), fecha=r.fecha.strftime('%Y-%m-%d'), cv=round(float(r.cv), 2)))
# ---------- Armar filas
rows, resumen, sin_peso = [], {}, {}
for col in cols:
    mes = col.replace('-', '')
    fm = f[f[col] != 0][['canal', 'cli', 'bod', 'ref', col]].rename(columns={col: 'fc'})
    if mes in rep:   # MODERNO sin cliente: se reemplaza por el reparto del gerente, que debe sumar igual por bodega y referencia
        rp = pd.DataFrame(rep[mes]); rp['bod'] = [str(b).strip() for b in rp.bod]; rp['ref'] = rp.ref.map(ref)
        a = fm[fm.cli == 'MODERNO'].groupby(['bod', 'ref']).fc.sum(); b = rp.groupby(['bod', 'ref']).fc.sum()
        dd = pd.concat([a, b], axis=1).fillna(0); dd = dd[(dd.iloc[:, 0] - dd.iloc[:, 1]).abs() > 0.01]
        if len(dd): err.append(f'{mes}: el reparto por cliente no suma igual al forecast de MODERNO en {len(dd)} bodega-referencias')
        fm = pd.concat([fm[fm.cli != 'MODERNO'], rp.assign(canal='MODERNO')[['canal', 'cli', 'bod', 'ref', 'fc']]])
    elif (fm.cli == 'MODERNO').any(): avisos.append(f'{mes}: el forecast de MODERNO no viene por cliente (queda como MODERNO)')
    K = ['canal', 'cli', 'bod', 'ref']
    a = fm.groupby(K).fc.sum(); a = a[a.abs() > 1e-9]
    b = n[n.mes == mes].groupby(K).real.sum(); b = b[b != 0]
    if abs(a.sum() - f[col].sum()) > 0.5: err.append(f'{mes}: forecast {a.sum():,.0f} ≠ Excel {f[col].sum():,.0f}')
    t0 = float(n0.loc[n0.mes == mes, 'real'].sum())
    if abs(b.sum() - t0) > 0.5: err.append(f'{mes}: real con bodega {b.sum():,.0f} ≠ hoja de nivel de servicio {t0:,.0f}')
    for k in sorted(set(a.index) | set(b.index)):
        re_ = float(b.get(k, 0)); pz = peso.get(k[3])
        if re_ and pz is None: sin_peso[k[3]] = sin_peso.get(k[3], 0) + re_
        rows.append(dict(tipo='v', mes=mes, canal=k[0], cli=k[1], bod=bnom.get(k[2], k[2].title()), ref=k[3], desc=desc.get(k[3], ''), seg=segm.get(k[3], 'SIN CLASIFICAR'),
                         fc=round(float(a.get(k, 0)), 2), real=re_, kg=round(re_ * (pz or 0), 2)))
    resumen[mes] = dict(fc=round(float(a.sum()), 2), real=float(b.sum()))
mod = openpyxl.load_workbook(A.nx, read_only=True).properties.modified
os.makedirs(A.out, exist_ok=True)
json.dump(rows + cuota, open(os.path.join(A.out, 'ritmo.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(dict(ns_guardado=(mod - dt.timedelta(hours=5)).strftime('%Y-%m-%d') if mod else None, meses=resumen, filas=len(rows), filas_cuota=len(cuota),
                      sin_segmento=sorted({r['ref'] for r in rows if r['seg'] == 'SIN CLASIFICAR'}), real_sin_peso=sin_peso, avisos=avisos), ensure_ascii=False, indent=1))
if err: print('\n'.join(err)); sys.exit('NO PUBLICAR: las cifras no cuadran')
