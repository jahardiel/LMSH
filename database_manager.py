import sqlite3
import os
from typing import List, Dict, Tuple, Optional

DB_FILE = "calibracion_termometros.db"

class DatabaseManager:
    """
    Gestiona la base de datos SQLite para calibración de termómetros.
    Permite registrar termómetros, sus resoluciones, derivas y sus certificados
    de calibración con puntos de prueba (Lectura, Patrón, Corrección, U_cal, k_cal).
    """
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla de termómetros / equipos de laboratorio
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS termometros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE NOT NULL,
                    marca TEXT,
                    modelo TEXT,
                    numero_serie TEXT,
                    resolucion REAL NOT NULL, -- °C o mm
                    deriva_estimada REAL DEFAULT 0.05, -- °C o mm
                    homogeneidad_concreto REAL DEFAULT 0.10,
                    fecha_calibracion TEXT,
                    laboratorio TEXT,
                    numero_certificado TEXT DEFAULT 'CERT-17025',
                    modulo TEXT DEFAULT 'temperatura'
                );
            """)

            # Migraciones automáticas
            try:
                cursor.execute("ALTER TABLE termometros ADD COLUMN homogeneidad_concreto REAL DEFAULT 0.10;")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE termometros ADD COLUMN numero_certificado TEXT DEFAULT 'CERT-17025';")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE termometros ADD COLUMN modulo TEXT DEFAULT 'temperatura';")
            except sqlite3.OperationalError:
                pass

            # Tabla de puntos de calibración
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS puntos_calibracion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    termometro_id INTEGER NOT NULL,
                    tipo_certificado TEXT DEFAULT 'actual', -- 'actual' o 'anterior'
                    temp_indicada REAL NOT NULL, -- °C o mm
                    temp_patron REAL NOT NULL,   -- °C o mm
                    correccion REAL NOT NULL,    -- °C o mm
                    u_expandida REAL NOT NULL,   -- U_cal
                    factor_k REAL NOT NULL DEFAULT 2.0, -- Factor de cobertura k
                    FOREIGN KEY (termometro_id) REFERENCES termometros(id) ON DELETE CASCADE
                );
            """)

            try:
                cursor.execute("ALTER TABLE puntos_calibracion ADD COLUMN tipo_certificado TEXT DEFAULT 'actual';")
            except sqlite3.OperationalError:
                pass

            # Tabla de historial de cálculos guardados por equipo
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calculos_guardados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    termometro_id INTEGER,
                    codigo_termometro TEXT NOT NULL,
                    fecha_hora TEXT NOT NULL,
                    realizado_por TEXT,
                    revisado_por TEXT,
                    unidad TEXT NOT NULL DEFAULT '°C',
                    lecturas_text TEXT NOT NULL,
                    temp_estimada REAL NOT NULL,
                    u_expandida REAL NOT NULL,
                    factor_k REAL NOT NULL,
                    u_combinada REAL NOT NULL,
                    resultado_declarado TEXT NOT NULL,
                    detalles_json TEXT NOT NULL,
                    modulo TEXT DEFAULT 'temperatura',
                    FOREIGN KEY (termometro_id) REFERENCES termometros(id) ON DELETE SET NULL
                );
            """)

            try:
                cursor.execute("ALTER TABLE calculos_guardados ADD COLUMN modulo TEXT DEFAULT 'temperatura';")
            except sqlite3.OperationalError:
                pass

            conn.commit()
            
        # Si la base de datos está vacía, cargar equipos de demostración
        self._cargar_datos_demo_si_vacio()

    def _cargar_datos_demo_si_vacio(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar si existe al menos 1 equipo de temperatura
            cursor.execute("SELECT COUNT(*) FROM termometros WHERE modulo = 'temperatura' OR modulo IS NULL")
            count_temp = cursor.fetchone()[0]
            if count_temp == 0:
                cursor.execute("""
                    INSERT INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'temperatura')
                """, ("LSMCH-EM-01", "Fluke / Hart Scientific", "5615 / 1523", "SN-984521", 0.01, 0.02, 0.10, "2026-01-15", "Laboratorio de Calibración Acreditado ISO/IEC 17025", "CERT-2026-0891"))
                
                term_id = cursor.lastrowid
                puntos_act = [(0.00, 0.02, 0.02, 0.04, 2.00), (25.00, 25.04, 0.04, 0.05, 2.00), (50.00, 50.08, 0.08, 0.06, 2.00)]
                for p in puntos_act:
                    cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (term_id, p[0], p[1], p[2], p[3], p[4]))
                
                puntos_ant = [(0.00, 0.01, 0.01, 0.04, 2.00), (25.00, 25.02, 0.02, 0.05, 2.00), (50.00, 50.06, 0.06, 0.06, 2.00)]
                for p in puntos_ant:
                    cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'anterior', ?, ?, ?, ?, ?)", (term_id, p[0], p[1], p[2], p[3], p[4]))

            # Verificar si existe al menos 1 equipo de asentamiento
            cursor.execute("SELECT COUNT(*) FROM termometros WHERE modulo = 'asentamiento'")
            count_slump = cursor.fetchone()[0]
            if count_slump == 0:
                cursor.execute("""
                    INSERT INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'asentamiento')
                """, ("LSMCH-EM-REGLA-01", "Starrett / Mitutoyo", "Regla Graduada de Metrología", "SN-REGLA-4421", 1.0, 0.5, 0.0, "2026-02-10", "Laboratorio de Metrología Acreditado ISO 17025", "CERT-REGLA-2026-01"))
                
                slump_id = cursor.lastrowid
                puntos_slump = [(75.0, 75.2, 0.2, 0.4, 2.00), (100.0, 100.3, 0.3, 0.5, 2.00), (150.0, 150.5, 0.5, 0.6, 2.00)]
                for p in puntos_slump:
                    cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (slump_id, p[0], p[1], p[2], p[3], p[4]))

            # Verificar si existe al menos 1 equipo de compresión
            cursor.execute("SELECT COUNT(*) FROM termometros WHERE modulo = 'compresion'")
            count_comp = cursor.fetchone()[0]
            if count_comp == 0:
                cursor.execute("""
                    INSERT OR IGNORE INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'compresion')
                """, ("LSMCH-EM-PRENSA-01", "Controls / ELE International", "Prensa Hidráulica Digital 2000 kN", "SN-PRENSA-9912", 0.1, 0.5, 0.0, "2026-01-20", "Laboratorio de Metrología Acreditado ISO 17025", "CERT-PRENSA-2026-05"))
                
                prensa_id = cursor.lastrowid
                puntos_prensa = [(100.0, 100.2, 0.2, 0.8, 2.00), (300.0, 300.5, 0.5, 1.2, 2.00), (500.0, 501.0, 1.0, 1.8, 2.00)]
                for p in puntos_prensa:
                    cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (prensa_id, p[0], p[1], p[2], p[3], p[4]))

                cursor.execute("""
                    INSERT OR IGNORE INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'compresion')
                """, ("LSMCH-EM-VERNIER-01", "Mitutoyo / Starrett", "Calibrador Digital Vernier 0-300 mm", "SN-VERNIER-7710", 0.01, 0.005, 0.0, "2026-01-25", "Laboratorio de Metrología Acreditado ISO 17025", "CERT-VERNIER-2026-03"))

                vernier_id = cursor.lastrowid
                puntos_vernier = [(100.0, 100.01, 0.01, 0.02, 2.00), (150.0, 150.02, 0.02, 0.02, 2.00), (200.0, 200.03, 0.03, 0.03, 2.00)]
                for p in puntos_vernier:
                    cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (vernier_id, p[0], p[1], p[2], p[3], p[4]))

            # Cargar los 4 equipos de los certificados PDF oficiales UTP
            self._cargar_certificados_oficiales_utp(cursor)

            conn.commit()

    def _cargar_certificados_oficiales_utp(self, cursor):
        # 1. LSMCH-EM-037 Balanza Digital RICE LAKE TP-820
        cursor.execute("SELECT id FROM termometros WHERE codigo = 'LSMCH-EM-037'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'concreto')
            """, ("LSMCH-EM-037", "RICE LAKE", "TP-820", "2202218007", 0.01, 0.005, 0.0, "2023-09-11", "Centro Experimental de Ingeniería - UTP", "03-SI-278-2023"))
            t_id = cursor.lastrowid
            pts = [
                (0.00, 0.00, 0.00, 0.01, 2.0),
                (1.00, 1.00, 0.00, 0.01, 2.0),
                (2.00, 2.00, 0.00, 0.01, 2.0),
                (5.00, 5.00, 0.00, 0.01, 2.0),
                (10.00, 10.00, 0.00, 0.01, 2.0),
                (20.00, 20.00, 0.00, 0.01, 2.0),
                (30.00, 30.00, 0.00, 0.01, 2.0),
                (50.00, 50.00, 0.00, 0.01, 2.0),
                (99.99, 100.00, 0.01, 0.01, 2.0),
                (200.00, 200.00, 0.00, 0.01, 2.0),
                (299.99, 300.00, 0.01, 0.01, 2.0),
                (399.99, 400.00, 0.01, 0.01, 2.0),
                (500.00, 500.00, 0.00, 0.01, 2.0),
                (599.99, 600.00, 0.01, 0.01, 2.0),
                (700.00, 700.00, 0.00, 0.01, 2.0),
                (799.99, 800.00, 0.01, 0.01, 2.0)
            ]
            for p in pts:
                cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (t_id, p[0], p[1], p[2], p[3], p[4]))

        # 2. LSMCH-EM-028 Calibrador Vernier Digital CMED
        cursor.execute("SELECT id FROM termometros WHERE codigo = 'LSMCH-EM-028'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'compresion')
            """, ("LSMCH-EM-028", "CMED", "Vernier Digital 600mm", "N/A", 0.01, 0.005, 0.0, "2024-02-28", "Centro Experimental de Ingeniería - UTP", "03-SI-0037-2024"))
            t_id = cursor.lastrowid
            pts = [
                (0.00, 0.00, 0.00, 0.02, 2.0),
                (49.98, 50.00, 0.02, 0.02, 2.0),
                (74.98, 75.00, 0.02, 0.02, 2.0),
                (99.98, 100.00, 0.02, 0.02, 2.0),
                (149.98, 150.00, 0.02, 0.02, 2.0),
                (199.98, 200.00, 0.02, 0.02, 2.0),
                (249.98, 250.00, 0.02, 0.02, 2.0),
                (299.97, 300.00, 0.03, 0.02, 2.0),
                (399.98, 400.00, 0.02, 0.02, 2.0),
                (500.00, 500.00, 0.00, 0.02, 2.0),
                (550.01, 550.00, -0.01, 0.02, 2.0)
            ]
            for p in pts:
                cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (t_id, p[0], p[1], p[2], p[3], p[4]))

        # 3. LSMCH-EM-067 Termómetro Digital Taylor 9878E
        cursor.execute("SELECT id FROM termometros WHERE codigo = 'LSMCH-EM-067'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'temperatura')
            """, ("LSMCH-EM-067", "Taylor", "9878E", "SN-9878E", 0.1, 0.05, 0.0, "2026-06-04", "Centro Experimental de Ingeniería - UTP", "03-SI-0124-2026"))
            t_id = cursor.lastrowid
            pts = [
                (0.0, 0.0, 0.0, 0.1, 2.0),
                (25.2, 25.0, -0.2, 0.1, 2.0),
                (50.2, 50.0, -0.2, 0.1, 2.0)
            ]
            for p in pts:
                cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (t_id, p[0], p[1], p[2], p[3], p[4]))

        # 4. LSMCH-EM-002 Máquina Ensayos ELE 900 kN
        cursor.execute("SELECT id FROM termometros WHERE codigo = 'LSMCH-EM-002'")
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'compresion')
            """, ("LSMCH-EM-002", "ELE International", "36-0690/02", "SN-ELE-900", 0.1, 0.5, 0.0, "2025-10-23", "Centro Experimental de Ingeniería - UTP", "03-SI-0356-2025"))
            t_id = cursor.lastrowid
            pts = [
                (100.0, 99.3, -0.7, 0.1, 2.0),
                (200.0, 198.7, -1.3, 0.8, 2.0),
                (300.0, 298.7, -1.3, 0.6, 2.0),
                (400.0, 398.6, -1.4, 2.0, 2.0),
                (500.0, 498.4, -1.6, 2.5, 2.0),
                (600.0, 597.7, -2.3, 1.8, 2.0),
                (700.0, 697.4, -2.6, 0.7, 2.0),
                (800.0, 796.8, -3.2, 1.6, 2.0),
                (900.0, 896.9, -3.1, 0.9, 2.0)
            ]
            for p in pts:
                cursor.execute("INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k) VALUES (?, 'actual', ?, ?, ?, ?, ?)", (t_id, p[0], p[1], p[2], p[3], p[4]))

    @staticmethod
    def calcular_deriva_entre_certificados(puntos_actuales: List[Dict], puntos_anteriores: Optional[List[Dict]]) -> float:
        """
        Calcula la deriva instrumental d = max(|C_actual,i - C_anterior,i|).
        Si no existe calibración anterior, retorna 0.000 (deriva nula).
        """
        if not puntos_anteriores or len(puntos_anteriores) == 0:
            return 0.0

        dif_max = 0.0
        for p_act in puntos_actuales:
            c_act = p_act.get("temp_patron", 0.0) - p_act.get("temp_indicada", 0.0)
            t_ind = p_act.get("temp_indicada", 0.0)
            
            # Buscar el punto más cercano en la calibración anterior
            p_ant_match = min(puntos_anteriores, key=lambda x: abs(x.get("temp_indicada", 0.0) - t_ind))
            c_ant = p_ant_match.get("temp_patron", 0.0) - p_ant_match.get("temp_indicada", 0.0)
            
            dif = abs(c_act - c_ant)
            if dif > dif_max:
                dif_max = dif
                
        return float(round(dif_max, 4))

    def agregar_termometro(self, codigo: str, marca: str, modelo: str, serie: str, resolucion: float, deriva: float, fecha: str, lab: str, homogeneidad: float = 0.10, numero_certificado: str = "CERT-17025", modulo: str = "temperatura") -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO termometros (codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo, marca, modelo, serie, resolucion, deriva, homogeneidad, fecha, lab, numero_certificado, modulo))
            conn.commit()
            return cursor.lastrowid

    def agregar_punto_calibracion(self, termometro_id: int, temp_ind: float, temp_ref: float, U_cal: float, k_cal: float = 2.0, tipo_certificado: str = 'actual'):
        correccion = temp_ref - temp_ind
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (termometro_id, tipo_certificado, temp_ind, temp_ref, correccion, U_cal, k_cal))
            conn.commit()

    def obtener_termometros(self, modulo: Optional[str] = None) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if modulo:
                cursor.execute("SELECT id, codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo FROM termometros WHERE modulo = ?", (modulo,))
            else:
                cursor.execute("SELECT id, codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo FROM termometros")
            rows = cursor.fetchall()
            termometros = []
            for r in rows:
                t_id = r[0]
                ptos_act = self.obtener_puntos_calibracion(t_id, tipo='actual')
                ptos_ant = self.obtener_puntos_calibracion(t_id, tipo='anterior')
                
                termometros.append({
                    "id": r[0], "codigo": r[1], "marca": r[2], "modelo": r[3],
                    "numero_serie": r[4], "resolucion": r[5], "deriva_estimada": r[6],
                    "homogeneidad_concreto": r[7], "fecha_calibracion": r[8], "laboratorio": r[9],
                    "numero_certificado": r[10] if len(r) > 10 and r[10] else "CERT-17025",
                    "modulo": r[11] if len(r) > 11 and r[11] else "temperatura",
                    "puntos_calibracion": ptos_act,
                    "puntos_calibracion_anteriores": ptos_ant
                })
            return termometros

    def obtener_termometro(self, termometro_id: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, codigo, marca, modelo, numero_serie, resolucion, deriva_estimada, homogeneidad_concreto, fecha_calibracion, laboratorio, numero_certificado, modulo FROM termometros WHERE id = ?", (termometro_id,))
            r = cursor.fetchone()
            if not r:
                return None
            ptos_act = self.obtener_puntos_calibracion(r[0], tipo='actual')
            ptos_ant = self.obtener_puntos_calibracion(r[0], tipo='anterior')
            return {
                "id": r[0], "codigo": r[1], "marca": r[2], "modelo": r[3],
                "numero_serie": r[4], "resolucion": r[5], "deriva_estimada": r[6],
                "homogeneidad_concreto": r[7], "fecha_calibracion": r[8], "laboratorio": r[9],
                "numero_certificado": r[10] if len(r) > 10 and r[10] else "CERT-17025",
                "modulo": r[11] if len(r) > 11 and r[11] else "temperatura",
                "puntos_calibracion": ptos_act,
                "puntos_calibracion_anteriores": ptos_ant
            }

    def obtener_puntos_calibracion(self, termometro_id: int, tipo: str = 'actual') -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT temp_indicada, temp_patron, correccion, u_expandida, factor_k
                FROM puntos_calibracion
                WHERE termometro_id = ? AND (tipo_certificado = ? OR (tipo_certificado IS NULL AND ? = 'actual'))
                ORDER BY temp_indicada ASC
            """, (termometro_id, tipo, tipo))
            rows = cursor.fetchall()
            return [{
                "temp_indicada": r[0], "temp_patron": r[1], "correccion": r[2],
                "u_expandida": r[3], "factor_k": r[4]
            } for r in rows]

    def eliminar_termometro(self, termometro_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM termometros WHERE id = ?", (termometro_id,))
            conn.commit()
            return cursor.rowcount > 0

    def actualizar_termometro(self, termometro_id: int, codigo: str, marca: str, modelo: str, serie: str, resolucion: float, deriva: float, fecha: str, lab: str, homogeneidad: float = 0.10, numero_certificado: str = "CERT-17025") -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE termometros
                SET codigo = ?, marca = ?, modelo = ?, numero_serie = ?, resolucion = ?, deriva_estimada = ?, homogeneidad_concreto = ?, fecha_calibracion = ?, laboratorio = ?, numero_certificado = ?
                WHERE id = ?
            """, (codigo, marca, modelo, serie, resolucion, deriva, homogeneidad, fecha, lab, numero_certificado, termometro_id))
            conn.commit()
            return cursor.rowcount > 0

    def actualizar_puntos_calibracion(self, termometro_id: int, puntos_actuales: List[Dict], puntos_anteriores: Optional[List[Dict]] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM puntos_calibracion WHERE termometro_id = ?", (termometro_id,))
            
            # Guardar puntos actuales
            for p in puntos_actuales:
                if p.get("temp_indicada") is not None and p.get("temp_patron") is not None and p.get("u_expandida") is not None:
                    try:
                        temp_ind = float(p["temp_indicada"])
                        temp_ref = float(p["temp_patron"])
                        correccion = temp_ref - temp_ind
                        u_exp = float(p["u_expandida"])
                        factor_k = float(p.get("factor_k", 2.0))
                        cursor.execute("""
                            INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k)
                            VALUES (?, 'actual', ?, ?, ?, ?, ?)
                        """, (termometro_id, temp_ind, temp_ref, correccion, u_exp, factor_k))
                    except (ValueError, TypeError):
                        pass

            # Guardar puntos anteriores si existen
            if puntos_anteriores:
                for p in puntos_anteriores:
                    if p.get("temp_indicada") is not None and p.get("temp_patron") is not None:
                        try:
                            temp_ind = float(p["temp_indicada"])
                            temp_ref = float(p["temp_patron"])
                            correccion = temp_ref - temp_ind
                            u_exp = float(p.get("u_expandida", 0.05))
                            factor_k = float(p.get("factor_k", 2.0))
                            cursor.execute("""
                                INSERT INTO puntos_calibracion (termometro_id, tipo_certificado, temp_indicada, temp_patron, correccion, u_expandida, factor_k)
                                VALUES (?, 'anterior', ?, ?, ?, ?, ?)
                            """, (termometro_id, temp_ind, temp_ref, correccion, u_exp, factor_k))
                        except (ValueError, TypeError):
                            pass

            conn.commit()

    def guardar_calculo(self, termometro_id: Optional[int], codigo_termometro: str, realizado_por: str, revisado_por: str, unidad: str, lecturas_text: str, temp_estimada: float, u_expandida: float, factor_k: float, u_combinada: float, resultado_declarado: str, detalles_json: str) -> int:
        import datetime
        fecha_hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO calculos_guardados (termometro_id, codigo_termometro, fecha_hora, realizado_por, revisado_por, unidad, lecturas_text, temp_estimada, u_expandida, factor_k, u_combinada, resultado_declarado, detalles_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (termometro_id, codigo_termometro, fecha_hora, realizado_por, revisado_por, unidad, lecturas_text, temp_estimada, u_expandida, factor_k, u_combinada, resultado_declarado, detalles_json))
            conn.commit()
            return cursor.lastrowid

    def obtener_calculos(self, termometro_id: Optional[int] = None) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if termometro_id:
                cursor.execute("""
                    SELECT id, termometro_id, codigo_termometro, fecha_hora, realizado_por, revisado_por, unidad, lecturas_text, temp_estimada, u_expandida, factor_k, u_combinada, resultado_declarado
                    FROM calculos_guardados
                    WHERE termometro_id = ?
                    ORDER BY id DESC
                """, (termometro_id,))
            else:
                cursor.execute("""
                    SELECT id, termometro_id, codigo_termometro, fecha_hora, realizado_por, revisado_por, unidad, lecturas_text, temp_estimada, u_expandida, factor_k, u_combinada, resultado_declarado
                    FROM calculos_guardados
                    ORDER BY id DESC
                """)
            rows = cursor.fetchall()
            return [{
                "id": r[0], "termometro_id": r[1], "codigo_termometro": r[2],
                "fecha_hora": r[3], "realizado_por": r[4], "revisado_por": r[5],
                "unidad": r[6], "lecturas_text": r[7], "temp_estimada": r[8],
                "u_expandida": r[9], "factor_k": r[10], "u_combinada": r[11],
                "resultado_declarado": r[12]
            } for r in rows]

    def obtener_calculo_por_id(self, calculo_id: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, termometro_id, codigo_termometro, fecha_hora, realizado_por, revisado_por, unidad, lecturas_text, temp_estimada, u_expandida, factor_k, u_combinada, resultado_declarado, detalles_json
                FROM calculos_guardados
                WHERE id = ?
            """, (calculo_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0], "termometro_id": row[1], "codigo_termometro": row[2],
                "fecha_hora": row[3], "realizado_por": row[4], "revisado_por": row[5],
                "unidad": row[6], "lecturas_text": row[7], "temp_estimada": row[8],
                "u_expandida": row[9], "factor_k": row[10], "u_combinada": row[11],
                "resultado_declarado": row[12], "detalles_json": row[13]
            }

    def eliminar_calculo(self, calculo_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM calculos_guardados WHERE id = ?", (calculo_id,))
            conn.commit()
            return cursor.rowcount > 0

if __name__ == "__main__":
    db = DatabaseManager()
    print("Base de datos inicializada correctamente.")
    print("Termómetros registrados:", db.obtener_termometros())
