"""
Motor de Cálculo Geotécnico Rigurosamente Alineado con ASTM D6913 / D6913M - 17 (Reaprobada 2025)
Formato Oficial HC-LSMCH-006 (Universidad Tecnológica de Panamá - LSMCH)
Soporte de Tamizado Compuesto y Reducción de Fracción Fina
"""

import math

TAMICES_ASTM_D6913 = [
    {"tamiz": '3"', "apertura_mm": 75.000, "es_gruesa": True},
    {"tamiz": '2"', "apertura_mm": 50.000, "es_gruesa": True},
    {"tamiz": '1 1/2"', "apertura_mm": 38.100, "es_gruesa": True},
    {"tamiz": '1"', "apertura_mm": 25.000, "es_gruesa": True},
    {"tamiz": '3/4"', "apertura_mm": 19.000, "es_gruesa": True},
    {"tamiz": '3/8"', "apertura_mm": 9.500, "es_gruesa": True},
    {"tamiz": 'No. 4', "apertura_mm": 4.750, "es_gruesa": True},
    {"tamiz": 'No. 10', "apertura_mm": 2.000, "es_gruesa": False},
    {"tamiz": 'No. 20', "apertura_mm": 0.850, "es_gruesa": False},
    {"tamiz": 'No. 40', "apertura_mm": 0.425, "es_gruesa": False},
    {"tamiz": 'No. 60', "apertura_mm": 0.250, "es_gruesa": False},
    {"tamiz": 'No. 100', "apertura_mm": 0.150, "es_gruesa": False},
    {"tamiz": 'No. 140', "apertura_mm": 0.105, "es_gruesa": False},
    {"tamiz": 'No. 200', "apertura_mm": 0.075, "es_gruesa": False},
    {"tamiz": 'Fondo', "apertura_mm": 0.000, "es_gruesa": False}
]

def calcular_granulometria_astm_d6913(datos):
    """
    Cálculo oficial ASTM D6913 / HC-LSMCH-006 con Tamizado Compuesto y Reducción de Fracción Fina.
    """
    metodo = datos.get("metodo_ensayo", "METODO_A")
    procedimiento = datos.get("procedimiento", "HUMEDO")
    
    s_md = float(datos.get("masa_total_seca_g", 1246.3)) # Masa total seca espécimen
    m_humeda_total = float(datos.get("masa_total_humeda_g", 1942.7))
    m_humeda_ffina_total = float(datos.get("masa_total_humeda_ffina_g", 1821.3))

    m_hum_fgruesa = float(datos.get("m_hum_fgruesa", 121.4))
    m_hum_ffina = float(datos.get("m_hum_ffina", 132.5))
    
    m_seca_fgruesa_user = float(datos.get("m_seca_fgruesa", 77.9))
    m_seca_ffina_user = float(datos.get("m_seca_ffina", 84.6))
    m_lavada_fgruesa_user = float(datos.get("m_lavada_fgruesa", 77.9))
    m_lavada_ffina_user = float(datos.get("m_lavada_ffina", 84.6))

    tamices_input = datos.get("tamices", [])
    
    # 1. Factores de tamizado unrounded (CSCF)
    factor_gruesa = (100.0 / s_md) if s_md > 0 else 0.0
    
    item_no4 = next((x for x in tamices_input if x.get("tamiz") == 'No. 4'), {})
    m_ret_gruesa_no4 = m_seca_fgruesa_user
    
    pct_ret_no4_raw = m_ret_gruesa_no4 * factor_gruesa
    pct_pasa_no4_raw = 100.0 - pct_ret_no4_raw

    # Masa de subespécimen fino lavado
    m_fina_total = sum(float(x.get("ffina_g", x.get("masa_retenida", 0.0))) for x in tamices_input if x.get("tamiz") != 'Fondo' and not next((t["es_gruesa"] for t in TAMICES_ASTM_D6913 if t["tamiz"] == x.get("tamiz")), True))
    m_fina_fondo = float(next((x.get("ffina_g", x.get("masa_retenida", 10.34)) for x in tamices_input if x.get("tamiz") == 'Fondo'), 10.34))
    sub_s_md = m_seca_ffina_user # Masa seca subespécimen fino ingresada por el usuario (e.g. 84.6g)

    # Factor Fracción Fina CSCF = pct_pasa_no4_raw / sub_s_md
    factor_fina = (pct_pasa_no4_raw / sub_s_md) if sub_s_md > 0 else factor_gruesa


    # 2. Procesar tamizado conservando precisión flotante
    resultado_tamices = []
    cmr_acumulada_raw = 0.0
    suma_masas_retenidas = 0.0

    for t_def in TAMICES_ASTM_D6913:
        nombre = t_def["tamiz"]
        apertura = t_def["apertura_mm"]
        es_gruesa = t_def["es_gruesa"]
        
        item_in = next((x for x in tamices_input if x.get("tamiz") == nombre), {})
        m_ret_fgruesa = float(item_in.get("fgruesa_g", 0.0))
        m_ret_ffina = float(item_in.get("ffina_g", item_in.get("masa_retenida", 0.0)))
        
        if nombre == 'No. 4':
            m_ret_fgruesa = m_ret_gruesa_no4
            
        if es_gruesa and nombre != 'No. 4':
            m_ret_ffina = 0.0
            
        if es_gruesa:
            pct_ret_ind_raw = m_ret_fgruesa * factor_gruesa
            factor_usado = factor_gruesa
        else:
            pct_ret_ind_raw = m_ret_ffina * factor_fina
            factor_usado = factor_fina
            
        if nombre != 'Fondo':
            suma_masas_retenidas += (m_ret_fgruesa + m_ret_ffina)
            cmr_acumulada_raw += pct_ret_ind_raw

        pct_pasa_raw = 100.0 - cmr_acumulada_raw
        if pct_pasa_raw < 0: pct_pasa_raw = 0.0
        pct_pasa_final = round(pct_pasa_raw) if metodo == "METODO_A" else round(pct_pasa_raw, 1)

        if nombre == 'Fondo':
            resultado_tamices.append({
                "tamiz": nombre,
                "apertura_mm": apertura,
                "fgruesa_g": round(m_ret_fgruesa, 2),
                "ffina_g": round(m_ret_ffina, 2),
                "factor_tamizado": "",
                "pct_retenido_ind": "--",
                "pct_acumulado_ret": "--",
                "pct_pasa": "--",
                "pct_pasa_raw": 0.0
            })
        else:
            resultado_tamices.append({
                "tamiz": nombre,
                "apertura_mm": apertura,
                "fgruesa_g": round(m_ret_fgruesa, 2),
                "ffina_g": round(m_ret_ffina, 2),
                "factor_tamizado": round(factor_usado, 7),
                "pct_retenido_ind": round(pct_ret_ind_raw, 2),
                "pct_acumulado_ret": round(cmr_acumulada_raw, 1),
                "pct_pasa": pct_pasa_final,
                "pct_pasa_raw": round(pct_pasa_raw, 2)
            })

    # Pérdida aceptable por lavado (CP_L) <= 0.5%
    cp_l = ((s_md - (suma_masas_retenidas + m_fina_fondo)) / s_md) * 100.0 if s_md > 0 else 0.0
    cp_l_aceptable = (abs(cp_l) <= 0.5)

    # Parámetros de Reducción y Tamizado Compuesto
    h_total_pct = round(((m_humeda_total - s_md) / s_md) * 100.0, 1) if s_md > 0 else 0.0
    h_fgruesa_pct = round(((m_hum_fgruesa - m_ret_gruesa_no4) / m_ret_gruesa_no4) * 100.0, 1) if m_ret_gruesa_no4 > 0 else 0.0
    h_ffina_pct = round(((m_hum_ffina - sub_s_md) / sub_s_md) * 100.0, 1) if sub_s_md > 0 else 0.0

    pct_fraccion_gruesa = round(pct_ret_no4_raw, 1)
    pct_fraccion_fina = round(pct_pasa_no4_raw, 1)

    sum_tamizado_gruesa = round(m_ret_gruesa_no4, 1)
    sum_tamizado_fina = round(sub_s_md - m_fina_fondo, 1)

    # Diámetros característicos D10, D15, D30, D50, D60, D85
    def interpolar_d_exacto(pct_objetivo):
        for i in range(len(resultado_tamices) - 1):
            p1 = resultado_tamices[i]["pct_pasa_raw"]
            p2 = resultado_tamices[i+1]["pct_pasa_raw"]
            d1 = resultado_tamices[i]["apertura_mm"]
            d2 = resultado_tamices[i+1]["apertura_mm"]
            
            if (p1 >= pct_objetivo >= p2) and d1 > 0 and d2 > 0 and p1 != p2:
                log_d1 = math.log10(d1)
                log_d2 = math.log10(d2)
                log_d = log_d1 + (pct_objetivo - p1) * (log_d2 - log_d1) / (p2 - p1)
                return round(10**log_d, 2)
        return None

    d10 = interpolar_d_exacto(10.0)
    d15 = interpolar_d_exacto(15.0)
    d30 = interpolar_d_exacto(30.0)
    d50 = interpolar_d_exacto(50.0)
    d60 = interpolar_d_exacto(60.0)
    d85 = interpolar_d_exacto(85.0)

    cu = round(d60 / d10, 2) if (d60 and d10 and d10 > 0) else None
    cc = round((d30**2) / (d60 * d10), 2) if (d30 and d60 and d10 and (d60 * d10) > 0) else None

    pasa_no4_raw = next((t["pct_pasa_raw"] for t in resultado_tamices if t["tamiz"] == 'No. 4'), 93.75)
    pasa_no200_raw = next((t["pct_pasa_raw"] for t in resultado_tamices if t["tamiz"] == 'No. 200'), 11.73)

    pct_grava = round(100.0 - pasa_no4_raw, 2)
    pct_arena = round(pasa_no4_raw - pasa_no200_raw, 2)
    pct_finos = round(pasa_no200_raw, 2)

    return {
        "formato": "HC-LSMCH-006",
        "norma": "ASTM D6913 / D6913M - 17 (2025)",
        "metodo_ensayo": metodo,
        "procedimiento": procedimiento,
        "tamizado_compuesto": {
            "m_humeda_total": m_humeda_total,
            "s_md": s_md,
            "m_humeda_ffina_total": m_humeda_ffina_total,
            "m_hum_fgruesa": m_hum_fgruesa,
            "m_hum_ffina": m_hum_ffina,
            "m_seca_fgruesa": m_ret_gruesa_no4,
            "sub_s_md": sub_s_md,
            "h_total_pct": h_total_pct,
            "h_fgruesa_pct": h_fgruesa_pct,
            "h_ffina_pct": h_ffina_pct,
            "pct_fraccion_gruesa": pct_fraccion_gruesa,
            "pct_fraccion_fina": pct_fraccion_fina,
            "sum_tamizado_gruesa": sum_tamizado_gruesa,
            "sum_tamizado_fina": sum_tamizado_fina
        },
        "factor_gruesa": round(factor_gruesa, 7),
        "factor_fina": round(factor_fina, 7),
        "tamices": resultado_tamices,
        "cp_l_pct": round(cp_l, 2),
        "cp_l_aceptable": cp_l_aceptable,
        "criterio_norma": "Cumple (CP_L <= 0.5%)" if cp_l_aceptable else "No Cumple (CP_L > 0.5%)",
        "d10": d10,
        "d15": d15,
        "d30": d30,
        "d50": d50,
        "d60": d60,
        "d85": d85,
        "cu": cu,
        "cc": cc,
        "pct_grava": pct_grava,
        "pct_arena": pct_arena,
        "pct_finos": pct_finos
    }

def calcular_granulometria(datos_tamices):
    if isinstance(datos_tamices, dict):
        return calcular_granulometria_astm_d6913(datos_tamices)
    return calcular_granulometria_astm_d6913({"tamices": datos_tamices})
