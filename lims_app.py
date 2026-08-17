"""
Servidor de Aplicación Web LIMS - LSMCH (ISO/IEC 17025)
Laboratorio de Suelos, Materiales y Concreto Hidráulico
"""

import os
import json
from flask import Flask, request, jsonify, render_template
from database_lims import DatabaseLIMS
import geotechnics_engine

app = Flask(__name__, template_folder="templates", static_folder="static")
db = DatabaseLIMS()

# ---------------------------------------------------------
# VISTAS PRINCIPALES
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template("lims_index.html")

# ---------------------------------------------------------
# API REST: ESTADÍSTICAS DASHBOARD & BUSCADOR GLOBAL
# ---------------------------------------------------------
@app.route('/api/lims/stats', methods=['GET'])
def get_stats():
    solicitudes = db.obtener_solicitudes(limite=500)
    clientes = db.obtener_clientes()
    proyectos = db.obtener_proyectos()
    
    total_solicitudes = len(solicitudes)
    solicitudes_activas = sum(1 for s in solicitudes if s.get("estado") == "EN_PROCESO")
    
    return jsonify({
        "total_solicitudes": total_solicitudes,
        "solicitudes_activas": solicitudes_activas,
        "total_clientes": len(clientes),
        "total_proyectos": len(proyectos)
    })

@app.route('/api/lims/buscar', methods=['GET'])
def buscar_global():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"solicitudes": [], "muestras": []})
    resultados = db.busqueda_global(q)
    return jsonify(resultados)

# ---------------------------------------------------------
# API REST: CLIENTES Y PROYECTOS
# ---------------------------------------------------------
@app.route('/api/lims/clientes', methods=['GET', 'POST'])
def handle_clientes():
    if request.method == 'POST':
        data = request.json or {}
        nombre = data.get("nombre", "").strip()
        if not nombre:
            return jsonify({"error": "El nombre del cliente es obligatorio"}), 400
        cid = db.agregar_cliente(
            nombre=nombre,
            ruc_nit=data.get("ruc_nit", ""),
            contacto=data.get("contacto", ""),
            email=data.get("email", ""),
            telefono=data.get("telefono", ""),
            direccion=data.get("direccion", "")
        )
        return jsonify({"success": True, "cliente_id": cid, "message": "Cliente registrado correctamente"})
    else:
        return jsonify(db.obtener_clientes())

@app.route('/api/lims/proyectos', methods=['GET', 'POST'])
def handle_proyectos():
    if request.method == 'POST':
        data = request.json or {}
        cliente_id = data.get("cliente_id")
        nombre = data.get("nombre", "").strip()
        if not cliente_id or not nombre:
            return jsonify({"error": "Cliente y nombre del proyecto son obligatorios"}), 400
        pid = db.agregar_proyecto(
            cliente_id=cliente_id,
            nombre=nombre,
            codigo_proyecto=data.get("codigo_proyecto", ""),
            ubicacion=data.get("ubicacion", ""),
            descripcion=data.get("descripcion", "")
        )
        return jsonify({"success": True, "proyecto_id": pid, "message": "Proyecto registrado correctamente"})
    else:
        cliente_id = request.args.get("cliente_id")
        return jsonify(db.obtener_proyectos(cliente_id=cliente_id))

# ---------------------------------------------------------
# API REST: SOLICITUDES (LSMCH-NNN-AAAA)
# ---------------------------------------------------------
@app.route('/api/lims/solicitudes', methods=['GET', 'POST'])
def handle_solicitudes():
    if request.method == 'POST':
        data = request.json or {}
        proyecto_id = data.get("proyecto_id")
        cliente_id = data.get("cliente_id")
        if not proyecto_id or not cliente_id:
            return jsonify({"error": "Proyecto y Cliente son obligatorios"}), 400
            
        sol_id, cod_sol = db.crear_solicitud(
            proyecto_id=proyecto_id,
            cliente_id=cliente_id,
            fecha_recepcion=data.get("fecha_recepcion"),
            fecha_entrega_estimada=data.get("fecha_entrega_estimada"),
            responsable_tecnico=data.get("responsable_tecnico", "Ing. Metrólogo LSMCH"),
            jefe_laboratorio=data.get("jefe_laboratorio", "Dr. Jefe de Laboratorio"),
            observaciones=data.get("observaciones", "")
        )
        return jsonify({
            "success": True,
            "solicitud_id": sol_id,
            "codigo_solicitud": cod_sol,
            "message": f"Solicitud {cod_sol} generada exitosamente con numeración anual automática."
        })
    else:
        limite = int(request.args.get("limite", 50))
        return jsonify(db.obtener_solicitudes(limite=limite))

@app.route('/api/lims/solicitudes/<int:solicitud_id>', methods=['GET'])
def get_solicitud_detalle(solicitud_id):
    detalle = db.obtener_solicitud_detalle(solicitud_id)
    if not detalle:
        return jsonify({"error": "Solicitud no encontrada"}), 404
    return jsonify(detalle)

# ---------------------------------------------------------
# API REST: MUESTREOS Y MUESTRAS
# ---------------------------------------------------------
@app.route('/api/lims/muestreos', methods=['POST'])
def crear_muestreo():
    data = request.json or {}
    solicitud_id = data.get("solicitud_id")
    codigo_muestreo = data.get("codigo_muestreo", "MUE-01")
    fecha_muestreo = data.get("fecha_muestreo")
    responsable = data.get("responsable_muestreo", "Técnico LSMCH")
    ubicacion = data.get("ubicacion_muestreo", "")
    
    mid = db.agregar_muestreo(solicitud_id, codigo_muestreo, fecha_muestreo, responsable, ubicacion)
    return jsonify({"success": True, "muestreo_id": mid, "message": "Muestreo registrado exitosamente"})

@app.route('/api/lims/muestras', methods=['POST'])
def crear_muestra():
    data = request.json or {}
    muestreo_id = data.get("muestreo_id")
    codigo_muestra = data.get("codigo_muestra")
    tipo_material = data.get("tipo_material", "Suelo Limoso Arcilloso")
    
    mu_id = db.agregar_muestra(
        muestreo_id=muestreo_id,
        codigo_muestra=codigo_muestra,
        tipo_material=tipo_material,
        descripcion=data.get("descripcion", ""),
        profundidad_elemento=data.get("profundidad_elemento", "")
    )
    return jsonify({"success": True, "muestra_id": mu_id, "message": "Muestra creada exitosamente"})

# ---------------------------------------------------------
# API REST: CÁLCULOS METROLÓGICOS & GEOTÉCNICOS
# ---------------------------------------------------------
@app.route('/api/lims/ensayos/geotecnia/granulometria', methods=['POST'])
def calcular_granulometria_api():
    data = request.json or {}
    tamices = data.get("tamices", [])
    ll = data.get("ll")
    lp = data.get("lp")
    
    if not tamices:
        return jsonify({"error": "No se enviaron tamices para procesar"}), 400
        
    res_gran = geotechnics_engine.calcular_granulometria(tamices)
    
    ip = None
    if ll is not None and lp is not None:
        try:
            ip = round(float(ll) - float(lp), 2)
        except Exception:
            pass

    sucs = geotechnics_engine.clasificar_sucs(
        pct_finos=res_gran.get("pct_finos"),
        pct_grava=res_gran.get("pct_grava"),
        pct_arena=res_gran.get("pct_arena"),
        ll=float(ll) if ll is not None else None,
        ip=ip,
        cu=res_gran.get("cu"),
        cc=res_gran.get("cc")
    )
    
    res_gran["clasificacion_sucs"] = sucs
    res_gran["ll"] = ll
    res_gran["lp"] = lp
    res_gran["ip"] = ip
    
    # Guardar en base de datos si viene muestra_id
    muestra_id = data.get("muestra_id")
    if muestra_id:
        db.guardar_ensayo(
            muestra_id=muestra_id,
            tipo_ensayo="GRANULOMETRIA_SUCS",
            norma="ASTM D6913 / ASTM D2487",
            fecha_ensayo=data.get("fecha_ensayo", "2026-02-17"),
            datos_json=data,
            resultados_json=res_gran
        )
        
    return jsonify(res_gran)

@app.route('/api/lims/ensayos/geotecnia/proctor', methods=['POST'])
def calcular_proctor_api():
    data = request.json or {}
    puntos = data.get("puntos", [])
    volumen = float(data.get("volumen_molde_cm3", 943.3))
    
    res = geotechnics_engine.calcular_proctor(puntos, volumen_molde_cm3=volumen)
    
    muestra_id = data.get("muestra_id")
    if muestra_id:
        db.guardar_ensayo(
            muestra_id=muestra_id,
            tipo_ensayo="PROCTOR",
            norma="ASTM D698 / D1557",
            fecha_ensayo=data.get("fecha_ensayo", "2026-02-17"),
            datos_json=data,
            resultados_json=res
        )
        
    return jsonify(res)

@app.route('/api/lims/ensayos/concreto/compresion', methods=['POST'])
def calcular_concreto_compresion():
    data = request.json or {}
    especimenes = data.get("especimenes", [])
    # especimenes: [{'codigo': 'C1', 'diametro_cm': 15.0, 'carga_kg': 35000, 'edad_dias': 28}]
    res_especimenes = []
    for esp in especimenes:
        d = float(esp.get("diametro_cm", 15.0))
        c = float(esp.get("carga_kg", 0.0))
        edad = int(esp.get("edad_dias", 28))
        area_cm2 = math.pi * ((d / 2.0) ** 2)
        res_kgcm2 = c / area_cm2 if area_cm2 > 0 else 0.0
        res_mpa = res_kgcm2 * 0.0980665
        
        res_especimenes.append({
            "codigo": esp.get("codigo", ""),
            "diametro_cm": round(d, 2),
            "area_cm2": round(area_cm2, 2),
            "carga_kg": c,
            "edad_dias": edad,
            "resistencia_kgcm2": round(res_kgcm2, 1),
            "resistencia_mpa": round(res_mpa, 2)
        })

    res_final = {
        "especimenes": res_especimenes,
        "promedio_28dias_kgcm2": round(sum(e["resistencia_kgcm2"] for e in res_especimenes) / len(res_especimenes), 1) if res_especimenes else 0.0
    }
    
    muestra_id = data.get("muestra_id")
    if muestra_id:
        db.guardar_ensayo(
            muestra_id=muestra_id,
            tipo_ensayo="CONCRETO_COMPRESION",
            norma="ASTM C39",
            fecha_ensayo=data.get("fecha_ensayo", "2026-02-17"),
            datos_json=data,
            resultados_json=res_final
        )
        
    return jsonify(res_final)

@app.route('/api/lims/incertidumbre/calcular', methods=['POST'])
def calcular_incertidumbre_gum():
    data = request.json or {}
    # Presupuesto GUM ISO 17025
    # u_A (repetibilidad), u_B1 (calibracion), u_B2 (resolucion)
    u_a = float(data.get("u_repetibilidad", 0.05))
    u_b1 = float(data.get("u_calibracion", 0.08)) / 2.0  # k=2
    u_b2 = float(data.get("u_resolucion", 0.01)) / math.sqrt(3)  # Rectangular
    
    u_combinada = math.sqrt(u_a**2 + u_b1**2 + u_b2**2)
    u_expandida = u_combinada * 2.0  # k=2 (95.45% confianza)
    
    # Porcentajes de contribución
    var_total = u_combinada**2 if u_combinada > 0 else 1.0
    contrib_a = round(((u_a**2) / var_total) * 100.0, 1)
    contrib_b1 = round(((u_b1**2) / var_total) * 100.0, 1)
    contrib_b2 = round(((u_b2**2) / var_total) * 100.0, 1)

    return jsonify({
        "incertidumbre_combinada": round(u_combinada, 4),
        "incertidumbre_expandida": round(u_expandida, 4),
        "factor_k": 2.0,
        "nivel_confianza": "95.45%",
        "contribuciones": {
            "repetibilidad_pct": contrib_a,
            "calibracion_balanza_pct": contrib_b1,
            "resolucion_equipo_pct": contrib_b2
        }
    })

if __name__ == '__main__':
    print("Iniciando Sistema LIMS LSMCH (ISO/IEC 17025) en http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=True)
