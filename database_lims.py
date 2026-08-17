"""
Gestor de Base de Datos Relacional LIMS - LSMCH
Sistema de Gestión de Información de Laboratorio (ISO/IEC 17025)
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = "lims_lsmch.db"

class DatabaseLIMS:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()
        self.seed_demo_data()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla 1: Clientes
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                ruc_nit TEXT,
                contacto TEXT,
                email TEXT,
                telefono TEXT,
                direccion TEXT,
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Tabla 2: Proyectos
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS proyectos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                codigo_proyecto TEXT,
                ubicacion TEXT,
                descripcion TEXT,
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
            );
            """)

            # Tabla 3: Solicitudes (Código LSMCH-NNN-AAAA)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS solicitudes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_solicitud TEXT UNIQUE NOT NULL,
                numero_informe TEXT,
                proyecto_id INTEGER NOT NULL,
                cliente_id INTEGER NOT NULL,
                anio INTEGER NOT NULL,
                numero_correlativo INTEGER NOT NULL,
                fecha_recepcion DATE NOT NULL,
                fecha_entrega_estimada DATE,
                responsable_tecnico TEXT,
                jefe_laboratorio TEXT,
                observaciones TEXT,
                estado TEXT DEFAULT 'EN_PROCESO',
                fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (proyecto_id) REFERENCES proyectos(id) ON DELETE CASCADE,
                FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
            );
            """)

            try:
                cursor.execute("ALTER TABLE solicitudes ADD COLUMN numero_informe TEXT;")
            except Exception:
                pass


            # Tabla 4: Muestreos
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS muestreos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitud_id INTEGER NOT NULL,
                codigo_muestreo TEXT NOT NULL,
                fecha_muestreo DATE NOT NULL,
                responsable_muestreo TEXT,
                ubicacion_muestreo TEXT,
                observaciones TEXT,
                FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
            );
            """)

            # Tabla 5: Muestras
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS muestras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                muestreo_id INTEGER NOT NULL,
                codigo_muestra TEXT UNIQUE NOT NULL,
                tipo_material TEXT NOT NULL,
                descripcion TEXT,
                profundidad_elemento TEXT,
                estado TEXT DEFAULT 'RECIBIDA',
                FOREIGN KEY (muestreo_id) REFERENCES muestreos(id) ON DELETE CASCADE
            );
            """)

            # Tabla 6: Ensayos
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ensayos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                muestra_id INTEGER NOT NULL,
                tipo_ensayo TEXT NOT NULL, -- 'GRANULOMETRIA', 'LIMITES', 'PROCTOR', 'CBR', 'CONCRETO', etc.
                norma TEXT NOT NULL,
                estado TEXT DEFAULT 'CALCULADO', -- 'EN_PROCESO', 'CALCULADO', 'VALIDADO'
                fecha_ensayo DATE NOT NULL,
                usuario_tecnico TEXT,
                datos_json TEXT, -- Entradas crudas de la hoja de cálculo
                resultados_json TEXT, -- Resultados calculados
                fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (muestra_id) REFERENCES muestras(id) ON DELETE CASCADE
            );
            """)

            # Tabla 7: Fuentes de Incertidumbre (GUM / ISO 17025)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS incertidumbre_presupuestos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ensayo_id INTEGER NOT NULL,
                tipo_ensayo TEXT NOT NULL,
                incertidumbre_combinada REAL,
                incertidumbre_expandida REAL,
                factor_k REAL DEFAULT 2.0,
                fuentes_json TEXT,
                fecha_calculo DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ensayo_id) REFERENCES ensayos(id) ON DELETE CASCADE
            );
            """)

            # Tabla 9: Usuarios Autorizados LIMS (Nivel de Autorización ISO 17025)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios_autorizados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                cargo TEXT NOT NULL,
                pin_autorizacion TEXT NOT NULL,
                nivel_permiso TEXT DEFAULT 'Técnico de Laboratorio',
                activo INTEGER DEFAULT 1
            );
            """)

            # Insertar usuarios demo si la tabla está vacía
            cursor.execute("SELECT COUNT(*) FROM usuarios_autorizados")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO usuarios_autorizados (nombre, cargo, pin_autorizacion, nivel_permiso) VALUES
                    ('Dr. Alexis Arrocha', 'Jefe de Laboratorio LSMCH', '17025', 'Jefe de Laboratorio'),
                    ('Ing. Néstor Saldaña', 'Responsable Técnico Metrólogo', '9999', 'Responsable Técnico'),
                    ('Ing. Jahardiel CO', 'Supervisor de Calidad LSMCH', '8888', 'Supervisor de Calidad'),
                    ('Técnico LSMCH', 'Analista de Ensayo', '1234', 'Técnico de Laboratorio')
                """)

            conn.commit()

    def obtener_usuarios_autorizados(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre, cargo, nivel_permiso FROM usuarios_autorizados WHERE activo = 1 ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def crear_usuario_autorizado(self, nombre, cargo, pin, nivel_permiso="Técnico de Laboratorio"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usuarios_autorizados (nombre, cargo, pin_autorizacion, nivel_permiso, activo)
                VALUES (?, ?, ?, ?, 1)
            """, (nombre.strip(), cargo.strip(), str(pin).strip(), nivel_permiso.strip()))
            conn.commit()
            return cursor.lastrowid

    def eliminar_usuario_autorizado(self, usuario_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios_autorizados SET activo = 0 WHERE id = ?", (usuario_id,))
            conn.commit()
            return True

    def validar_pin_autorizacion(self, usuario_id_o_ninguno, pin):
        pin_str = str(pin).strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if usuario_id_o_ninguno and str(usuario_id_o_ninguno).isdigit():
                cursor.execute("SELECT * FROM usuarios_autorizados WHERE id = ? AND pin_autorizacion = ? AND activo = 1", (usuario_id_o_ninguno, pin_str))
                row = cursor.fetchone()
                if row: return dict(row)
            
            # Buscar por PIN en todos los usuarios activos
            cursor.execute("SELECT * FROM usuarios_autorizados WHERE pin_autorizacion = ? AND activo = 1", (pin_str,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def eliminar_solicitud_con_autorizacion(self, codigo_solicitud, usuario_id, pin, motivo=""):
        usuario = self.validar_pin_autorizacion(usuario_id, pin)
        if not usuario:
            return False, "Código PIN de autorización incorrecto o no registrado."

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM solicitudes WHERE codigo_solicitud = ? OR id = ?", (codigo_solicitud, str(codigo_solicitud)))
            conn.commit()
            return True, f"Orden de Servicio {codigo_solicitud} eliminada exitosamente por {usuario['nombre']} ({usuario['cargo']})."


    # ----------------------------------------------------
    # GENERADOR AUTOMÁTICO LSMCH-NNN-AAAA
    # ----------------------------------------------------

    def generar_codigo_solicitud(self, anio=None):
        if not anio:
            anio = datetime.now().year
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(numero_correlativo) FROM solicitudes WHERE anio = ?
            """, (anio,))
            max_num = cursor.fetchone()[0]
            
            siguiente_num = 1 if max_num is None else max_num + 1
            codigo_solicitud = f"LSMCH-{siguiente_num:03d}-{anio}"
            return codigo_solicitud, siguiente_num, anio

    # ----------------------------------------------------
    # OPERACIONES CLIENTES & PROYECTOS
    # ----------------------------------------------------
    def agregar_cliente(self, nombre, ruc_nit="", contacto="", email="", telefono="", direccion=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clientes (nombre, ruc_nit, contacto, email, telefono, direccion)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (nombre, ruc_nit, contacto, email, telefono, direccion))
            conn.commit()
            return cursor.lastrowid

    def obtener_clientes(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes ORDER BY nombre ASC")
            return [dict(row) for row in cursor.fetchall()]

    def agregar_proyecto(self, cliente_id, nombre, codigo_proyecto="", ubicacion="", descripcion=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO proyectos (cliente_id, nombre, codigo_proyecto, ubicacion, descripcion)
                VALUES (?, ?, ?, ?, ?)
            """, (cliente_id, nombre, codigo_proyecto, ubicacion, descripcion))
            conn.commit()
            return cursor.lastrowid

    def obtener_proyectos(self, cliente_id=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if cliente_id:
                cursor.execute("""
                    SELECT p.*, c.nombre as cliente_nombre 
                    FROM proyectos p 
                    JOIN clientes c ON p.cliente_id = c.id 
                    WHERE p.cliente_id = ?
                    ORDER BY p.id DESC
                """, (cliente_id,))
            else:
                cursor.execute("""
                    SELECT p.*, c.nombre as cliente_nombre 
                    FROM proyectos p 
                    JOIN clientes c ON p.cliente_id = c.id 
                    ORDER BY p.id DESC
                """)
            return [dict(row) for row in cursor.fetchall()]

    def crear_solicitud_completa(self, cliente_nombre, proyecto_nombre, ubicacion="", numero_informe="", 
                                 muestreado_por="", descripcion="SUELO", ident_cliente="SUELO", fuente="", ident_lsmch="",
                                 fecha_recepcion=None, fecha_entrega_estimada=None, observaciones=""):
        if not fecha_recepcion:
            fecha_recepcion = datetime.now().strftime("%Y-%m-%d")

        cliente_nombre = str(cliente_nombre or "").strip()
        proyecto_nombre = str(proyecto_nombre or "").strip()
        ubicacion = str(ubicacion or "").strip()
        numero_informe = str(numero_informe or "").strip()
        muestreado_por = str(muestreado_por or "").strip()
        descripcion = str(descripcion or "SUELO").strip()
        ident_cliente = str(ident_cliente or "SUELO").strip()
        fuente = str(fuente or "").strip()
        ident_lsmch = str(ident_lsmch or "").strip()
        observaciones = str(observaciones or "").strip()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Buscar o Crear Cliente
            cursor.execute("SELECT id FROM clientes WHERE nombre = ?", (cliente_nombre,))
            row_c = cursor.fetchone()
            if row_c:
                cliente_id = row_c["id"]
            else:
                cursor.execute("INSERT INTO clientes (nombre) VALUES (?)", (cliente_nombre,))
                cliente_id = cursor.lastrowid
                
            # 2. Buscar o Crear Proyecto
            cursor.execute("SELECT id FROM proyectos WHERE nombre = ? AND cliente_id = ?", (proyecto_nombre, cliente_id))
            row_p = cursor.fetchone()
            if row_p:
                proyecto_id = row_p["id"]
            else:
                cursor.execute("INSERT INTO proyectos (cliente_id, nombre, ubicacion) VALUES (?, ?, ?)", 
                               (cliente_id, proyecto_nombre, ubicacion))
                proyecto_id = cursor.lastrowid

            # 3. Generar Solicitud LSMCH-NNN-AAAA (Ej. LSMCH-002-2026)
            anio_actual = datetime.now().year
            cursor.execute("SELECT MAX(numero_correlativo) FROM solicitudes WHERE anio = ?", (anio_actual,))
            max_num = cursor.fetchone()[0]
            siguiente_num = 1 if max_num is None else max_num + 1
            codigo_solicitud = f"LSMCH-{siguiente_num:03d}-{anio_actual}"

            cursor.execute("""
                INSERT INTO solicitudes (codigo_solicitud, numero_informe, proyecto_id, cliente_id, anio, numero_correlativo,
                                        fecha_recepcion, fecha_entrega_estimada, responsable_tecnico, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo_solicitud, numero_informe or f"LSMCH-{siguiente_num:03d}-{anio_actual}",
                  proyecto_id, cliente_id, anio_actual, siguiente_num,
                  fecha_recepcion, fecha_entrega_estimada, muestreado_por, observaciones))
            
            sol_id = cursor.lastrowid

            # 4. Crear Muestreo y Muestra asociada
            cursor.execute("""
                INSERT INTO muestreos (solicitud_id, codigo_muestreo, fecha_muestreo, responsable_muestreo, ubicacion_muestreo, observaciones)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sol_id, f"MUE-{siguiente_num:02d}", fecha_recepcion, muestreado_por, ubicacion, fuente))
            muestreo_id = cursor.lastrowid

            # Garantizar unicidad absoluta de cod_muestra sin colisiones SQLite
            base_cod = ident_lsmch if ident_lsmch else f"{codigo_solicitud}-M01"
            cod_muestra = base_cod
            counter = 1
            while True:
                cursor.execute("SELECT COUNT(*) FROM muestras WHERE codigo_muestra = ?", (cod_muestra,))
                if cursor.fetchone()[0] == 0:
                    break
                counter += 1
                cod_muestra = f"{base_cod}-{counter}"

            cursor.execute("""
                INSERT INTO muestras (muestreo_id, codigo_muestra, tipo_material, descripcion, profundidad_elemento)
                VALUES (?, ?, ?, ?, ?)
            """, (muestreo_id, cod_muestra, "SUELO", descripcion, fuente))

            conn.commit()
            return sol_id, codigo_solicitud




    def crear_solicitud(self, proyecto_id, cliente_id, fecha_recepcion=None, fecha_entrega_estimada=None, 
                        responsable_tecnico="Ing. Metrólogo", jefe_laboratorio="Dr. Jefe de Lab", observaciones=""):

        if not fecha_recepcion:
            fecha_recepcion = datetime.now().strftime("%Y-%m-%d")

        anio_actual = datetime.now().year
        codigo_solicitud, num_correlativo, anio = self.generar_codigo_solicitud(anio_actual)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO solicitudes (codigo_solicitud, proyecto_id, cliente_id, anio, numero_correlativo,
                                        fecha_recepcion, fecha_entrega_estimada, responsable_tecnico, jefe_laboratorio, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo_solicitud, proyecto_id, cliente_id, anio, num_correlativo,
                  fecha_recepcion, fecha_entrega_estimada, responsable_tecnico, jefe_laboratorio, observaciones))
            conn.commit()
            return cursor.lastrowid, codigo_solicitud

    def obtener_solicitudes(self, limite=50):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, p.nombre as proyecto_nombre, c.nombre as cliente_nombre
                FROM solicitudes s
                JOIN proyectos p ON s.proyecto_id = p.id
                JOIN clientes c ON s.cliente_id = c.id
                ORDER BY s.id DESC
                LIMIT ?
            """, (limite,))
            return [dict(row) for row in cursor.fetchall()]

    def actualizar_numero_informe(self, solicitud_id_o_codigo, numero_informe):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE solicitudes SET numero_informe = ?
                WHERE id = ? OR codigo_solicitud = ?
            """, (numero_informe, solicitud_id_o_codigo, str(solicitud_id_o_codigo)))
            conn.commit()
            return True

    def obtener_solicitud_detalle(self, solicitud_id):

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, p.nombre as proyecto_nombre, p.ubicacion as proyecto_ubicacion,
                       c.nombre as cliente_nombre, c.ruc_nit, c.contacto, c.email
                FROM solicitudes s
                JOIN proyectos p ON s.proyecto_id = p.id
                JOIN clientes c ON s.cliente_id = c.id
                WHERE s.id = ? OR s.codigo_solicitud = ?
            """, (solicitud_id, str(solicitud_id)))
            row = cursor.fetchone()
            if not row:
                return None
            sol_dict = dict(row)
            
            # Obtener muestreos
            cursor.execute("SELECT * FROM muestreos WHERE solicitud_id = ?", (sol_dict["id"],))
            muestreos = [dict(m) for m in cursor.fetchall()]
            
            for m in muestreos:
                cursor.execute("SELECT * FROM muestras WHERE muestreo_id = ?", (m["id"],))
                muestras = [dict(mu) for mu in cursor.fetchall()]
                for mu in muestras:
                    cursor.execute("SELECT * FROM ensayos WHERE muestra_id = ?", (mu["id"],))
                    mu["ensayos"] = [dict(e) for e in cursor.fetchall()]
                m["muestras"] = muestras
                
            sol_dict["muestreos"] = muestreos
            return sol_dict

    # ----------------------------------------------------
    # OPERACIONES MUESTREOS Y MUESTRAS
    # ----------------------------------------------------
    def agregar_muestreo(self, solicitud_id, codigo_muestreo, fecha_muestreo, responsable, ubicacion=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO muestreos (solicitud_id, codigo_muestreo, fecha_muestreo, responsable_muestreo, ubicacion_muestreo)
                VALUES (?, ?, ?, ?, ?)
            """, (solicitud_id, codigo_muestreo, fecha_muestreo, responsable, ubicacion))
            conn.commit()
            return cursor.lastrowid

    def agregar_muestra(self, muestreo_id, codigo_muestra, tipo_material, descripcion="", profundidad_elemento=""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO muestras (muestreo_id, codigo_muestra, tipo_material, descripcion, profundidad_elemento)
                VALUES (?, ?, ?, ?, ?)
            """, (muestreo_id, codigo_muestra, tipo_material, descripcion, profundidad_elemento))
            conn.commit()
            return cursor.lastrowid

    # ----------------------------------------------------
    # OPERACIONES ENSAYOS E INCERTIDUMBRE
    # ----------------------------------------------------
    def guardar_ensayo(self, muestra_id, tipo_ensayo, norma, fecha_ensayo, datos_json, resultados_json, usuario="Tecnico LSMCH"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            d_str = json.dumps(datos_json) if isinstance(datos_json, (dict, list)) else datos_json
            r_str = json.dumps(resultados_json) if isinstance(resultados_json, (dict, list)) else resultados_json
            
            cursor.execute("""
                INSERT INTO ensayos (muestra_id, tipo_ensayo, norma, fecha_ensayo, usuario_tecnico, datos_json, resultados_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (muestra_id, tipo_ensayo, norma, fecha_ensayo, usuario, d_str, r_str))
            conn.commit()
            return cursor.lastrowid

    def obtener_ensayos(self, muestra_id=None, tipo_ensayo=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT e.*, m.codigo_muestra, m.tipo_material FROM ensayos e JOIN muestras m ON e.muestra_id = m.id WHERE 1=1"
            params = []
            if muestra_id:
                query += " AND e.muestra_id = ?"
                params.append(muestra_id)
            if tipo_ensayo:
                query += " AND e.tipo_ensayo = ?"
                params.append(tipo_ensayo)
            query += " ORDER BY e.id DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            resultado = []
            for r in rows:
                d = dict(r)
                d["datos"] = json.loads(d["datos_json"]) if d["datos_json"] else {}
                d["resultados"] = json.loads(d["resultados_json"]) if d["resultados_json"] else {}
                resultado.append(d)
            return resultado

    # ----------------------------------------------------
    # BUSCADOR GLOBAL
    # ----------------------------------------------------
    def busqueda_global(self, termino):
        termino = f"%{termino.strip()}%"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Buscar en solicitudes
            cursor.execute("""
                SELECT s.id, s.codigo_solicitud, 'SOLICITUD' as tipo, s.fecha_recepcion as fecha, c.nombre as cliente
                FROM solicitudes s
                JOIN clientes c ON s.cliente_id = c.id
                WHERE s.codigo_solicitud LIKE ? OR c.nombre LIKE ?
            """, (termino, termino))
            solicitudes = [dict(r) for r in cursor.fetchall()]
            
            # Buscar en muestras
            cursor.execute("""
                SELECT m.id, m.codigo_muestra, 'MUESTRA' as tipo, m.tipo_material as detalle, s.codigo_solicitud
                FROM muestras m
                JOIN muestreos mu ON m.muestreo_id = mu.id
                JOIN solicitudes s ON mu.solicitud_id = s.id
                WHERE m.codigo_muestra LIKE ? OR m.descripcion LIKE ?
            """, (termino, termino))
            muestras = [dict(r) for r in cursor.fetchall()]
            
            return {
                "solicitudes": solicitudes,
                "muestras": muestras
            }

    # ----------------------------------------------------
    # DATOS DE DEMO INICIALES
    # ----------------------------------------------------
    def seed_demo_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM clientes")
            if cursor.fetchone()[0] > 0:
                return

        c_id = self.agregar_cliente(
            nombre="Constructora e Inmobiliaria San Martin S.A.",
            ruc_nit="20458912301",
            contacto="Ing. Carlos Mendoza",
            email="cmendoza@sanmartin.com",
            telefono="+51 987 654 321",
            direccion="Av. Universidad 450, Lima"
        )
        
        p_id = self.agregar_proyecto(
            cliente_id=c_id,
            nombre="Edificio Facultativo de Ingeniería - Campus Central",
            codigo_proyecto="PRY-2026-EFI",
            ubicacion="Sector 4 - Campus Universitario",
            descripcion="Supervisión geotécnica y control de calidad de concreto."
        )

        sol_id, cod_sol = self.crear_solicitud(
            proyecto_id=p_id,
            cliente_id=c_id,
            fecha_recepcion="2026-02-10",
            fecha_entrega_estimada="2026-02-25",
            responsable_tecnico="Ing. Metrólogo LSMCH",
            jefe_laboratorio="Dr. Jefe de Laboratorio",
            observaciones="Solicitud inicial de ensayo de suelos y resistencia de concreto."
        )

        mues_id = self.agregar_muestreo(
            solicitud_id=sol_id,
            codigo_muestreo="MUE-01",
            fecha_muestreo="2026-02-09",
            responsable="Técnico de Campo LSMCH",
            ubicacion="Calicata C-1 a C-3"
        )

        muestra_id = self.agregar_muestra(
            muestreo_id=mues_id,
            codigo_muestra=f"{cod_sol}-M01",
            tipo_material="Suelo Limoso Arcilloso con Grava",
            descripcion="Calicata 1, Muestra M-1",
            profundidad_elemento="Profundidad 1.50m a 2.20m"
        )

        # Cargar un ensayo de granulometría demo
        from geotechnics_engine import calcular_granulometria, clasificar_sucs
        tamices_demo = [
            {"tamiz": '3"', "apertura_mm": 75.0, "masa_retenida": 0.0},
            {"tamiz": '2"', "apertura_mm": 50.0, "masa_retenida": 0.0},
            {"tamiz": '1 1/2"', "apertura_mm": 37.5, "masa_retenida": 120.0},
            {"tamiz": '1"', "apertura_mm": 25.0, "masa_retenida": 180.0},
            {"tamiz": '3/4"', "apertura_mm": 19.0, "masa_retenida": 250.0},
            {"tamiz": '3/8"', "apertura_mm": 9.5, "masa_retenida": 310.0},
            {"tamiz": 'N° 4', "apertura_mm": 4.75, "masa_retenida": 420.0},
            {"tamiz": 'N° 10', "apertura_mm": 2.0, "masa_retenida": 350.0},
            {"tamiz": 'N° 40', "apertura_mm": 0.425, "masa_retenida": 480.0},
            {"tamiz": 'N° 200', "apertura_mm": 0.075, "masa_retenida": 520.0},
            {"tamiz": 'Fondo', "apertura_mm": 0.0, "masa_retenida": 370.0}
        ]
        res_gran = calcular_granulometria(tamices_demo)
        sucs_demo = clasificar_sucs(res_gran["pct_finos"], res_gran["pct_grava"], res_gran["pct_arena"], ll=38.0, ip=16.0, cu=res_gran["cu"], cc=res_gran["cc"])
        res_gran["clasificacion_sucs"] = sucs_demo
        res_gran["ll"] = 38.0
        res_gran["lp"] = 22.0
        res_gran["ip"] = 16.0

        self.guardar_ensayo(
            muestra_id=muestra_id,
            tipo_ensayo="GRANULOMETRIA_SUCS",
            norma="ASTM D6913 / ASTM D2487",
            fecha_ensayo="2026-02-12",
            datos_json={"tamices": tamices_demo, "ll": 38.0, "lp": 22.0},
            resultados_json=res_gran
        )
