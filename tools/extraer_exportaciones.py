"""Tablero Supply Chain Don Maíz · Exportaciones (pedido vigente y órdenes de producción).
Lee del Excel OTIF_Don_Maiz.xlsx, sin modificarlo, las tablas Pedidos_Exportacion (hoja Exportaciones) y
Ordenes_Exportacion (hoja Ordenes de Exportaciones), con los valores que dejó calculados el Excel.
Uso: python -I extraer_exportaciones.py OTIF_Don_Maiz.xlsx CARPETA_SALIDA [exportaciones_publicado.json]
Genera exportaciones.json: filas tipo 'ped' (una por referencia del pedido) y tipo 'op' (una por orden de producción).
Si se da el JSON publicado, conserva los pedidos anteriores (otra fecha de despacho o cliente) y las OP que ya no vienen: histórico.
Valida, fila por fila, que lo que el tablero recalcula sea igual a lo que muestra el Excel:
  Producido = suma de 'Cantidad completa' de las OP '1. Item OP' de la referencia; % completo = MIN(1, producido ÷ pedido);
  Falta = MAX(0, pedido - producido); Falta después de programado = MAX(0, falta - programado pendiente); Estado (con la fecha
  de guardado del Excel como hoy) y la fila TOTAL. Si algo no cuadra, sale con 'NO PUBLICAR'."""
import sys, os, json, datetime as dt, openpyxl
xl, out = sys.argv[1], sys.argv[2]
prev = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else []
wb = openpyxl.load_workbook(xl, data_only=True)
def tabla(nombre):
    for ws in wb.worksheets:
        if nombre in ws.tables:
            rng = ws[ws.tables[nombre].ref]; head = [str(c.value).strip() if c.value is not None else '' for c in rng[0]]
            return ws, head, [[c.value for c in r] for r in rng[1:]]
    sys.exit(f'NO PUBLICAR: no encontré la tabla {nombre}')
def col(head, *claves):
    for i, h in enumerate(head):
        n = h.upper().replace(' ', '')
        if any(k in n for k in claves): return i
    sys.exit(f'NO PUBLICAR: no encontré la columna {claves}')
err = []
mod = wb.properties.modified
hoy = (mod - dt.timedelta(hours=5)).date() if mod else dt.date.today()
fecha = lambda v: v.date() if isinstance(v, dt.datetime) else v if isinstance(v, dt.date) else None
num = lambda v: float(v) if isinstance(v, (int, float)) else 0.0
# Órdenes de producción
ws, h, filas = tabla('Ordenes_Exportacion')
iop, iest, itip, iref, ides, iord, icomp, ifec = (col(h, 'OP') if h[0].upper() == 'OP' else 0), col(h, 'ESTADO'), col(h, 'TIPO'), col(h, 'REFERENCIA'), col(h, 'DESCRIP'), col(h, 'ORDENADA'), col(h, 'COMPLETA'), col(h, 'FECHA')
ops = []
for r in filas:
    if r[iref] is None: continue
    f = fecha(r[ifec])
    ops.append(dict(tipo='op', op=str(r[iop]).strip(), est=str(r[iest] or '').strip(), reg=str(r[itip] or '').strip(), ref=str(r[iref]).strip(),
                    desc=str(r[ides] or '').strip(), ord=num(r[iord]), comp=num(r[icomp]), f=f.isoformat() if f else None))
# Pedido
ws, h, filas = tabla('Pedidos_Exportacion')
icli, iref, ides, iped, idesp, iprod, ipct, ifal, iprog, ifd, iest = (col(h, 'CLIENTE'), col(h, 'REFERENCIA'), col(h, 'DESCRIP'), col(h, 'PEDIDO'), col(h, 'DESPACHO'),
    col(h, 'PRODUCIDO'), col(h, '%COMPLETO'), h.index('Falta'), col(h, 'PROGRAMADOPENDIENTE'), col(h, 'FALTADESPU'), col(h, 'ESTADO'))
peds = []
for r in filas:
    if r[iref] is None: continue
    ref = str(r[iref]).strip(); ped = num(r[iped]); desp = fecha(r[idesp])
    prod = sum(o['comp'] for o in ops if o['ref'] == ref and o['reg'] == '1. Item OP')
    pct = min(1, prod / ped) if ped else None; falta = max(0, ped - prod); prog = num(r[iprog]); fd = max(0, falta - prog)
    estado = 'COMPLETO' if falta == 0 else 'NO CUMPLIÓ' if desp and hoy > desp else 'CUBIERTO CON LO PROGRAMADO' if fd == 0 else 'FALTA PROGRAMAR'
    for nom, mio, xl_ in [('producido', prod, r[iprod]), ('% completo', pct, r[ipct]), ('falta', falta, r[ifal]), ('falta después de programado', fd, r[ifd])]:
        if xl_ is None or mio is None or abs(mio - num(xl_)) > 1e-6: err.append(f'{ref}: {nom} {mio} ≠ Excel {xl_}')
    if estado != str(r[iest]).strip(): err.append(f'{ref}: estado {estado} ≠ Excel {r[iest]}')
    peds.append(dict(tipo='ped', cli=str(r[icli] or '').strip(), ref=ref, desc=str(r[ides] or '').strip(), ped=ped, desp=desp.isoformat() if desp else None,
                     prod=prod, prog=prog, estado_xl=str(r[iest]).strip(), guardado=hoy.isoformat()))
# Fila TOTAL (debajo de la tabla)
tot = None
for row in ws.iter_rows(values_only=True):
    if any(str(v).strip().upper() == 'TOTAL' for v in row if v is not None): tot = row
if tot is None: err.append('No encontré la fila TOTAL de Exportaciones')
else:
    for nom, i, mio in [('pedido', iped, sum(p['ped'] for p in peds)), ('producido', iprod, sum(p['prod'] for p in peds)),
                        ('falta', ifal, sum(max(0, p['ped'] - p['prod']) for p in peds)), ('programado pendiente', iprog, sum(p['prog'] for p in peds))]:
        if abs(mio - num(tot[i])) > 1e-6: err.append(f'TOTAL {nom} {mio} ≠ Excel {tot[i]}')
if not peds: err.append('La tabla de pedidos está vacía')
# Histórico: pedidos de otros despachos/clientes y OP que ya no vienen en el Excel
claves = {(p['cli'], p['desp']) for p in peds}; ids = {o['op'] for o in ops}
viejos = [r for r in prev if r.get('tipo') == 'ped' and (r['cli'], r['desp']) not in claves] + [r for r in prev if r.get('tipo') == 'op' and r['op'] not in ids]
rows = peds + ops + viejos
os.makedirs(out, exist_ok=True)
json.dump(rows, open(os.path.join(out, 'exportaciones.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(dict(guardado=hoy.isoformat(), pedidos=sorted({f"{c} {d}" for c, d in claves}), refs=len(peds), ops=len(ops), historico=len(viejos),
                      pedido=sum(p['ped'] for p in peds), producido=sum(p['prod'] for p in peds), validacion='OK' if not err else 'ERROR'), ensure_ascii=False, indent=1))
if err: print('\n'.join(err)); sys.exit('NO PUBLICAR: las cifras no cuadran con el Excel')
