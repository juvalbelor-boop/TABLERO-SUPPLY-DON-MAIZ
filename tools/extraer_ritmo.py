"""Tablero Supply Chain Don Maíz · Ritmo de venta (forecast del mes vs cantidad facturada).
Uso: python -I extraer_ritmo.py Forecast.xlsx "Nivel de servicio por canal.xlsx" Maestros.xlsx CARPETA_SALIDA
Genera ritmo.json: una fila por mes (AAAAMM), canal y referencia con fc (forecast del mes, paquetes) y real (Suma de Cant_Facturada
del archivo de nivel de servicio), más descripción y segmento (pestaña Segmentos de Maestros). Solo los meses que trae Forecast.xlsx.
Reglas (27-nov-2026, aprobadas por el usuario):
  - Canal del forecast: las cadenas (Éxito, Cencosud, Jerónimo Martins, Olímpica, Makro, PriceSmart, Colombiana de Comercio) van a MODERNO;
    Cheeky Foods y Wouters a EXPORTACION; Venta interna a OTROS. Un canal que no esté en la lista para el proceso (NO PUBLICAR).
  - Canal del nivel de servicio: TAT se suma a DISTRIBUIDORES; canal en blanco = SIN CANAL.
  - El archivo de nivel de servicio no trae ciudad: el detalle de cada referencia es por canal.
Valida: por mes, la suma del forecast = la columna del Excel y la suma de lo real = Cant_Facturada del archivo. Si no: NO PUBLICAR."""
import sys, os, json, datetime as dt, pandas as pd, openpyxl
fx, nx, mx, out = sys.argv[1:5]
M = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
CANAL_FC = {'ALMACENES EXITO S.A.': 'MODERNO', 'CENCOSUD COLOMBIA S.A.': 'MODERNO', 'JERONIMO MARTINS COLOMBIA S.A.S': 'MODERNO',
            'SUPERTIENDAS Y DROGUERIAS OLIMPICA S A': 'MODERNO', 'MAKRO SUPERMAYORISTA S.A.S.': 'MODERNO', 'PRICESMART COLOMBIA S.A.S': 'MODERNO',
            'COLOMBIANA DE COMERCIO S A': 'MODERNO', 'CHEEKY FOODS': 'EXPORTACION', 'WOUTERS': 'EXPORTACION', 'VENTA INTERNA': 'OTROS'}
BASE = {'ALTERNATIVOS', 'DISTRIBUIDORES', 'EXPORTACION', 'INSTITUCIONAL', 'MODERNO', 'OTROS', 'SUPERETES', 'SIN CANAL'}
def ref(x):
    s = str(x).strip()
    try: return str(int(float(s)))
    except Exception: return s
err = []
f = pd.read_excel(fx, 'Forecast', dtype={'Cod': str}); f.columns = [str(c).strip() for c in f.columns]
cols = [c for c in f.columns if len(c) == 7 and c[4] == '-' and c[:4].isdigit()]
if not cols: sys.exit('NO PUBLICAR: Forecast.xlsx no tiene columnas de mes AAAA-MM')
f['canal'] = f.CANAL.astype(str).str.strip().str.upper().map(lambda c: CANAL_FC.get(c, c))
nuevos = sorted(set(f.canal) - BASE)
if nuevos: err.append('Canales del forecast sin regla: ' + ', '.join(nuevos))
f['ref'] = f.Cod.map(ref)
n = pd.read_excel(nx, sheet_name=0, dtype=object); n.columns = [str(c).strip() for c in n.columns]
ca, cm, cc = n.columns[:3]
cf = next(c for c in n.columns if 'CANT_FACTURADA' in c.upper().replace(' ', ''))
cr = next((c for c in n.columns if c.upper().replace(' ', '') == 'CODREFERENCIA'), None)
cd = next((c for c in n.columns if c.upper().replace(' ', '') == 'DESCREFERENCIA'), None)
if not cr: sys.exit('NO PUBLICAR: el archivo de nivel de servicio no trae CodReferencia')
n[ca] = n[ca].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
n = n[~n[ca].str.upper().str.startswith('TOTAL') & n[cm].notna()].copy()
n['mes'] = [f'{a}{M.index(str(m).strip().upper()) + 1:02d}' if str(m).strip().upper() in M else None for a, m in zip(n[ca], n[cm])]
n['canal'] = n[cc].where(n[cc].notna() & (n[cc].astype(str).str.strip() != '') & (n[cc].astype(str).str.strip().str.upper() != '(EN BLANCO)'), 'SIN CANAL').astype(str).str.strip().str.upper().replace({'TAT': 'DISTRIBUIDORES'})
n['ref'] = n[cr].map(ref); n['real'] = pd.to_numeric(n[cf])
seg = pd.read_excel(mx, 'Segmentos', dtype=str); segm = dict(zip(seg.SKU.map(ref), seg.Segmento.str.strip()))
desc = {}
for r, d in zip(f.ref, f.DescReferencia): desc.setdefault(r, ' '.join(str(d).split()))
if cd:
    for r, d in zip(n.ref, n[cd]): desc.setdefault(r, ' '.join(str(d).split()))
rows, resumen = [], {}
for c in cols:
    mes = c.replace('-', '')
    a = f.groupby(['canal', 'ref'])[c].sum(); a = a[a.abs() > 1e-9]
    b = n[n.mes == mes].groupby(['canal', 'ref']).real.sum(); b = b[b != 0]
    if abs(a.sum() - f[c].sum()) > 0.5: err.append(f'{mes}: forecast {a.sum():,.0f} ≠ Excel {f[c].sum():,.0f}')
    tr = float(n.loc[n.mes == mes, 'real'].sum())
    if abs(b.sum() - tr) > 0.5: err.append(f'{mes}: real {b.sum():,.0f} ≠ archivo {tr:,.0f}')
    for k in sorted(set(a.index) | set(b.index)):
        rows.append(dict(mes=mes, canal=k[0], ref=k[1], desc=desc.get(k[1], ''), seg=segm.get(k[1], 'SIN CLASIFICAR'),
                         fc=round(float(a.get(k, 0)), 2), real=float(b.get(k, 0))))
    resumen[mes] = dict(fc=round(float(a.sum()), 2), real=tr)
mod = openpyxl.load_workbook(nx, read_only=True).properties.modified
guardado = (mod - dt.timedelta(hours=5)).strftime('%Y-%m-%d') if mod else None
os.makedirs(out, exist_ok=True)
json.dump(rows, open(os.path.join(out, 'ritmo.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(dict(ns_guardado=guardado, meses=resumen, filas=len(rows),
                      sin_segmento=sorted({r['ref'] for r in rows if r['seg'] == 'SIN CLASIFICAR'})), ensure_ascii=False, indent=1))
if err: print('\n'.join(err)); sys.exit('NO PUBLICAR: las cifras no cuadran')
