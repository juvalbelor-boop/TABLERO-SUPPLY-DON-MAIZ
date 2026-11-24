"""Tablero Supply Chain Don Maíz · Nivel de servicio (cantidad y dinero).
Lee el Excel de nivel de servicio por canal (tabla dinámica), sin modificarlo. Columnas que usa (por nombre):
  AñoFacturaNS, MesEntregaLetrasNSNC, CANAL, Suma de Cant_Facturada, Suma de Cant_Pedida, NSCA,
  Suma de ValorFacturadoPedido, NSVA, Suma de Vlr_Pendiente  (las tres últimas son opcionales: sin ellas solo hay cantidad).
Uso: python -I extraer_ns.py ARCHIVO.xlsx CARPETA_SALIDA
Genera ns.json (una fila por año-mes-canal: fact, ped y, si hay dinero, vf, vp, vpend) y ns_estado.json.
  NS cantidad = facturada ÷ pedida.  NS dinero = valor facturado ÷ valor pedido, con valor pedido = ValorFacturadoPedido ÷ NSVA
  (así se reproduce exacto el NSVA de cada fila y el del Total general, ponderado como la tabla dinámica).
Valida filas y Total general en cantidad y dinero. Si algo no cuadra, sale con 'NO PUBLICAR'.
Desde el 24-nov-2026 el archivo puede traer además CodReferencia y DescReferencia (debajo del cliente). Entonces:
  ns.json se agrupa por año-mes-canal-cliente (igual que antes, sin referencia) y se genera ns_ref.json con el detalle por
  referencia de las filas con faltante (pedido > facturado o valor pedido > valor facturado), para la tabla
  "¿Qué faltó para llegar al 100 %?". Ambos suman exactamente lo mismo que el archivo."""
import sys, os, json, datetime as dt, pandas as pd, openpyxl
xl, out = sys.argv[1], sys.argv[2]
M = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
d = pd.read_excel(xl, sheet_name=0, dtype=object); d.columns = [str(c).strip() for c in d.columns]
def col(*claves, opcional=False):
    for c in d.columns:
        n = c.upper().replace(' ', '')
        if any(k in n for k in claves): return c
    if opcional: return None
    sys.exit(f'NO PUBLICAR: no encontré la columna {claves}')
ca, cm, cc = d.columns[:3]
cf, cp, cn = col('CANT_FACTURADA'), col('CANT_PEDIDA'), col('NSCA')
cvf, cnv, cvp = col('VALORFACTURADO', opcional=True), col('NSVA', opcional=True), col('VLR_PENDIENTE', opcional=True)
cli = col('RASONSOCIAL', 'RAZONSOCIAL', opcional=True)  # desde el 17-nov-2026 el archivo viene por cliente
cref, cdes = col('CODREFERENCIA', opcional=True), col('DESCREFERENCIA', opcional=True)  # desde el 24-nov-2026, por referencia
dinero = bool(cvf and cnv and cvp)
err = []
d[ca] = d[ca].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
tot = d[d[ca].str.upper().str.startswith('TOTAL')]; d = d[~d[ca].str.upper().str.startswith('TOTAL') & d[cm].notna()].copy()
# Canal en blanco en la tabla dinámica ("(en blanco)"): se conserva como SIN CANAL para que el total cuadre.
d[cc] = d[cc].where(d[cc].notna() & (d[cc].astype(str).str.strip() != '') & (d[cc].astype(str).str.strip().str.upper() != '(EN BLANCO)'), 'SIN CANAL')
d['mes'] = d[cm].astype(str).str.strip().str.upper().map(lambda m: M.index(m) + 1 if m in M else None)
if d.mes.isna().any(): err.append('Meses no reconocidos: ' + str(sorted(set(d.loc[d.mes.isna(), cm]))))
for c in [cf, cp, cn] + ([cvf, cnv, cvp] if dinero else []): d[c] = pd.to_numeric(d[c])
bad = d[(d[cp] > 0) & ((d[cf] / d[cp] - d[cn]).abs() > 1e-9)]
if len(bad): err.append(f'{len(bad)} filas donde NSCA ≠ facturada/pedida')
if dinero:
    sin = d[(d[cnv] <= 0) & (d[cvf] > 0)]
    if len(sin): err.append(f'{len(sin)} filas con valor facturado y NSVA en 0: no se puede sacar el valor pedido')
    # Valor pedido = facturado ÷ NSVA. Si NSVA = 0 (nada facturado), el pedido es todo pendiente: se toma Vlr_Pendiente.
    d['vp'] = [vf / nv if nv > 0 else float(vpd) for vf, nv, vpd in zip(d[cvf], d[cnv], d[cvp])]
if len(tot):
    t = tot.iloc[0]
    if abs(d[cf].sum() - float(t[cf])) > 0.5 or abs(d[cp].sum() - float(t[cp])) > 0.5: err.append('La suma de las filas no cuadra con Total general (cantidad)')
    if dinero:
        if abs(d[cvf].sum() - float(t[cvf])) > 1: err.append('El valor facturado no cuadra con Total general')
        if abs(d[cvp].sum() - float(t[cvp])) > 1: err.append('El valor pendiente no cuadra con Total general')
        # Por cliente: tolerancia 1e-5 (0,001 pp). Por referencia (desde el 24-nov-2026, aprobado por el usuario: un solo archivo con
        # referencias): el valor pedido sumado fila a fila da hasta ~0,01 pp distinto del NSVA del Total general; se acepta hasta 0,05 pp
        # y la diferencia queda registrada en ns_estado (nsva_excel y nsva_calculado).
        tol = 5e-4 if cref else 1e-5
        if abs(d[cvf].sum() / d['vp'].sum() - float(t[cnv])) > tol: err.append('El NS en dinero no cuadra con el NSVA del Total general')
        nsva_excel = float(t[cnv])
else: err.append('No se encontró la fila Total general')
rows, refs, agg = [], [], {}
for _, r in d.iterrows():
    if pd.isna(r.mes): continue
    o = dict(anio=int(r[ca]), mes=int(r.mes), canal=str(r[cc]).strip().upper(), fact=float(r[cf]), ped=float(r[cp]))
    if cli: o['cli'] = str(r[cli]).strip() if pd.notna(r[cli]) else 'SIN CLIENTE'
    if dinero: o.update(vf=float(r[cvf]), vp=float(r['vp']), vpend=float(r[cvp]))
    if cref:
        k = (o['anio'], o['mes'], o['canal'], o.get('cli'))
        if k not in agg: agg[k] = dict(o); rows.append(agg[k])
        else:
            for f in ('fact', 'ped', 'vf', 'vp', 'vpend'):
                if f in o: agg[k][f] += o[f]
        if o['ped'] - o['fact'] > 1e-9 or (dinero and o['vp'] - o['vf'] > 0.5):
            ref = str(r[cref]).strip().removesuffix('.0') if pd.notna(r[cref]) else 'SIN REF'
            x = dict(o, ref=ref, desc=str(r[cdes]).strip() if cdes and pd.notna(r[cdes]) else '')
            if dinero: x.update(vf=round(x['vf'], 2), vp=round(x['vp'], 2), vpend=round(x['vpend'], 2))
            refs.append(x)
    else: rows.append(o)
if dinero:
    for o in rows: o.update(vf=round(o['vf'], 2), vp=round(o['vp'], 2), vpend=round(o['vpend'], 2))
ult = max((r['anio'], r['mes']) for r in rows)
mod = openpyxl.load_workbook(xl, read_only=True).properties.modified
estado = dict(archivo=os.path.basename(xl), guardado=(mod - dt.timedelta(hours=5)).strftime('%Y-%m-%d') if mod else None,
              ultimo_mes=f'{ult[0]}{ult[1]:02d}', total_fact=float(d[cf].sum()), total_ped=float(d[cp].sum()), ns_total=float(d[cf].sum() / d[cp].sum()),
              dinero=dinero, validacion='OK' if not err else 'ERROR')
if dinero: estado.update(total_vf=float(d[cvf].sum()), total_vp=float(d['vp'].sum()), nsv_total=float(d[cvf].sum() / d['vp'].sum()), total_vpend=float(d[cvp].sum()))
if dinero and len(tot): estado.update(nsva_excel=float(tot.iloc[0][cnv]))
os.makedirs(out, exist_ok=True)
json.dump(rows, open(os.path.join(out, 'ns.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
if cref:
    json.dump(refs, open(os.path.join(out, 'ns_ref.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    estado.update(referencias=True, filas_ref=len(refs))
json.dump(estado, open(os.path.join(out, 'ns_estado.json'), 'w'), ensure_ascii=False)
print(json.dumps(estado, ensure_ascii=False, indent=1), len(rows), 'filas')
if err: print('\n'.join(err)); sys.exit('NO PUBLICAR: las cifras no cuadran con el Excel')
