"""Tablero Supply Chain Don Maíz · módulo MPS y OTIF.
Lee el Excel OTIF_Don_Maiz (sin modificarlo), replica sus fórmulas y genera:
  produccion.json  una fila por SKU-día programado (tipo 'plan') o producido sin programar (tipo 'np')
  mps.json         una fila por semana y SKU con el MPS final
  estado.json      'hoy' del archivo (fecha en que se guardó), fechas cargadas y resultado de las validaciones
Uso: python -I extraer_mps_otif.py OTIF.xlsx CARPETA_SALIDA
Reglas (las del Excel aprobado): clave fecha+SKU; solo cuentan días anteriores al 'hoy' del archivo; se excluyen referencias PP*;
In Full = min(real/programado, 1); On Time por la tabla Rangos; OTIF = In Full × On Time; faltante = max(programado - real, 0);
la semana va de domingo a sábado y se nombra por su lunes. Si alguna validación contra los resúmenes del Excel falla, sale con error."""
import sys, os, json, pandas as pd, numpy as np, openpyxl
xl, out = sys.argv[1], sys.argv[2]
def ref(x):
    s = str(x).strip()
    try: return str(int(float(s)))
    except Exception: return s
def semana(d): return d - pd.to_timedelta(d.dt.weekday, 'D')  # semana de lunes a domingo (desde el 24-nov-2026, igual que la programación)
def horno(x):
    s = str(x).strip().upper().replace(' ', '')
    if s.startswith('HORNO'): s = 'H' + s[5:]
    if s.startswith('H') and s[1:].isdigit(): return 'Horno ' + s[1:]
    if 'CHOC' in s: return 'Laminadora choclo'
    if 'SALSA' in s or s == 'AJI': return 'Línea salsas'
    return str(x).strip().title() if str(x).strip() and str(x) != 'nan' else 'Sin horno'
DIAS_ES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
def fechas(x):
    """Fechas del Excel: algunas filas llegan como número de serie (p. ej. 46335 = 9-nov-2026) en vez de fecha."""
    def una(v):
        if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
            return pd.NaT if pd.isna(v) or not 20000 < v < 80000 else pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(v))
        return pd.to_datetime(v, errors='coerce')
    return pd.Series([una(v) for v in list(x)], index=x.index if isinstance(x, pd.Series) else None, dtype='datetime64[ns]')
# --- valores guardados del Excel (para inferir 'hoy' y validar)
wb = openpyxl.load_workbook(xl, data_only=True, read_only=True)
def hoja(nombre):
    ws = wb[nombre]; rows = list(ws.iter_rows(values_only=True)); return pd.DataFrame(rows[1:], columns=rows[0])
dias_c = hoja('DIAS'); siesa_c = hoja('SIESA')
cont = dias_c[dias_c['Cuenta'] == 'SI']; nocont = dias_c[(dias_c['Primera'] == 'SI') & (dias_c['Cuenta'] == 'NO')]
s_nocont = siesa_c[(siesa_c['Cuenta'] == 'NO') & ~siesa_c['Ref'].astype(str).str.startswith('PP')]
cands = list(fechas(nocont['Fecha']).dropna()) + list(pd.to_datetime(s_nocont['Fecha inicio']).dropna())
# 'hoy' del Excel: la fecha (hora de Colombia) en que se guardó el archivo; debe ser coherente con los días que el Excel ya cuenta.
lo = (max(fechas(cont['Fecha'])) + pd.Timedelta(days=1)).normalize()          # hoy > último día contado
hi = min(cands).normalize() if cands else None                                          # hoy <= primer día no contado
_mod = openpyxl.load_workbook(xl, read_only=True).properties.modified
guardado = (pd.Timestamp(_mod) - pd.Timedelta(hours=5)).normalize() if _mod else None
HOY = guardado if guardado is not None and guardado >= lo and (hi is None or guardado <= hi) else (hi if hi is not None else lo)
# --- réplica desde los datos de entrada
seg = pd.read_excel(xl, 'Segmentos'); seg_map = dict(zip(seg.iloc[:, 0].map(ref), seg.iloc[:, 1]))
cat = pd.read_excel(xl, 'Categorias'); cat_map = dict(zip(cat.Segmento, cat.Categoria))
rg = pd.read_excel(xl, 'Rangos'); assert list(rg.iloc[:6, 1]) == [1, .9, .8, .7, .6, 0], 'La tabla Rangos cambió: revisar la regla de On Time'
segm = lambda r: seg_map.get(r, 'SIN SEGMENTO'); catm = lambda s: cat_map.get(s, 'OTROS')
si = pd.read_excel(xl, 'SIESA', usecols='A:H,M,N'); si = si[si['O.P. Número'].notna()].copy()
si.columns = [c.strip() for c in si.columns]
# Kilos por paquete (regla de GENERAL!O): suma de 'Cant. ejecutar en KG' ÷ suma de 'Cant. Programada' de todas las órdenes del SKU con kilos
_s = si.assign(Ref=si['Item O.P. Referencia'].map(ref)); _s = _s[_s['Cant. ejecutar en KG'].notna()]
_g = _s.groupby('Ref').agg(kg=('Cant. ejecutar en KG', 'sum'), cp=('Cant. Programada', 'sum'))
en_general = set(pd.read_excel(xl, 'GENERAL', usecols='A').iloc[:, 0].dropna().map(ref))
PESO = {r: (row.kg / row.cp) for r, row in _g.iterrows() if row.cp and r in en_general}
si['Ref'] = si['Item O.P. Referencia'].map(ref); si['Fecha'] = pd.to_datetime(si['Fecha inicio']).dt.normalize()
si = si[~si.Ref.str.startswith('PP') & (si.Fecha < HOY)].copy(); si['Semana'] = semana(si.Fecha)
di = pd.read_excel(xl, 'DIAS', usecols='A:E'); di.columns = ['Fecha', 'LINEA', 'SKU', 'DESC', 'PROG']
di['Ref'] = di.SKU.map(lambda x: ref(x) if pd.notna(x) else '')
di['Fecha'] = fechas(di.Fecha).values
ok = (di.Ref != '') & (di.Ref != 'SKU') & pd.to_numeric(di.PROG, errors='coerce').notna() & di.Fecha.notna()
di = di[ok].copy(); di['PROG'] = di.PROG.astype(float); di['Fecha'] = pd.to_datetime(di.Fecha).dt.normalize()
di = di[(di.PROG > 0) & ~di.DESC.astype(str).str.upper().str.contains('TOTAL')]
claves = set(zip(di.Fecha, di.Ref))
plan = di.groupby(['Fecha', 'Ref'], as_index=False, sort=False).agg(PROG=('PROG', 'sum'), LINEA=('LINEA', 'first'), DESC=('DESC', 'first'))
plan = plan[plan.Fecha < HOY].copy()
real = si.groupby(['Fecha', 'Ref'], as_index=False).agg(REAL=('Cant. Completa', 'sum'), REALK=('Cant. completa en KG', 'sum'))
plan = plan.merge(real, on=['Fecha', 'Ref'], how='left').fillna({'REAL': 0, 'REALK': 0})
plan['PROGK'] = [p * PESO.get(r, 0) for p, r in zip(plan.PROG, plan.Ref)]
plan['INF'] = np.minimum(plan.REAL / plan.PROG, 1); v = -(plan.REAL / plan.PROG - 1)
plan['ONT'] = np.select([v <= 0, v <= .05, v <= .10, v <= .15, v <= .20], [1, .9, .8, .7, .6], 0)
plan['OTIF'] = plan.INF * plan.ONT; plan['FALT'] = np.maximum(plan.PROG - plan.REAL, 0)
np_ = si[[(f, r) not in claves for f, r in zip(si.Fecha, si.Ref)]]
mp = pd.read_excel(xl, 'MPS_Semanas', usecols='A,B,I,O'); mp.columns = ['COD', 'DESC', 'MPS', 'Semana']
mp = mp[mp.COD.notna()].copy(); mp['Ref'] = mp.COD.map(ref); mp['Semana'] = pd.to_datetime(mp.Semana).dt.normalize(); mp['MPS'] = mp.MPS.fillna(0).astype(float)
desc = {}
for r, d in list(zip(si.Ref, si['Item O.P. Resumen'])) + list(zip(plan.Ref, plan.DESC)) + list(zip(mp.Ref, mp.DESC)):
    if r not in desc and isinstance(d, str): desc[r] = ' '.join(d.split()).removeprefix(r + ' ').strip()
d8 = lambda x: x.strftime('%Y-%m-%d')
prod = []
for x in plan.itertuples():
    sg = segm(x.Ref)
    prod.append(dict(tipo='plan', f=d8(x.Fecha), s=d8(x.Fecha - pd.Timedelta(days=x.Fecha.weekday())),
                     dia=DIAS_ES[x.Fecha.weekday()], ref=x.Ref, desc=desc.get(x.Ref, ''), seg=sg, cat=catm(sg), horno=horno(x.LINEA),
                     prog=float(x.PROG), real=float(x.REAL), falt=float(x.FALT), inf=float(x.INF), ont=float(x.ONT), otif=float(x.OTIF),
                     progk=float(x.PROGK), realk=float(x.REALK), faltk=float(max(x.PROGK - x.REALK, 0))))
for x in np_.itertuples():
    sg = segm(x.Ref)
    prod.append(dict(tipo='np', f=d8(x.Fecha), s=d8(x.Semana), dia=DIAS_ES[x.Fecha.weekday()], ref=x.Ref, desc=desc.get(x.Ref, ''), seg=sg, cat=catm(sg),
                     horno=horno(x._6), prog=0.0, real=float(x._8), falt=0.0, inf=None, ont=None, otif=None,
                     progk=0.0, realk=float(x._10), faltk=0.0))
mps = [dict(s=d8(x.Semana), ref=x.Ref, desc=desc.get(x.Ref, ''), seg=segm(x.Ref), cat=catm(segm(x.Ref)), mps=float(x.MPS), mpsk=float(x.MPS) * PESO.get(x.Ref, 0)) for x in mp.itertuples() if pd.notna(x.Semana)]
# --- validaciones contra los resúmenes guardados del Excel
P = pd.DataFrame(prod); M = pd.DataFrame(mps); errores = []
def vacio(x): return x is None or x == '' or (isinstance(x, float) and np.isnan(x))
def igual(a, b):
    if vacio(a) and (vacio(b) or b == 0): return True
    if vacio(a) or vacio(b): return vacio(b) and a == 0
    return abs(float(a) - float(b)) <= 1e-6 * max(1, abs(float(a)))
rs = hoja('Resumen_Semana'); rs = rs[rs['Semana'].notna()]
for r in rs.itertuples(index=False):
    w = d8(fechas([r[0]])[0]); pw = P[P.s == w]; pl = pw[pw.tipo == 'plan']; pr = pl.prog.sum()
    chk = {'MPS': (r[4], M[M.s == w].mps.sum()), 'PROGRAMADO': (r[5], pr), 'REAL': (r[6], pw.real.sum()), 'Real no programado': (r[7], pw[pw.tipo == 'np'].real.sum()),
           'OTIF ponderado': (r[17], (pl.otif * pl.prog).sum() / pr if pr else None),
           'MPS kg': (r[20], M[M.s == w].mpsk.sum()), 'Programado kg': (r[21], pl.progk.sum()), 'Real kg': (r[22], pw.realk.sum())}
    for k, (a, b) in chk.items():
        if not igual(a, b): errores.append(f'Semana {w} {k}: Excel {a} vs tablero {b}')
    est_t = 'Cerrada' if HOY > fechas([r[0]])[0] + pd.Timedelta(days=6) else 'Abierta'
    if r[3] in ('Abierta', 'Cerrada') and r[3] != est_t: errores.append(f'Semana {w} estado: Excel {r[3]} vs tablero {est_t}')
rd = hoja('Resumen_Dia'); rd = rd[rd['Fecha'].notna()]
for r in rd.itertuples(index=False):
    f = d8(fechas([r[0]])[0]); pf = P[P.f == f]; pl = pf[pf.tipo == 'plan']
    for k, a, b in [('PROGRAMADO', r[3], pl.prog.sum()), ('REAL', r[4], pf.real.sum()), ('Programado kg', r[16], pl.progk.sum()), ('Real kg', r[17], pf.realk.sum())]:
        if not igual(a or 0, b): errores.append(f'Día {f} {k}: Excel {a} vs tablero {b}')
ctrl = hoja('Control'); malos = ctrl[ctrl['Estado'] == 'REVISAR']['Validación'].tolist()
estado = dict(archivo=os.path.basename(xl), hoy=d8(HOY), guardado=d8(guardado) if guardado is not None else None, siesa_hasta=d8(pd.to_datetime(siesa_c['Fecha inicio']).max()), plan_hasta=d8(fechas(dias_c['Fecha']).max()),
              control_excel='Todo OK' if not malos else 'REVISAR: ' + '; '.join(malos), validacion='OK' if not errores else 'FALLÓ',
              semanas=sorted(P.s.unique().tolist()), filas_produccion=len(prod), filas_mps=len(mps))
# --- Excepción aprobada por Juan Camilo (10-nov-2026), solo para el domingo 8-nov-2026: no hubo programa en DIAS, así que el
# programado de ese día es la Cant. Programada de sus órdenes en Siesa (las 11 órdenes) y el real su Cant. Completa. Con eso se
# calculan In Full, On Time y OTIF con las mismas reglas, por SKU y día. Ese domingo cuenta en la semana ANTERIOR (la del lunes 2-nov),
# como último día de esa semana, por decisión del usuario. Se aplica DESPUÉS de validar contra el Excel.
EXC_DIAS = ['2026-11-08']
for f in EXC_DIAS:
    if any(p['tipo'] == 'plan' and p['f'] == f for p in prod): continue
    o = si[si.Fecha == pd.Timestamp(f)]
    if o.empty: continue
    prod = [p for p in prod if not (p['tipo'] == 'np' and p['f'] == f)]
    g = o.groupby('Ref', sort=False).agg(PROG=('Cant. Programada', 'sum'), REAL=('Cant. Completa', 'sum'), REALK=('Cant. completa en KG', 'sum'), LINEA=('Desc. C. Trabajo', 'first'))
    for r, x in g.iterrows():
        if not x.PROG: continue
        inf = min(x.REAL / x.PROG, 1); v = -(x.REAL / x.PROG - 1)
        ont = 1 if v <= 0 else .9 if v <= .05 else .8 if v <= .10 else .7 if v <= .15 else .6 if v <= .20 else 0
        fe = pd.Timestamp(f); sg = segm(r); progk = float(x.PROG) * PESO.get(r, 0)
        prod.append(dict(tipo='plan', f=f, s=d8(fe - pd.Timedelta(days=fe.weekday())), dia=DIAS_ES[fe.weekday()],
                         ref=r, desc=desc.get(r, ''), seg=sg, cat=catm(sg), horno=horno(x.LINEA), prog=float(x.PROG), real=float(x.REAL), falt=float(max(x.PROG - x.REAL, 0)),
                         inf=float(inf), ont=float(ont), otif=float(inf * ont), progk=progk, realk=float(x.REALK), faltk=float(max(progk - x.REALK, 0)),
                         excepcion='Domingo sin programa en DIAS: programado = Cant. Programada de las órdenes de Siesa'))
    estado['excepciones'] = estado.get('excepciones', []) + [dict(fecha=f, semana=d8(pd.Timestamp(f) - pd.Timedelta(days=pd.Timestamp(f).weekday())), regla='Sin programa en DIAS: programado = Cant. Programada de las órdenes de Siesa del día; cuenta en la semana anterior', ordenes=int(len(o)),
                                                                  programado=float(o['Cant. Programada'].sum()), real=float(o['Cant. Completa'].sum()))]
    estado['filas_produccion'] = len(prod)
os.makedirs(out, exist_ok=True)
for n, obj in [('produccion', prod), ('mps', mps), ('estado', [estado])]:
    json.dump(obj, open(os.path.join(out, n + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(estado, ensure_ascii=False, indent=1))
if errores or malos:
    print('\n'.join(errores[:30])); sys.exit('NO PUBLICAR: las cifras no cuadran con el Excel')
