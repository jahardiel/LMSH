import os
import io
import json
import base64
from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
from database_manager import DatabaseManager
from gum_calculator import GUMCalculator
from uncertainty_plots import generar_graficos_incertidumbre
from excel_handler import crear_plantilla_excel, leer_datos_excel

app = Flask(__name__, template_folder="templates", static_folder="static")
db = DatabaseManager()

# Asegurar archivo plantilla de ejemplo
EXCEL_PLANTILLA = "plantilla_medicion_concreto.xlsx"
if not os.path.exists(EXCEL_PLANTILLA):
    crear_plantilla_excel(EXCEL_PLANTILLA)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/api/termometros', methods=['GET'])
def get_termometros():
    modulo = request.args.get("modulo", None)
    termometros = db.obtener_termometros(modulo=modulo)
    for t in termometros:
        t["puntos_calibracion"] = db.obtener_puntos_calibracion(t["id"])
    return jsonify(termometros)

@app.route('/api/termometros', methods=['POST'])
def crear_termometro():
    try:
        data = request.json or {}
        raw_code = data.get("codigo", "").strip()
        if not raw_code:
            return jsonify({"success": False, "error": "El código del termómetro es obligatorio."}), 400
        
        # Formatear el código asegurando el prefijo LSMCH-EM-
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

        puntos = data.get("puntos_calibracion", [])
        puntos_anteriores = data.get("puntos_calibracion_anteriores", [])
        tiene_anterior = data.get("tiene_calibracion_anterior", len(puntos_anteriores) > 0)

        if tiene_anterior and puntos_anteriores and len(puntos_anteriores) > 0:
            deriva = DatabaseManager.calcular_deriva_entre_certificados(puntos, puntos_anteriores)
        elif "deriva" in data and data["deriva"] is not None:
            deriva = float(data["deriva"])
        else:
            deriva = 0.0

        term_id = db.agregar_termometro(codigo, marca, modelo, numero_serie, resolucion, deriva, fecha, lab, homogeneidad=homogeneidad, numero_certificado=num_cert)
        db.actualizar_puntos_calibracion(term_id, puntos, puntos_anteriores)

        return jsonify({
            "success": True, 
            "termometro_id": term_id, 
            "codigo": codigo, 
            "deriva_calculada": deriva,
            "message": f"Termómetro {codigo} registrado exitosamente con deriva de {deriva:.4f} °C."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/termometros/<int:termometro_id>/puntos', methods=['POST'])
def agregar_punto(termometro_id):
    try:
        data = request.json or {}
        temp_ind = float(data["temp_indicada"])
        temp_ref = float(data["temp_patron"])
        u_exp = float(data["u_expandida"])
        factor_k = float(data.get("factor_k", 2.0))

        db.agregar_punto_calibracion(termometro_id, temp_ind, temp_ref, u_exp, factor_k)
        return jsonify({"success": True, "message": "Punto de calibración agregado exitosamente."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/termometros/<int:termometro_id>', methods=['DELETE'])
def eliminar_termometro(termometro_id):
    try:
        exito = db.eliminar_termometro(termometro_id)
        if exito:
            return jsonify({"success": True, "message": "Termómetro eliminado correctamente."})
        else:
            return jsonify({"success": False, "error": "No se encontró el termómetro especificado."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/termometros/<int:termometro_id>', methods=['PUT'])
def actualizar_termometro(termometro_id):
    try:
        data = request.json or {}
        raw_code = data.get("codigo", "").strip()
        if not raw_code:
            return jsonify({"success": False, "error": "El código del termómetro es obligatorio."}), 400
        
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

        puntos = data.get("puntos_calibracion", [])
        puntos_anteriores = data.get("puntos_calibracion_anteriores", [])
        tiene_anterior = data.get("tiene_calibracion_anterior", len(puntos_anteriores) > 0)

        if tiene_anterior and puntos_anteriores and len(puntos_anteriores) > 0:
            deriva = DatabaseManager.calcular_deriva_entre_certificados(puntos, puntos_anteriores)
        elif "deriva" in data and data["deriva"] is not None:
            deriva = float(data["deriva"])
        else:
            deriva = 0.0

        exito = db.actualizar_termometro(termometro_id, codigo, marca, modelo, numero_serie, resolucion, deriva, fecha, lab, homogeneidad=homogeneidad, numero_certificado=num_cert)
        db.actualizar_puntos_calibracion(termometro_id, puntos, puntos_anteriores)

        return jsonify({
            "success": True, 
            "deriva_calculada": deriva,
            "message": f"Termómetro {codigo} actualizado exitosamente con deriva de {deriva:.4f} °C."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/calcular', methods=['POST'])
def calcular():
    try:
        data = request.json or {}
        modulo = data.get("modulo", "temperatura")
        
        default_lecturas = [23.4, 23.6, 23.5, 23.7, 23.5, 23.4] if modulo == "temperatura" else ([75.0, 80.0, 75.0, 70.0, 75.0] if modulo == "asentamiento" else [285.4, 290.1, 288.5, 292.0])
        default_res = 0.01 if modulo == "temperatura" else (1.0 if modulo == "asentamiento" else 0.1)
        default_deriva = 0.05 if modulo == "temperatura" else (0.5 if modulo == "asentamiento" else 0.5)
        default_unit = "°C" if modulo == "temperatura" else ("mm" if modulo == "asentamiento" else "MPa")

        lecturas = data.get("lecturas", default_lecturas)
        resolucion = float(data.get("resolucion", default_res))
        deriva = float(data.get("deriva", default_deriva))
        homogeneidad = float(data.get("homogeneidad", 0.00))
        puntos_cal = data.get("puntos_calibracion", [])
        unidad = data.get("unidad", default_unit)
        diametro_mm = float(data.get("diametro_mm", 100.0))
        longitud_mm = float(data.get("longitud_mm", 200.0))
        lecturas_d = data.get("lecturas_diametro", [])
        lecturas_l = data.get("lecturas_longitud", [])
        vernier_id = data.get("vernier_id")

        puntos_cal_vernier = []
        res_vernier = 0.01
        deriva_vernier = 0.005

        if modulo == "compresion":
            if vernier_id:
                term_v = db.obtener_termometro(int(vernier_id))
                if term_v:
                    puntos_cal_vernier = db.obtener_puntos_calibracion(term_v["id"])
                    res_vernier = term_v["resolucion"]
                    deriva_vernier = term_v["deriva_estimada"]
            else:
                # Buscar Vernier en la BD
                terms = db.obtener_termometros(modulo="compresion")
                verniers = [t for t in terms if "VERNIER" in t["codigo"].upper() or "CALIBRADOR" in t["modelo"].upper()]
                if verniers:
                    puntos_cal_vernier = db.obtener_puntos_calibracion(verniers[0]["id"])
                    res_vernier = verniers[0]["resolucion"]
                    deriva_vernier = verniers[0]["deriva_estimada"]

        if not puntos_cal:
            # Usar primer equipo del módulo en BD si no se enviaron puntos
            terms = db.obtener_termometros(modulo=modulo)
            prensas = [t for t in terms if "PRENSA" in t["codigo"].upper() or "PRENSA" in t["modelo"].upper()]
            target_term = prensas[0] if prensas else (terms[0] if terms else None)
            if target_term:
                puntos_cal = db.obtener_puntos_calibracion(target_term["id"])

        res = GUMCalculator.evaluar_incertidumbre(
            lecturas_concreto=lecturas,
            resolucion=resolucion,
            puntos_calibracion=puntos_cal,
            deriva_estimada=deriva,
            homogeneidad_concreto=homogeneidad,
            unidad=unidad,
            modulo=modulo,
            diametro_mm=diametro_mm,
            longitud_mm=longitud_mm,
            lecturas_diametro=lecturas_d,
            lecturas_longitud=lecturas_l,
            puntos_calibracion_vernier=puntos_cal_vernier,
            resolucion_vernier=res_vernier,
            deriva_vernier=deriva_vernier
        )

        # Generar gráfico en memoria base64
        img_path = "temp_grafico_web.png"
        generar_graficos_incertidumbre(res, filename=img_path, show_plot=False)
        
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        if os.path.exists(img_path):
            os.remove(img_path)

        # Convertir dataframe a dict serializable
        res["tabla_presupuesto_json"] = res["tabla_presupuesto"].to_dict(orient="records")
        del res["tabla_presupuesto"]
        res["grafico_base64"] = f"data:image/png;base64,{img_b64}"

        return jsonify({"success": True, "data": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/importar-excel', methods=['POST'])
def importar_excel():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No se envió ningún archivo Excel"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "Nombre de archivo vacío"}), 400

        unidad = request.form.get("unidad", "°C")

        # Leer archivo Excel 100% en memoria con BytesIO para evitar bloqueos de archivo en Windows
        file_bytes = io.BytesIO(file.read())
        datos_excel = leer_datos_excel(file_bytes)

        # Si el Excel no trajo puntos de calibración, usaremos el termómetro por defecto de la BD
        puntos_cal = datos_excel["puntos_calibracion"]
        if not puntos_cal:
            terms = db.obtener_termometros()
            if terms:
                puntos_cal = db.obtener_puntos_calibracion(terms[0]["id"])

        res = GUMCalculator.evaluar_incertidumbre(
            lecturas_concreto=datos_excel["lecturas"],
            resolucion=datos_excel["resolucion"],
            puntos_calibracion=puntos_cal,
            deriva_estimada=datos_excel["deriva"],
            homogeneidad_concreto=datos_excel["homogeneidad"],
            unidad=unidad
        )

        img_path = "temp_grafico_excel.png"
        generar_graficos_incertidumbre(res, filename=img_path, show_plot=False)
        
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception:
                pass

        res["tabla_presupuesto_json"] = res["tabla_presupuesto"].to_dict(orient="records")
        del res["tabla_presupuesto"]
        res["grafico_base64"] = f"data:image/png;base64,{img_b64}"
        res["datos_excel_importados"] = datos_excel

        return jsonify({"success": True, "data": res})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error al procesar archivo Excel: {str(e)}"}), 400

@app.route('/api/descargar-plantilla', methods=['GET'])
def descargar_plantilla():
    if not os.path.exists(EXCEL_PLANTILLA):
        crear_plantilla_excel(EXCEL_PLANTILLA)
    return send_file(EXCEL_PLANTILLA, as_attachment=True, download_name="plantilla_medicion_concreto.xlsx")

# --- ENDPOINTS HISTORIAL DE CÁLCULOS / ENSAYOS ---

@app.route('/api/calculos/guardar', methods=['POST'])
def guardar_calculo():
    try:
        data = request.json or {}
        term_id = data.get("termometro_id")
        codigo = data.get("codigo_termometro", "LSMCH-EM-XX")
        realizado = data.get("realizado_por", "Responsable Técnico")
        revisado = data.get("revisado_por", "Jefe de Laboratorio")
        unidad = data.get("unidad", "°C")
        lecturas_text = data.get("lecturas_text", "")
        temp_est = float(data.get("temp_estimada", 0.0))
        u_exp = float(data.get("u_expandida", 0.0))
        factor_k = float(data.get("factor_k", 2.0))
        u_comb = float(data.get("u_combinada", 0.0))
        res_dec = data.get("resultado_declarado", "")
        detalles_json = json.dumps(data.get("detalles_calculo", {}))

        calc_id = db.guardar_calculo(
            termometro_id=term_id,
            codigo_termometro=codigo,
            realizado_por=realizado,
            revisado_por=revisado,
            unidad=unidad,
            lecturas_text=lecturas_text,
            temp_estimada=temp_est,
            u_expandida=u_exp,
            factor_k=factor_k,
            u_combinada=u_comb,
            resultado_declarado=res_dec,
            detalles_json=detalles_json
        )

        return jsonify({"success": True, "calculo_id": calc_id, "message": f"Cálculo N° {calc_id} guardado correctamente en la BD."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/calculos', methods=['GET'])
def listar_calculos():
    try:
        term_id = request.args.get("termometro_id", type=int)
        calculos = db.obtener_calculos(termometro_id=term_id)
        return jsonify({"success": True, "calculos": calculos})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/calculos/<int:calculo_id>', methods=['GET'])
def obtener_calculo(calculo_id):
    try:
        calc = db.obtener_calculo_por_id(calculo_id)
        if not calc:
            return jsonify({"success": False, "error": "No se encontró el cálculo especificado."}), 404
        calc["detalles_calculo"] = json.loads(calc["detalles_json"]) if calc.get("detalles_json") else {}
        return jsonify({"success": True, "calculo": calc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/api/calculos/<int:calculo_id>', methods=['DELETE'])
def eliminar_calculo(calculo_id):
    try:
        exito = db.eliminar_calculo(calculo_id)
        if exito:
            return jsonify({"success": True, "message": "Registro de cálculo eliminado del historial."})
        else:
            return jsonify({"success": False, "error": "No se encontró el cálculo."}), 404
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

        # Extraer Código de Equipo
        m_code = re.search(r'(LSMCH-(?:EM|EA|CR)-\d{2,4})', texto_pdf, re.IGNORECASE)
        if m_code:
            res_data["codigo"] = m_code.group(1).upper()

        # Extraer Número de Certificado
        m_cert = re.search(r'(03-SI-\d{3,4}-\d{4}|CEI\s+N[°o]?\s*03-SI-\d{3,4}-\d{4})', texto_pdf, re.IGNORECASE)
        if m_cert:
            res_data["numero_certificado"] = m_cert.group(1).strip()

        # Extraer Marca
        m_marca = re.search(r'Marca:\s*([^\n\r]+)', texto_pdf, re.IGNORECASE)
        if m_marca:
            res_data["marca"] = m_marca.group(1).split("Modelo:")[0].strip()

        # Extraer Modelo
        m_mod = re.search(r'Modelo:\s*([^\n\r]+)', texto_pdf, re.IGNORECASE)
        if m_mod:
            res_data["modelo"] = m_mod.group(1).split("Serie:")[0].strip()

        # Extraer Serie
        m_serie = re.search(r'Serie:\s*([^\n\r]+)', texto_pdf, re.IGNORECASE)
        if m_serie:
            res_data["numero_serie"] = m_serie.group(1).split("Capacidad")[0].strip()

        # Extraer Resolución
        m_res = re.search(r'(?:resolución|división\s+mínima|graduación):\s*([\d,\.]+)', texto_pdf, re.IGNORECASE)
        if m_res:
            try:
                res_data["resolucion"] = float(m_res.group(1).replace(",", "."))
            except ValueError:
                pass

        # Extraer Fecha
        m_fecha = re.search(r'(?:Fecha\s+de\s+la\s+calibración|Fecha\s+de\s+emisión):\s*([^\n\r]+)', texto_pdf, re.IGNORECASE)
        if m_fecha:
            res_data["fecha_calibracion"] = m_fecha.group(1).strip()

        # Extraer Puntos de Calibración
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

        return jsonify({"success": True, "datos": res_data, "message": "Datos de certificado extraídos exitosamente del PDF."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Error al procesar el archivo PDF: {str(e)}"}), 400

if __name__ == '__main__':
    print("Iniciando Servidor Web Metrológico GUM en http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
