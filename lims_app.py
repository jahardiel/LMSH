"""
Servidor de Aplicación Web LIMS - LSMCH (ISO/IEC 17025)
Laboratorio de Suelos, Materiales y Concreto Hidráulico
"""

import os
import json
import math
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
        cliente_nombre = data.get("cliente_nombre")
        proyecto_nombre = data.get("proyecto_nombre")
        
        if cliente_nombre and proyecto_nombre:
            sol_id, cod_sol = db.crear_solicitud_completa(
                cliente_nombre=cliente_nombre,
                proyecto_nombre=proyecto_nombre,
                ubicacion=data.get("ubicacion", ""),
                numero_informe=data.get("numero_informe", ""),
                muestreado_por=data.get("muestreado_por", ""),
                descripcion=data.get("descripcion", "SUELO"),
                ident_cliente=data.get("ident_cliente", "SUELO"),
                fuente=data.get("fuente", ""),
                ident_lsmch=data.get("ident_lsmch", ""),
                fecha_recepcion=data.get("fecha_recepcion"),
                fecha_entrega_estimada=data.get("fecha_entrega_estimada"),
                observaciones=data.get("observaciones", "")
            )
        else:
            proyecto_id = data.get("proyecto_id")
            cliente_id = data.get("cliente_id")
            if not proyecto_id or not cliente_id:
                return jsonify({"error": "Debe especificar Cliente y Proyecto"}), 400
                
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
            "message": f"Solicitud {cod_sol} generada exitosamente en la base de datos."
        })

    else:
        limite = int(request.args.get("limite", 50))
        return jsonify(db.obtener_solicitudes(limite=limite))

@app.route('/api/lims/solicitudes/<codigo>', methods=['GET'])
def get_solicitud_detalle(codigo):
    sol = db.obtener_solicitud_detalle(codigo)
    if not sol:
        return jsonify({"error": f"No se encontró la solicitud {codigo}"}), 404
    return jsonify(sol)

@app.route('/api/lims/solicitudes/actualizar_informe', methods=['POST'])
def actualizar_informe_solicitud():
    data = request.json or {}
    cod_sol = data.get("codigo_solicitud")
    num_inf = data.get("numero_informe", "").strip()
    if not cod_sol:
        return jsonify({"error": "El código de solicitud es obligatorio"}), 400
    
    db.actualizar_numero_informe(cod_sol, num_inf)
    return jsonify({"success": True, "message": f"Número de informe '{num_inf}' actualizado correctamente para {cod_sol}"})

@app.route('/api/lims/autorizados', methods=['GET'])
def get_usuarios_autorizados():
    return jsonify(db.obtener_usuarios_autorizados())

@app.route('/api/lims/autorizados/crear', methods=['POST'])
def crear_usuario_autorizado_api():
    data = request.json or {}
    nombre = data.get("nombre", "").strip()
    cargo = data.get("cargo", "").strip()
    pin = data.get("pin", "").strip()
    permiso = data.get("nivel_permiso", "SUPERVISOR").strip()

    if not nombre or not cargo or not pin:
        return jsonify({"error": "Nombre, Cargo y PIN son obligatorios"}), 400

    u_id = db.crear_usuario_autorizado(nombre, cargo, pin, permiso)
    return jsonify({"success": True, "usuario_id": u_id, "message": f"Usuario autorizado {nombre} creado con éxito."})

@app.route('/api/lims/autorizados/eliminar', methods=['POST'])
def eliminar_usuario_autorizado_api():
    data = request.json or {}
    u_id = data.get("usuario_id")
    if not u_id:
        return jsonify({"error": "ID de usuario es obligatorio"}), 400

    db.eliminar_usuario_autorizado(u_id)
    return jsonify({"success": True, "message": "Usuario autorizado desactivado con éxito."})



@app.route('/api/lims/solicitudes/eliminar', methods=['POST'])
def eliminar_solicitud_api():
    data = request.json or {}
    cod_sol = data.get("codigo_solicitud")
    usr_id = data.get("usuario_id")
    pin = data.get("pin")
    motivo = data.get("motivo", "")

    if not cod_sol or not usr_id or not pin:
        return jsonify({"error": "Debe proporcionar Solicitud, Usuario Autorizado y PIN de Seguridad."}), 400

    success, msg = db.eliminar_solicitud_con_autorizacion(cod_sol, usr_id, pin, motivo)
    if success:
        return jsonify({"success": True, "message": msg})
    else:
        return jsonify({"success": False, "error": msg}), 403




# ---------------------------------------------------------
# API REST: CÁLCULO Y GUARDADO DE ENSAYO DE GRANULOMETRÍA
# ---------------------------------------------------------
@app.route('/api/lims/ensayos/geotecnia/granulometria', methods=['POST'])
def calcular_granulometria_api():
    data = request.json or {}
    tamices = data.get("tamices", [])
    if not tamices:
        return jsonify({"error": "No se enviaron tamices para procesar"}), 400
        
    res_gran = geotechnics_engine.calcular_granulometria_astm_d6913(data)
    return jsonify(res_gran)

@app.route('/api/lims/ensayos/guardar', methods=['POST'])
def guardar_ensayo_bd():
    try:
        data = request.json or {}
        solicitud_codigo = data.get("codigo_solicitud", "LSMCH-050-2026")
        tipo_ensayo = data.get("tipo_ensayo", "GRANULOMETRIA_ASTM_D6913")
        norma = data.get("norma", "ASTM D6913 / D2487")
        fecha_ensayo = data.get("fecha_ensayo", "2026-08-10")
        datos_json = data.get("datos_entrada", {})
        resultados_json = data.get("resultados", {})

        # Buscar o crear muestra por defecto vinculada a solicitud
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM solicitudes WHERE codigo_solicitud = ?", (solicitud_codigo,))
            row_sol = cursor.fetchone()
            if row_sol:
                sol_id = row_sol["id"]
            else:
                # Si no existe la solicitud exacta, usamos la primera solicitud activa o creamos una
                cursor.execute("SELECT id FROM solicitudes ORDER BY id DESC LIMIT 1")
                row_first = cursor.fetchone()
                sol_id = row_first["id"] if row_first else 1

            # Muestreo
            cursor.execute("SELECT id FROM muestreos WHERE solicitud_id = ?", (sol_id,))
            row_mues = cursor.fetchone()
            if row_mues:
                mues_id = row_mues["id"]
            else:
                mues_id = db.agregar_muestreo(sol_id, "MUE-01", fecha_ensayo, "Técnico LSMCH")

            # Muestra
            cod_muestra = f"{solicitud_codigo}-M01"
            cursor.execute("SELECT id FROM muestras WHERE codigo_muestra = ?", (cod_muestra,))
            row_mu = cursor.fetchone()
            if row_mu:
                mu_id = row_mu["id"]
            else:
                mu_id = db.agregar_muestra(mues_id, cod_muestra, "Suelo Granular")

        ensayo_id = db.guardar_ensayo(
            muestra_id=mu_id,
            tipo_ensayo=tipo_ensayo,
            norma=norma,
            fecha_ensayo=fecha_ensayo,
            datos_json=datos_json,
            resultados_json=resultados_json,
            usuario=datos_json.get("ensayado_por", "Técnico LSMCH")
        )

        return jsonify({
            "success": True,
            "ensayo_id": ensayo_id,
            "codigo_solicitud": solicitud_codigo,
            "message": f"Ensayo de Granulometría (HC-LSMCH-006) guardado exitosamente en la base de datos vinculado a {solicitud_codigo}."
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == '__main__':
    print("Iniciando Sistema LIMS LSMCH (ISO/IEC 17025) en http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=True)
