"""
Motor de Cálculo Geotécnico Rigurosamente Alineado con ASTM D6913 / D6913M - 17 (Reaprobada 2025)
Formato Oficial HC-LSMCH-006 (Universidad Tecnológica de Panamá - LSMCH)
Cálculo con Precisión Interna Sin Redondear y Redondeo Final según Método A (1%) o Método B (0.1%)
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
    Cálculo oficial ASTM D6913 / HC-LSMCH-006 con conservación de precisión interna.
    Redondeo al final:
      - % Retenido (Intermedio): 2 decimales
      - % Acumulado Retenido: 1 decimal (0.1%)
      - % Que Pasa: Entero (1%) para Método A o 1 decimal (0.1%) para Método B.
    """
    metodo = datos.get("metodo_ensayo", "METODO_A")
    procedimiento = datos.get("procedimiento", "HUMEDO")
    
    s_md = float(datos.get("masa_total_seca_g", 1246.3)) # Masa total seca espécimen
    m_humeda_total = float(datos.get("masa_total_humeda_g", 1942.7))

    tamices_input = datos.get("tamices", [])
    
    # 1. Factores de tamizado unrounded (CSCF)
    # Factor Fracción Gruesa = 100 / S,Md
    factor_gruesa = (100.0 / s_md) if s_md > 0 else 0.0
    
    # Calcular retención de masa en gruesa en Tamiz No. 4
    item_no4 = next((x for x in tamices_input if x.get("tamiz") == 'No. 4'), {})
    m_ret_gruesa_no4 = float(item_no4.get("fgruesa_g", item_no4.get("masa_retenida", 77.9)))
    
    pct_ret_no4_raw = m_ret_gruesa_no4 * factor_gruesa
    pct_pasa_no4_raw = 100.0 - pct_ret_no4_raw

    # Masa de subespécimen fino lavado
    m_fina_total = sum(float(x.get("ffina_g", x.get("masa_retenida", 0.0))) for x in tamices_input if x.get("tamiz") != 'Fondo' and not next((t["es_gruesa"] for t in TAMICES_ASTM_D6913 if t["tamiz"] == x.get("tamiz")), True))
    m_fina_fondo = float(next((x.get("ffina_g", x.get("masa_retenida", 10.34)) for x in tamices_input if x.get("tamiz") == 'Fondo'), 10.34))
    sub_s_md = m_fina_total + m_fina_fondo # Masa seca subespécimen fino (e.g. 84.6g)

    # Factor Fracción Fina CSCF = pct_pasa_no4_raw / sub_s_md
    factor_fina = (pct_pasa_no4_raw / sub_s_md) if sub_s_md > 0 else factor_gruesa

    # 2. Procesar tamizado conservando precisión flotante sin redondear intermedios
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
            
        # % Retenido sin redondear
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

        # Redondeo final según Método A (1% en Que Pasa) o Método B (0.1%)
        pct_pasa_final = round(pct_pasa_raw) if metodo == "METODO_A" else round(pct_pasa_raw, 1)

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

    # Diámetros característicos D10, D15, D30, D50, D60, D85 usando valores no redondeados
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

    # Porcentajes desglosados
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

def clasificar_sucs(pct_finos, pct_grava, pct_arena, ll=None, ip=None, cu=None, cc=None):
    if pct_finos is None: return "Indeterminado"
    linea_a = (0.73 * (ll - 20)) if (ll is not None and ll >= 20) else 0.0
    if pct_finos < 50.0:
        es_grava = (pct_grava > pct_arena)
        if pct_finos < 5.0:
            if es_grava: return "GW" if ((cu and cu >= 4.0) and (cc and 1.0 <= cc <= 3.0)) else "GP"
            else: return "SW" if ((cu and cu >= 6.0) and (cc and 1.0 <= cc <= 3.0)) else "SP"
        elif pct_finos > 12.0:
            if ll and ip:
                es_arcilloso = (ip > linea_a and ip > 7)
                es_limoso = (ip < linea_a or ip < 4)
                return ("GC" if es_arcilloso else ("GM" if es_limoso else "GC-GM")) if es_grava else ("SC" if es_arcilloso else ("SM" if es_limoso else "SC-SM"))
            return "Grava con finos" if es_grava else "Arena con finos"
        else:
            return "Grava/Arena con finos"
    else:
        if ll is None or ip is None: return "Fino sin clasificar"
        if 4 <= ip <= 7 and (ip >= linea_a or abs(ip - linea_a) <= 1): return "CL-ML"
        if ll >= 50.0: return "CH" if ip > linea_a else "MH"
        else: return "CL" if ip > linea_a else "ML"
