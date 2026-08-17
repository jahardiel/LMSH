"""
Servidor de Aplicación Web LIMS - LSMCH (ISO/IEC 17025)
Laboratorio de Suelos, Materiales y Concreto Hidráulico
"""

import os
import io
import json
import math
import base64
import numpy as np
from flask import Flask, request, jsonify, render_template, send_file
from database_lims import DatabaseLIMS
from database_manager import DatabaseManager
import geotechnics_engine


app = Flask(__name__, template_folder="templates", static_folder="static")
db = DatabaseLIMS()
db_manager = DatabaseManager()

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

# ---------------------------------------------------------
# API REST: GUARDAR Y RECUPERAR HOJAS DE CÁLCULO (HC) POR MUESTRA Y ENSAYO
# ---------------------------------------------------------
@app.route('/api/lims/hojas/guardar', methods=['POST'])
def api_guardar_hoja():
    try:
        data = request.json or {}
        cod_sol = data.get("codigo_solicitud", "")
        cod_mue = data.get("codigo_muestra", "")
        tipo_ens = data.get("tipo_ensayo", "GRANULOMETRIA")
        norma = data.get("norma", "ASTM D6913")
        datos_j = data.get("datos_json", {})
        res_j = data.get("resultados_json", {})
        usr = data.get("usuario_tecnico", "Analista LIMS")

        if not cod_sol and not cod_mue:
            return jsonify({"success": False, "error": "Debe especificar la Orden de Servicio o el Código de Muestra"}), 400

        ensayo_id = db.guardar_hoja_calculo(
            codigo_solicitud=cod_sol,
            codigo_muestra=cod_mue,
            tipo_ensayo=tipo_ens,
            norma=norma,
            datos_json=datos_j,
            resultados_json=res_j,
            usuario_tecnico=usr
        )

        return jsonify({
            "success": True,
            "ensayo_id": ensayo_id,
            "codigo_solicitud": cod_sol,
            "codigo_muestra": cod_mue,
            "tipo_ensayo": tipo_ens,
            "message": f"Hoja de Cálculo de {tipo_ens} guardada exitosamente para la Orden {cod_sol} / Muestra {cod_mue}."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/lims/hojas/cargar', methods=['GET'])
def api_cargar_hoja():
    try:
        cod_sol = request.args.get("solicitud", "")
        cod_mue = request.args.get("muestra", "")
        tipo_ens = request.args.get("tipo", "GRANULOMETRIA")

        hoja = db.obtener_hoja_calculo(cod_sol, cod_mue, tipo_ens)
        if not hoja:
            return jsonify({"success": False, "found": False, "message": f"No hay Hoja de Cálculo guardada para {tipo_ens} en la Orden {cod_sol} / Muestra {cod_mue}."}), 444

        return jsonify({"success": True, "found": True, "hoja": hoja})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/lims/hojas/listar', methods=['GET'])
def api_listar_hojas():
    try:
        cod_sol = request.args.get("solicitud")
        lista = db.listar_hojas_guardadas(cod_sol)
        return jsonify({"success": True, "hojas": lista})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/lims/incertidumbre/evaluar', methods=['POST'])
def api_evaluar_incertidumbre():
    try:
        data = request.json or {}
        lecturas = data.get("lecturas", [28.5, 28.7, 28.4, 28.6])
        resolucion = float(data.get("resolucion", 0.1))
        u_cal = float(data.get("u_calibracion", 1.5))
        k_cal = float(data.get("k_calibracion", 2.0))
        deriva = float(data.get("deriva", 0.2))
        homogeneidad = float(data.get("homogeneidad", 0.0))
        modulo = data.get("modulo", "compresion")
        unidad = data.get("unidad", "MPa")
        unidad_origen = data.get("unidad_origen", unidad)
        
        puntos_cal = [{
            'temp_indicada': float(np.mean(lecturas)),
            'temp_patron': float(np.mean(lecturas)),
            'correccion': 0.0,
            'u_expandida': u_cal,
            'factor_k': k_cal
        }]

        from gum_calculator import GUMCalculator
        res = GUMCalculator.evaluar_incertidumbre(
            lecturas_concreto=lecturas,
            resolucion=resolucion,
            puntos_calibracion=puntos_cal,
            deriva_estimada=deriva,
            homogeneidad_concreto=homogeneidad,
            unidad=unidad,
            modulo=modulo,
            unidad_origen=unidad_origen
        )


        def sanitize_json(obj):
            if isinstance(obj, dict):
                return {k: sanitize_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_json(v) for v in obj]
            elif hasattr(obj, 'item'):
                return obj.item()
            else:
                return obj

        if "tabla_presupuesto" in res and hasattr(res["tabla_presupuesto"], "to_dict"):
            res["tabla_presupuesto"] = res["tabla_presupuesto"].to_dict(orient="records")

        res_clean = sanitize_json(res)
        return jsonify({"success": True, "resultado": res_clean})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

# ---------------------------------------------------------
# API REST: GESTIÓN DE EQUIPOS METROLÓGICOS Y CERTIFICADOS DE CALIBRACIÓN
# ---------------------------------------------------------
@app.route('/api/termometros', methods=['GET'])
def get_termometros():
    modulo = request.args.get("modulo", None)
    termometros = db_manager.obtener_termometros(modulo=modulo)
    for t in termometros:
        t["puntos_calibracion"] = db_manager.obtener_puntos_calibracion(t["id"])
    return jsonify(termometros)

@app.route('/api/termometros', methods=['POST'])
def crear_termometro():
    try:
        data = request.json or {}
        raw_code = data.get("codigo", "").strip()
        if not raw_code:
            return jsonify({"success": False, "error": "El código del equipo es obligatorio."}), 400
        
        if not raw_code.upper().startswith("LSMCH-EM-"):
            codigo = f"LSMCH-EM-{raw_code}"
        else:
            codigo = raw_code
        
        marca = data.get("marca", "")
        modelo = data.get("modelo", "")
        numero_serie = data.get("numero_serie", "")
        resolucion = float(data.get("resolucion", 0.01))
        homogeneidad = float(data.get("homogeneidad_concreto", 0.10))
        fecha = data.get("fecha_calibracion", "")
        lab = data.get("laboratorio", "")
        num_cert = data.get("numero_certificado", "CERT-17025")

        nombre = data.get("nombre", f"{marca} {modelo}".strip() or "Equipo Metrológico")
        puntos = data.get("puntos_calibracion", [])
        puntos_anteriores = data.get("puntos_calibracion_anteriores", [])
        tiene_anterior = data.get("tiene_calibracion_anterior", len(puntos_anteriores) > 0)

        if tiene_anterior and puntos_anteriores and len(puntos_anteriores) > 0:
            deriva = DatabaseManager.calcular_deriva_entre_certificados(puntos, puntos_anteriores)
        elif "deriva" in data and data["deriva"] is not None:
            deriva = float(data["deriva"])
        else:
            deriva = 0.0

        term_id = db_manager.agregar_termometro(codigo, marca, modelo, numero_serie, resolucion, deriva, fecha, lab, homogeneidad=homogeneidad, numero_certificado=num_cert, nombre=nombre)
        db_manager.actualizar_puntos_calibracion(term_id, puntos, puntos_anteriores)


        return jsonify({
            "success": True, 
            "termometro_id": term_id, 
            "codigo": codigo, 
            "deriva_calculada": deriva,
            "message": f"Equipo metrológico {codigo} registrado exitosamente con deriva de {deriva:.4f}."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/termometros/<int:termometro_id>', methods=['PUT'])
def actualizar_termometro(termometro_id):
    try:
        data = request.json or {}
        raw_code = data.get("codigo", "").strip()
        if not raw_code:
            return jsonify({"success": False, "error": "El código del equipo es obligatorio."}), 400
        
        if not raw_code.upper().startswith("LSMCH-EM-"):
            codigo = f"LSMCH-EM-{raw_code}"
        else:
            codigo = raw_code

        nombre = data.get("nombre", "Equipo Metrológico")
        marca = data.get("marca", "")
        modelo = data.get("modelo", "")
        numero_serie = data.get("numero_serie", "")
        resolucion = float(data.get("resolucion", 0.01))
        homogeneidad = float(data.get("homogeneidad_concreto", 0.10))
        fecha = data.get("fecha_calibracion", "")
        lab = data.get("laboratorio", "")
        num_cert = data.get("numero_certificado", "CERT-17025")

        puntos = data.get("puntos_calibracion", [])
        puntos_anteriores = data.get("puntos_calibracion_anteriores", [])
        tiene_anterior = data.get("tiene_calibracion_anterior", len(puntos_anteriores) > 0)

        if tiene_anterior and puntos_anteriores and len(puntos_anteriores) > 0:
            deriva = DatabaseManager.calcular_deriva_entre_certificados(puntos, puntos_anteriores)
        elif "deriva" in data and data["deriva"] is not None:
            deriva = float(data["deriva"])
        else:
            deriva = 0.0

        exito = db_manager.actualizar_termometro(termometro_id, codigo, marca, modelo, numero_serie, resolucion, deriva, fecha, lab, homogeneidad=homogeneidad, numero_certificado=num_cert, nombre=nombre)
        db_manager.actualizar_puntos_calibracion(termometro_id, puntos, puntos_anteriores)

        return jsonify({
            "success": True, 
            "deriva_calculada": deriva,
            "message": f"Equipo metrológico {codigo} actualizado exitosamente en la Base de Datos."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/termometros/<int:termometro_id>', methods=['DELETE'])
def eliminar_termometro(termometro_id):
    try:
        exito = db_manager.eliminar_termometro(termometro_id)
        if exito:
            return jsonify({"success": True, "message": "Equipo metrológico eliminado correctamente."})
        else:
            return jsonify({"success": False, "error": "No se encontró el equipo especificado."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/cargar-pdf-certificado', methods=['POST'])
def cargar_pdf_certificado():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No se adjuntó ningún archivo PDF."}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "Nombre de archivo vacío."}), 400

        import pypdf, re, io
        file_bytes = io.BytesIO(file.read())
        reader = pypdf.PdfReader(file_bytes)
        
        texto_pdf = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texto_pdf += t + "\n"

        res_data = {
            "codigo": "",
            "nombre": "",
            "marca": "",
            "modelo": "",
            "numero_serie": "",
            "resolucion": 0.01,
            "numero_certificado": "",
            "fecha_calibracion": "",
            "laboratorio": "Centro Experimental de Ingeniería - UTP",
            "puntos_calibracion": []
        }

        m_code = re.search(r'(LSMCH-(?:EM|EA|CR)-\d{2,4})', texto_pdf, re.IGNORECASE)
        if m_code:
            res_data["codigo"] = m_code.group(1).upper()

        m_cert = re.search(r'(03-SI-\d{3,4}-\d{4}|CEI\s+N[°o]?\s*03-SI-\d{3,4}-\d{4})', texto_pdf, re.IGNORECASE)
        if m_cert:
            res_data["numero_certificado"] = m_cert.group(1).strip()

        m_marca = re.search(r'Marca:\s*([^\n\r]+)', texto_pdf, re.IGNORECASE)
        if m_marca:
            res_data["marca"] = m_marca.group(1).split("Modelo:")[0].strip()

        m_mod = re.search(r'Modelo:\s*([^\n\r]+)', texto_pdf, re.IGNORECASE)
        if m_mod:
            res_data["modelo"] = m_mod.group(1).split("Serie:")[0].strip()

        m_serie = re.search(r'Serie:\s*([^\n\r]+)', texto_pdf, re.IGNORECASE)
        if m_serie:
            res_data["numero_serie"] = m_serie.group(1).split("Capacidad")[0].strip()

        m_res = re.search(r'(?:resolución|división\s+mínima|graduación):\s*([\d,\.]+)', texto_pdf, re.IGNORECASE)
        if m_res:
            try:
                res_data["resolucion"] = float(m_res.group(1).replace(",", "."))
            except ValueError:
                pass

        lines = texto_pdf.split("\n")
        pts = []
        for line in lines:
            parts = re.findall(r'[-+]?\d+[.,]\d+|[-+]?\d+', line)
            if len(parts) >= 3:
                try:
                    nums = [float(p.replace(",", ".")) for p in parts[:4]]
                    if len(nums) == 3:
                        ind, err_pat, u_val = nums
                        corr = -err_pat if abs(err_pat) < abs(ind) else (err_pat - ind)
                        pat = ind + corr
                        pts.append({"temp_indicada": ind, "temp_patron": pat, "correccion": corr, "u_expandida": abs(u_val), "factor_k": 2.0})
                    elif len(nums) >= 4:
                        ind, pat, err, u_val = nums[0], nums[1], nums[2], nums[3]
                        corr = -err if abs(err) < abs(ind) else (pat - ind)
                        pts.append({"temp_indicada": ind, "temp_patron": pat, "correccion": corr, "u_expandida": abs(u_val), "factor_k": 2.0})
                except Exception:
                    pass
        
        if pts:
            res_data["puntos_calibracion"] = pts

        return jsonify({"success": True, "datos": res_data, "message": "Datos del certificado extraídos exitosamente del PDF."})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error al procesar el archivo PDF: {str(e)}"}), 400


if __name__ == '__main__':
    print("Iniciando Sistema LIMS LSMCH (ISO/IEC 17025) en http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=True)
