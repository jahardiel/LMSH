import numpy as np
import pandas as pd
from scipy.stats import t
from typing import List, Dict, Tuple, Optional

class GUMCalculator:
    """
    Calculadora de Incertidumbre de Medición de Temperatura del Concreto
    según la Guía GUM (ISO/IEC Guide 98-3).
    """

    @staticmethod
    def interpolar_calibracion(puntos_calibracion: List[Dict], temp_medida: float) -> Tuple[float, float, float]:
        """
        Interpola linealmente la corrección y la incertidumbre del certificado
        para una temperatura medida dada.
        
        Retorna: (correccion_interpolada, u_cal_estandar, factor_k_cal)
        """
        if not puntos_calibracion:
            return 0.0, 0.05, 2.0  # Valores predeterminados si no hay datos de calibración

        temps = np.array([float(p["temp_indicada"]) for p in puntos_calibracion])
        corrs = np.array([float(p["correccion"]) for p in puntos_calibracion])
        u_exp = np.array([float(p.get("u_expandida", 0.1)) for p in puntos_calibracion])

        # Ordenar por magnitud/temperatura indicada ascendente para interpolación exacta np.interp
        idx = np.argsort(temps)
        temps = temps[idx]
        corrs = corrs[idx]
        u_exp = u_exp[idx]

        # Interpolación lineal metrológica exacta dentro del rango de medición
        corr_interp = float(np.interp(temp_medida, temps, corrs))
        u_exp_interp = float(np.interp(temp_medida, temps, u_exp))
        k_interp = 2.0  # Factor de cobertura k para certificados es 2.00 constante

        # Incertidumbre estándar del certificado u_cal = U_cal / 2.0
        u_cal_std = u_exp_interp / k_interp

        return corr_interp, u_cal_std, k_interp


    @staticmethod
    def convertir_valor(val: float, orig: str, dest: str, es_delta: bool = False) -> float:
        """
        Convierte lecturas o diferencias metrológicas entre °F <-> °C, psi <-> MPa, in <-> mm.
        """
        if not orig or not dest:
            return float(val)
        u_orig = str(orig).strip().lower()
        u_dest = str(dest).strip().lower()
        if u_orig == u_dest:
            return float(val)

        # Temperatura °F <-> °C
        if ("°f" in u_orig or "f" == u_orig) and ("°c" in u_dest or "c" == u_dest):
            return float(val / 1.8) if es_delta else float((val - 32.0) / 1.8)
        elif ("°c" in u_orig or "c" == u_orig) and ("°f" in u_dest or "f" == u_dest):
            return float(val * 1.8) if es_delta else float(val * 1.8 + 32.0)

        # Presión psi <-> MPa
        elif "psi" in u_orig and "mpa" in u_dest:
            return float(val * 0.006894757)
        elif "mpa" in u_orig and "psi" in u_dest:
            return float(val * 145.0377)

        # Longitud in <-> mm
        elif ("in" in u_orig or "pulg" in u_orig) and "mm" in u_dest:
            return float(val * 25.4)
        elif "mm" in u_orig and ("in" in u_dest or "pulg" in u_dest):
            return float(val / 25.4)

        return float(val)

    @classmethod
    def evaluar_incertidumbre(
        cls,
        lecturas_concreto: List[float],
        resolucion: float,
        puntos_calibracion: List[Dict],
        deriva_estimada: float = 0.05,
        homogeneidad_concreto: float = 0.00,
        nivel_confianza: float = 0.9545,
        unidad: str = "°C",
        modulo: str = "temperatura",
        diametro_mm: float = 100.0,
        longitud_mm: float = 200.0,
        lecturas_diametro: Optional[List[float]] = None,
        lecturas_longitud: Optional[List[float]] = None,
        puntos_calibracion_vernier: Optional[List[Dict]] = None,
        resolucion_vernier: float = 0.01,
        deriva_vernier: float = 0.005,
        unidad_origen: Optional[str] = None
    ) -> Dict:
        """
        Realiza la evaluación de la incertidumbre de medición paso a paso según la GUM.
        Soporta Módulo 1 (Temperatura), Módulo 2 (Asentamiento) y Módulo 3 (Compresión ASTM C39).
        Transforma automáticamente datos del certificado si unidad_origen != unidad (unidad destino).
        """
        unidad_destino = unidad
        u_orig = unidad_origen or unidad_destino

        # Convertir datos si unidad_origen es diferente de unidad_destino
        if u_orig and unidad_destino and u_orig.strip().lower() != unidad_destino.strip().lower():
            # 1. Transformar resolucion y deriva
            resolucion = cls.convertir_valor(resolucion, u_orig, unidad_destino, es_delta=True)
            deriva_estimada = cls.convertir_valor(deriva_estimada, u_orig, unidad_destino, es_delta=True)
            homogeneidad_concreto = cls.convertir_valor(homogeneidad_concreto, u_orig, unidad_destino, es_delta=True)

            # 2. Transformar puntos de calibracion
            puntos_convertidos = []
            for p in (puntos_calibracion or []):
                p_ind = cls.convertir_valor(p.get("temp_indicada", 0.0), u_orig, unidad_destino, es_delta=False)
                p_pat = cls.convertir_valor(p.get("temp_patron", 0.0), u_orig, unidad_destino, es_delta=False)
                p_corr = cls.convertir_valor(p.get("correccion", 0.0), u_orig, unidad_destino, es_delta=True)
                p_uexp = cls.convertir_valor(p.get("u_expandida", 0.0), u_orig, unidad_destino, es_delta=True)
                puntos_convertidos.append({
                    "temp_indicada": p_ind,
                    "temp_patron": p_pat,
                    "correccion": p_corr,
                    "u_expandida": p_uexp,
                    "factor_k": p.get("factor_k", 2.0)
                })
            puntos_calibracion = puntos_convertidos

        mod_clean = str(modulo).lower()
        es_compresion = ("compresion" in mod_clean)
        es_asentamiento = ("asentamiento" in mod_clean or "slump" in mod_clean)

        # Variables por defecto para módulos no-compresión
        d_medido = float(diametro_mm)
        std_d = 0.0
        n_d = 1
        u_cal_vernier_mm = 0.0
        u_res_vernier_mm = 0.0
        u_deriva_vernier_mm = 0.0
        u_d_comb_mm = 0.0

        L_medido = float(longitud_mm)
        std_L = 0.0
        n_L = 1
        u_L_comb_mm = 0.0
        coef_cL = 0.0

        if es_compresion:
            unit_symbol = "psi" if "PSI" in str(unidad).upper() else "MPa"
        elif es_asentamiento:
            unit_symbol = "in" if "IN" in str(unidad).upper() else "mm"
        else:
            unit_symbol = "°F" if "F" in str(unidad).upper() else "°C"

        lecturas = np.array(lecturas_concreto, dtype=float)
        n = len(lecturas)
        temp_media = float(np.mean(lecturas))

        # 1. Corrección de Calibración
        if unit_symbol == "°F":
            temp_media_C = (temp_media - 32.0) * 5.0 / 9.0
            corr_cal_C, u_cal_C, k_cal_cert = cls.interpolar_calibracion(puntos_calibracion, temp_media_C)
            corr_cal = corr_cal_C * 1.8
            u_cal = u_cal_C * 1.8
            temp_corregida = temp_media + corr_cal
        elif unit_symbol == "in":
            temp_media_mm = temp_media * 25.4
            corr_cal_mm, u_cal_mm, k_cal_cert = cls.interpolar_calibracion(puntos_calibracion, temp_media_mm)
            corr_cal = corr_cal_mm / 25.4
            u_cal = u_cal_mm / 25.4
            temp_corregida = temp_media + corr_cal
        elif es_compresion:
            # lecturas están en kN (carga de rotura)
            corr_cal_kN, u_cal_kN, k_cal_cert = cls.interpolar_calibracion(puntos_calibracion, temp_media)
            corr_cal = corr_cal_kN
            u_cal = u_cal_kN

            # Procesamiento del diámetro d con Vernier / Pie de Rey
            if lecturas_diametro and len(lecturas_diametro) > 0:
                arr_d = np.array(lecturas_diametro, dtype=float)
                d_medido = float(np.mean(arr_d))
                std_d = float(np.std(arr_d, ddof=1)) if len(arr_d) > 1 else 0.02
                n_d = len(arr_d)
            else:
                d_medido = max(diametro_mm, 10.0)
                std_d = 0.02
                n_d = 1

            # Procesamiento de la longitud L con Vernier / Pie de Rey
            if lecturas_longitud and len(lecturas_longitud) > 0:
                arr_L = np.array(lecturas_longitud, dtype=float)
                L_medido = float(np.mean(arr_L))
                std_L = float(np.std(arr_L, ddof=1)) if len(arr_L) > 1 else 0.05
                n_L = len(arr_L)
            else:
                L_medido = max(longitud_mm, 10.0)
                std_L = 0.05
                n_L = 1

            # Corrección por calibración del Vernier
            corr_vernier_mm, u_cal_vernier_mm, k_cal_vernier = cls.interpolar_calibracion(puntos_calibracion_vernier or [], d_medido)
            corr_vernier_L_mm, u_cal_vernier_L_mm, _ = cls.interpolar_calibracion(puntos_calibracion_vernier or [], L_medido)

            d_real = d_medido + corr_vernier_mm
            L_real = L_medido + corr_vernier_L_mm
            area_mm2 = (np.pi * (d_real**2)) / 4.0

            # Esfuerzo bruto fc_raw = (P_kN * 1000 N) / area_mm2  [MPa]
            carga_corregida_kN = temp_media + corr_cal_kN
            fc_raw_MPa = (carga_corregida_kN * 1000.0) / area_mm2

            # Factor de corrección L/D (ASTM C39 Tabla 1)
            ratio_LD = L_real / d_real
            df_ld_dratio = 0.0
            if ratio_LD >= 1.75:
                f_ld = 1.00
                df_ld_dratio = 0.0
            elif ratio_LD >= 1.50:
                f_ld = 0.96 + (ratio_LD - 1.50) * (1.00 - 0.96) / 0.25
                df_ld_dratio = 0.16
            elif ratio_LD >= 1.25:
                f_ld = 0.93 + (ratio_LD - 1.25) * (0.96 - 0.93) / 0.25
                df_ld_dratio = 0.12
            else:
                f_ld = 0.87 + (ratio_LD - 1.00) * (0.93 - 0.87) / 0.25
                df_ld_dratio = 0.24

            fc_final_MPa = fc_raw_MPa * f_ld

            # Coeficientes de sensibilidad
            coef_cP = (1000.0 * f_ld) / area_mm2
            coef_cd = (2.0 * fc_final_MPa) / d_real
            coef_cL = (fc_raw_MPa * df_ld_dratio) / d_real if ratio_LD < 1.75 else 0.0001

            if unit_symbol == "psi":
                conv_factor = 145.03773778
                temp_corregida = fc_final_MPa * conv_factor
                coef_cP *= conv_factor
                coef_cd *= conv_factor
            else:
                temp_corregida = fc_final_MPa
        else:
            corr_cal, u_cal, k_cal_cert = cls.interpolar_calibracion(puntos_calibracion, temp_media)
            temp_corregida = temp_media + corr_cal

        # 2. Fuentes de Incertidumbre
        fuentes = []

        if es_compresion:
            nombre_f1 = "Repetibilidad en la carga de rotura (Prensa)"
            nombre_f2 = "Certificado de Calibración de la Prensa de Compresión"
            nombre_f3 = "Resolución de la Prensa Hidráulica"
            nombre_f4 = "Incertidumbre Combinada de la Medición del Diámetro (Vernier)"
            nombre_f5 = "Deriva instrumental de la Prensa"

            # Fuente 1: Repetibilidad Carga (Tipo A)
            std_muestral = float(np.std(lecturas, ddof=1)) if n > 1 else 2.0
            u_rep_kN = std_muestral / np.sqrt(n) if n > 1 else 2.0
            nu_rep = n - 1 if n > 1 else 50
            u_rep_y = coef_cP * u_rep_kN

            fuentes.append({
                "fuente": nombre_f1,
                "simbolo": "u_rep",
                "tipo": "A",
                "valor_xi": std_muestral,
                "distribucion": "Normal",
                "divisor": np.sqrt(n) if n > 1 else 1.0,
                "u_std": u_rep_kN,
                "coef_sensibilidad": coef_cP,
                "u_i_y": u_rep_y,
                "grados_libertad": nu_rep
            })

            # Fuente 2: Calibración Prensa (Tipo B)
            u_cal_y = coef_cP * u_cal
            fuentes.append({
                "fuente": nombre_f2,
                "simbolo": "u_cal",
                "tipo": "B",
                "valor_xi": u_cal * k_cal_cert,
                "distribucion": "Normal",
                "divisor": k_cal_cert,
                "u_std": u_cal,
                "coef_sensibilidad": coef_cP,
                "u_i_y": u_cal_y,
                "grados_libertad": 1000
            })

            # Fuente 3: Resolución Prensa (Tipo B)
            u_res_kN = (resolucion / 2.0) / np.sqrt(3)
            u_res_y = coef_cP * u_res_kN
            fuentes.append({
                "fuente": nombre_f3,
                "simbolo": "u_res",
                "tipo": "B",
                "valor_xi": resolucion,
                "distribucion": "Rectangular",
                "divisor": np.sqrt(12),
                "u_std": u_res_kN,
                "coef_sensibilidad": coef_cP,
                "u_i_y": u_res_y,
                "grados_libertad": 1000
            })

            # Fuente 4: Incertidumbre Combinada del Diámetro (Vernier Calibración + Resolución + Repetibilidad)
            u_rep_d_mm = std_d / np.sqrt(n_d) if n_d > 1 else 0.01
            u_res_vernier_mm = (resolucion_vernier / 2.0) / np.sqrt(3)
            u_deriva_vernier_mm = deriva_vernier / np.sqrt(3)

            u_d_comb_mm = float(np.sqrt(u_rep_d_mm**2 + u_cal_vernier_mm**2 + u_res_vernier_mm**2 + u_deriva_vernier_mm**2))
            u_d_y = coef_cd * u_d_comb_mm

            fuentes.append({
                "fuente": nombre_f4,
                "simbolo": "u_d",
                "tipo": "B",
                "valor_xi": u_d_comb_mm,
                "distribucion": "Normal/Rectangular",
                "divisor": 1.0,
                "u_std": u_d_comb_mm,
                "coef_sensibilidad": coef_cd,
                "u_i_y": u_d_y,
                "grados_libertad": 1000
            })

            # Fuente 5: Incertidumbre Combinada de la Longitud / Altura (Vernier)
            u_rep_L_mm = std_L / np.sqrt(n_L) if n_L > 1 else 0.01
            u_res_vernier_L_mm = (resolucion_vernier / 2.0) / np.sqrt(3)
            u_deriva_vernier_L_mm = deriva_vernier / np.sqrt(3)
            u_L_comb_mm = float(np.sqrt(u_rep_L_mm**2 + u_cal_vernier_L_mm**2 + u_res_vernier_L_mm**2 + u_deriva_vernier_L_mm**2))
            u_L_y = coef_cL * u_L_comb_mm

            fuentes.append({
                "fuente": "Incertidumbre Combinada de la Longitud / Altura (Vernier)",
                "simbolo": "u_L",
                "tipo": "B",
                "valor_xi": u_L_comb_mm,
                "distribucion": "Normal/Rectangular",
                "divisor": 1.0,
                "u_std": u_L_comb_mm,
                "coef_sensibilidad": coef_cL,
                "u_i_y": u_L_y,
                "grados_libertad": 1000
            })

            # Fuente 6: Deriva (Tipo B)
            u_deriva_kN = deriva_estimada / np.sqrt(3)
            u_deriva_y = coef_cP * u_deriva_kN
            fuentes.append({
                "fuente": nombre_f5,
                "simbolo": "u_deriva",
                "tipo": "B",
                "valor_xi": deriva_estimada,
                "distribucion": "Rectangular",
                "divisor": np.sqrt(3),
                "u_std": u_deriva_kN,
                "coef_sensibilidad": coef_cP,
                "u_i_y": u_deriva_y,
                "grados_libertad": 1000
            })

            # Sincronizar variables internas
            u_rep = u_rep_y
            u_res = u_res_y
            u_deriva = u_deriva_y
            u_cal = u_cal_y

        else:
            # Nombres según módulo (Temperatura o Asentamiento)
            nombre_f1 = "Asentamiento en concreto fresco" if es_asentamiento else "Temperatura en concreto fresco"
            nombre_f2 = "Certificado de Calibración de la Regla" if es_asentamiento else "Certificado de Calibración"
            nombre_f3 = "Resolución de la Regla Graduada" if es_asentamiento else "Resolución del termómetro"
            nombre_f4 = "Deriva instrumental de la Regla" if es_asentamiento else "Deriva instrumental"

            # Fuente 1: Repetibilidad (Tipo A)
            if n > 1:
                std_muestral = float(np.std(lecturas, ddof=1))
                u_rep = std_muestral / np.sqrt(n)
                nu_rep = n - 1
            else:
                std_muestral = 0.5 if es_asentamiento else (0.05 if unit_symbol == "°C" else 0.09)
                u_rep = std_muestral
                nu_rep = 50

            fuentes.append({
                "fuente": nombre_f1,
                "simbolo": "u_rep",
                "tipo": "A",
                "valor_xi": std_muestral,
                "distribucion": "Normal",
                "divisor": np.sqrt(n) if n > 1 else 1.0,
                "u_std": u_rep,
                "coef_sensibilidad": 1.0,
                "u_i_y": u_rep,
                "grados_libertad": nu_rep
            })

            # Fuente 2: Calibración (Tipo B)
            fuentes.append({
                "fuente": nombre_f2,
                "simbolo": "u_cal",
                "tipo": "B",
                "valor_xi": u_cal * k_cal_cert,
                "distribucion": "Normal",
                "divisor": k_cal_cert,
                "u_std": u_cal,
                "coef_sensibilidad": 1.0,
                "u_i_y": u_cal,
                "grados_libertad": 1000
            })

            # Fuente 3: Resolución (Tipo B)
            u_res = (resolucion / 2.0) / np.sqrt(3)
            fuentes.append({
                "fuente": nombre_f3,
                "simbolo": "u_res",
                "tipo": "B",
                "valor_xi": resolucion,
                "distribucion": "Rectangular",
                "divisor": np.sqrt(12),
                "u_std": u_res,
                "coef_sensibilidad": 1.0,
                "u_i_y": u_res,
                "grados_libertad": 1000
            })

            # Fuente 4: Deriva (Tipo B) - Solo si es estrictamente mayor que cero
            u_deriva = 0.0
            if deriva_estimada > 0:
                u_deriva = deriva_estimada / np.sqrt(3)
                fuentes.append({
                    "fuente": nombre_f4,
                    "simbolo": "u_deriva",
                    "tipo": "B",
                    "valor_xi": deriva_estimada,
                    "distribucion": "Rectangular",
                    "divisor": np.sqrt(3),
                    "u_std": u_deriva,
                    "coef_sensibilidad": 1.0,
                    "u_i_y": u_deriva,
                    "grados_libertad": 1000
                })

        # 3. Incertidumbre Estándar Combinada u_c
        varianzas = np.array([f["u_i_y"]**2 for f in fuentes])
        u_c = float(np.sqrt(np.sum(varianzas)))

        # 4. Porcentajes de Contribución a la Varianza Combinada (%)
        for f in fuentes:
            f["varianza_i"] = f["u_i_y"]**2
            f["contribucion_pct"] = (f["varianza_i"] / (u_c**2)) * 100.0 if u_c > 0 else 0.0
            # Mapear claves en espanol y estandar para JS y DataFrames
            f["Fuente de Incertidumbre"] = f["fuente"]
            f["Tipo"] = f["tipo"]
            f["Distribución"] = f["distribucion"]
            f["Valor Semi-intervalo"] = f["valor_xi"]
            f["Divisor"] = f["divisor"]
            f[f"Incertidumbre u_i ({unit_symbol})"] = f["u_std"]
            f["u(xi) Estándar"] = f["u_std"]
            f["Coef. Sens. c_i"] = f["coef_sensibilidad"]
            f["Coef. Sensibilidad ci"] = f["coef_sensibilidad"]
            f[f"u_i(y) ({unit_symbol})"] = f["u_i_y"]
            f["ui(y) Contribución"] = f["u_i_y"]
            f["Contribución (%)"] = f["contribucion_pct"]

        # 5. Grados de Libertad Efectivos (Welch-Satterthwaite)
        denom_ws = np.sum([f["u_i_y"]**4 / f["grados_libertad"] for f in fuentes])
        nu_eff = (u_c**4) / denom_ws if denom_ws > 0 else 100.0
        nu_eff = float(np.floor(nu_eff)) if np.isfinite(nu_eff) else 100.0

        # 6. Factor de Cobertura k
        if nu_eff >= 100:
            k_factor = 2.00 if nivel_confianza >= 0.95 else 1.96
        else:
            p_val = (1.0 + nivel_confianza) / 2.0
            k_factor = float(t.ppf(p_val, df=max(nu_eff, 1)))

        # 7. Incertidumbre Expandida U
        U_expandida = k_factor * u_c

        # Construcción de lista de diccionarios sanitizados para API
        tabla_presupuesto_sanitizada = []
        for f in fuentes:
            d_item = dict(f)
            tabla_presupuesto_sanitizada.append(d_item)


        return {
            "lecturas_originales": lecturas_concreto,
            "num_lecturas": n,
            "temp_media_indicada": temp_media,
            "std_muestral": std_muestral,
            "u_rep": u_rep,
            "u_cal": u_cal,
            "u_res": u_res,
            "u_deriva": u_deriva,
            "correccion_aplicada": corr_cal,
            "temp_estimada_final": temp_corregida,
            "u_combinada": u_c,
            "varianza_combinada": u_c**2,
            "grados_libertad_efectivos": nu_eff,
            "factor_k": k_factor,
            "nivel_confianza_pct": nivel_confianza * 100.0,
            "incertidumbre_expandida_U": U_expandida,
            "fuentes": fuentes,
            "tabla_presupuesto": tabla_presupuesto_sanitizada,
            "unidad": unit_symbol,

            "detalles_calculo": {
                "n": n,
                "temp_media": temp_media,
                "std_muestral": std_muestral,
                "u_rep": u_rep,
                "nu_rep": nu_rep,
                "u_cal": u_cal,
                "k_cal": k_cal_cert,
                "resolucion": resolucion,
                "u_res": u_res,
                "deriva": deriva_estimada,
                "u_deriva": u_deriva,
                "u_c_sq": u_c**2,
                "u_c": u_c,
                "denom_ws": denom_ws,
                "nu_eff": nu_eff,
                "k": k_factor,
                "U": U_expandida,
                "temp_final": temp_corregida,
                "unidad": unit_symbol,
                "lecturas_diametro": lecturas_diametro or [d_medido],
                "n_d": n_d,
                "d_medido": d_medido,
                "std_d": std_d,
                "u_rep_d": std_d / np.sqrt(n_d) if n_d > 1 else 0.01,
                "u_cal_vernier": u_cal_vernier_mm,
                "u_res_vernier": u_res_vernier_mm,
                "u_deriva_vernier": u_deriva_vernier_mm,
                "u_d_comb": u_d_comb_mm,
                "lecturas_longitud": lecturas_longitud or [L_medido],
                "n_L": n_L,
                "L_medido": L_medido,
                "std_L": std_L,
                "u_rep_L": std_L / np.sqrt(n_L) if n_L > 1 else 0.01,
                "u_L_comb": u_L_comb_mm,
                "coef_cL": coef_cL
            }
        }

if __name__ == "__main__":
    puntos_demo = [
        {"temp_indicada": 0.0, "correccion": 0.02, "u_expandida": 0.04, "factor_k": 2.0},
        {"temp_indicada": 25.0, "correccion": 0.04, "u_expandida": 0.05, "factor_k": 2.0},
        {"temp_indicada": 50.0, "correccion": 0.08, "u_expandida": 0.06, "factor_k": 2.0},
    ]
    res = GUMCalculator.evaluar_incertidumbre(
        lecturas_concreto=[24.5, 24.6, 24.5, 24.7, 24.5],
        resolucion=0.1,
        puntos_calibracion=puntos_demo,
        deriva_estimada=0.05,
        homogeneidad_concreto=0.10
    )
    print("--- RESULTADOS METROLÓGICOS GUM ---")
    print(f"Temperatura Estimada Final: {res['temp_estimada_final']:.3f} °C")
    print(f"Incertidumbre Estándar Combinada u_c: {res['u_combinada']:.4f} °C")
    print(f"Factor de Cobertura k ({res['nivel_confianza_pct']:.2f}%): {res['factor_k']:.3f}")
    print(f"Incertidumbre Expandida U: {res['incertidumbre_expandida_U']:.4f} °C")
    print("\nTabla de Presupuesto de Incertidumbre:")
    print(res['tabla_presupuesto'].to_string(index=False))
