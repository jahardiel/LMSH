"""
Motor de Cálculo Geotécnico Rigurosamente Alineado con ASTM D6913 / D6913M - 17 (Reaprobada 2025)
Formato Oficial HC-LSMCH-006 (Universidad Tecnológica de Panamá - LSMCH)
"""

import math

# Conjunto Estándar de Tamices según ASTM D6913 Tabla 1 / E11
TAMICES_ASTM_D6913 = [
    {"tamiz": '3"', "apertura_mm": 75.000, "fraccion": "GRAVA_GRUASA"},
    {"tamiz": '2"', "apertura_mm": 50.000, "fraccion": "GRAVA_GRUASA"},
    {"tamiz": '1 1/2"', "apertura_mm": 37.500, "fraccion": "GRAVA_FINA"},
    {"tamiz": '1"', "apertura_mm": 25.000, "fraccion": "GRAVA_FINA"},
    {"tamiz": '3/4"', "apertura_mm": 19.000, "fraccion": "GRAVA_FINA"},
    {"tamiz": '3/8"', "apertura_mm": 9.500, "fraccion": "GRAVA_FINA"},
    {"tamiz": 'No. 4', "apertura_mm": 4.750, "fraccion": "GRAVA_FINA"},
    {"tamiz": 'No. 10', "apertura_mm": 2.000, "fraccion": "ARENA_GRUASA"},
    {"tamiz": 'No. 20', "apertura_mm": 0.850, "fraccion": "ARENA_MEDIA"},
    {"tamiz": 'No. 40', "apertura_mm": 0.425, "fraccion": "ARENA_MEDIA"},
    {"tamiz": 'No. 60', "apertura_mm": 0.250, "fraccion": "ARENA_FINA"},
    {"tamiz": 'No. 100', "apertura_mm": 0.150, "fraccion": "ARENA_FINA"},
    {"tamiz": 'No. 140', "apertura_mm": 0.106, "fraccion": "ARENA_FINA"},
    {"tamiz": 'No. 200', "apertura_mm": 0.075, "fraccion": "ARENA_FINA"},
    {"tamiz": 'Fondo', "apertura_mm": 0.000, "fraccion": "FINOS"}
]

def calcular_granulometria_astm_d6913(datos):
    """
    Cálculo riguroso según la norma ASTM D6913 / D6913M - 17 (2025) y Formato HC-LSMCH-006.
    
    Parámetros de datos:
      - metodo_ensayo: 'METODO_A' (1% precisión) o 'METODO_B' (0.1% precisión)
      - procedimiento: 'HUMEDO', 'SECADO_AIRE', 'SECADO_HORNO'
      - dispersante_usado: bool
      - masa_total_humeda_g: float
      - masa_total_seca_g: float (S,Md según ec. ASTM)
      - tamices: lista de dicts [{'tamiz': 'No. 4', 'masa_retenida': 77.9, ...}]
      - ll, lp: float
    """
    metodo = datos.get("metodo_ensayo", "METODO_A")
    procedimiento = datos.get("procedimiento", "HUMEDO")
    
    m_humeda_total = float(datos.get("masa_total_humeda_g", 1942.7))
    s_md = float(datos.get("masa_total_seca_g", 1246.3)) # S,Md: Masa seca del espécimen (g)
    
    # Tamices recibidos
    tamices_input = datos.get("tamices", [])
    
    resultado_tamices = []
    cmr_acumulada = 0.0
    suma_masas_retenidas = 0.0

    for t_def in TAMICES_ASTM_D6913:
        nombre = t_def["tamiz"]
        apertura = t_def["apertura_mm"]
        
        item_in = next((x for x in tamices_input if x.get("tamiz") == nombre), {})
        m_ret_ind = float(item_in.get("masa_retenida", item_in.get("ffina_g", 0.0)))
        
        if nombre != 'Fondo':
            suma_masas_retenidas += m_ret_ind
            
        cmr_acumulada += m_ret_ind
        
        # Ecuación 2 de ASTM D6913 Cl. 12.3: PPN = 100 * (1 - CMR_N / S,Md)
        if s_md > 0:
            pct_ret_ind = (m_ret_ind / s_md) * 100.0
            pct_acum_ret = (cmr_acumulada / s_md) * 100.0
            pct_pasa = 100.0 - pct_acum_ret
        else:
            pct_ret_ind = 0.0
            pct_acum_ret = 0.0
            pct_pasa = 100.0
            
        if pct_pasa < 0: pct_pasa = 0.0

        # Redondeo según Método A (1%) o Método B (0.1%) - Cl. 1.6 / 13.1
        dec = 1 if metodo == "METODO_B" else 2
        
        resultado_tamices.append({
            "tamiz": nombre,
            "apertura_mm": apertura,
            "masa_retenida": round(m_ret_ind, 2),
            "pct_retenido_ind": round(pct_ret_ind, dec),
            "pct_acumulado_ret": round(pct_acum_ret, dec),
            "pct_pasa": round(pct_pasa, dec)
        })

    # Pérdida aceptable por lavado y tamizado (CP_L) según Cl. 12.5.1.3 / Ec. 5:
    # CP_L = 100 * (S,Md - M_recuperada) / S,Md
    m_fondo = float(next((x.get("masa_retenida", 0.0) for x in tamices_input if x.get("tamiz") == 'Fondo'), 0.0))
    m_recuperada_total = suma_masas_retenidas + m_fondo
    cp_l = ((s_md - m_recuperada_total) / s_md) * 100.0 if s_md > 0 else 0.0
    cp_l_aceptable = (abs(cp_l) <= 0.5)

    # Interpolar diámetros característicos D10, D15, D30, D50, D60, D85 en escala semilog
    def interpolar_d(pct_objetivo):
        for i in range(len(resultado_tamices) - 1):
            p1 = resultado_tamices[i]["pct_pasa"]
            p2 = resultado_tamices[i+1]["pct_pasa"]
            d1 = resultado_tamices[i]["apertura_mm"]
            d2 = resultado_tamices[i+1]["apertura_mm"]
            
            if (p1 >= pct_objetivo >= p2) and d1 > 0 and d2 > 0 and p1 != p2:
                log_d1 = math.log10(d1)
                log_d2 = math.log10(d2)
                log_d = log_d1 + (pct_objetivo - p1) * (log_d2 - log_d1) / (p2 - p1)
                return round(10**log_d, 2)
        return None

    d10 = interpolar_d(10.0)
    d15 = interpolar_d(15.0)
    d30 = interpolar_d(30.0)
    d50 = interpolar_d(50.0)
    d60 = interpolar_d(60.0)
    d85 = interpolar_d(85.0)

    cu = round(d60 / d10, 2) if (d60 and d10 and d10 > 0) else None
    cc = round((d30**2) / (d60 * d10), 2) if (d30 and d60 and d10 and (d60 * d10) > 0) else None

    # Porcentajes por fracción granulométrica
    pasa_3in = 100.0
    pasa_no4 = 100.0
    pasa_no200 = 0.0
    
    for t in resultado_tamices:
        if t["tamiz"] == '3"': pasa_3in = t["pct_pasa"]
        elif t["tamiz"] == 'No. 4': pasa_no4 = t["pct_pasa"]
        elif t["tamiz"] == 'No. 200': pasa_no200 = t["pct_pasa"]

    pct_grava = round(100.0 - pasa_no4, 2)
    pct_arena = round(pasa_no4 - pasa_no200, 2)
    pct_finos = round(pasa_no200, 2)

    pct_grava_gruesa = round(100.0 - next((t["pct_pasa"] for t in resultado_tamices if t["tamiz"] == '3/4"'), 100.0), 2)
    pct_grava_fina = round(pct_grava - pct_grava_gruesa, 2)
    if pct_grava_fina < 0: pct_grava_fina = 0.0

    pasa_no10 = next((t["pct_pasa"] for t in resultado_tamices if t["tamiz"] == 'No. 10'), pasa_no4)
    pasa_no40 = next((t["pct_pasa"] for t in resultado_tamices if t["tamiz"] == 'No. 40'), pasa_no10)
    
    pct_arena_gruesa = round(pasa_no4 - pasa_no10, 2)
    pct_arena_media = round(pasa_no10 - pasa_no40, 2)
    pct_arena_fina = round(pasa_no40 - pasa_no200, 2)

    # Clasificación SUCS ASTM D2487
    ll = datos.get("ll")
    lp = datos.get("lp")
    ip = round(float(ll) - float(lp), 2) if (ll is not None and lp is not None) else None
    
    from geotechnics_engine import clasificar_sucs
    sucs = clasificar_sucs(pct_finos, pct_grava, pct_arena, ll=float(ll) if ll is not None else None, ip=ip, cu=cu, cc=cc)

    return {
        "formato": "HC-LSMCH-006",
        "norma": "ASTM D6913 / D6913M - 17 (2025)",
        "metodo_ensayo": metodo,
        "procedimiento": procedimiento,
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
        "pct_grava_gruesa": pct_grava_gruesa,
        "pct_grava_fina": pct_grava_fina,
        "pct_arena": pct_arena,
        "pct_arena_gruesa": pct_arena_gruesa,
        "pct_arena_media": pct_arena_media,
        "pct_arena_fina": pct_arena_fina,
        "pct_finos": pct_finos,
        "clasificacion_sucs": sucs,
        "ll": ll,
        "lp": lp,
        "ip": ip
    }

def calcular_granulometria(datos_tamices):
    """Función wrapper de compatibilidad."""
    if isinstance(datos_tamices, dict):
        return calcular_granulometria_astm_d6913(datos_tamices)
    return calcular_granulometria_astm_d6913({"tamices": datos_tamices})

def clasificar_sucs(pct_finos, pct_grava, pct_arena, ll=None, ip=None, cu=None, cc=None):
    if pct_finos is None:
        return "Indeterminado"

    linea_a = (0.73 * (ll - 20)) if (ll is not None and ll >= 20) else 0.0

    if pct_finos < 50.0:
        es_grava = (pct_grava > pct_arena)
        if pct_finos < 5.0:
            if es_grava:
                return "GW (Grava bien graduada)" if ((cu and cu >= 4.0) and (cc and 1.0 <= cc <= 3.0)) else "GP (Grava mal graduada)"
            else:
                return "SW (Arena bien graduada)" if ((cu and cu >= 6.0) and (cc and 1.0 <= cc <= 3.0)) else "SP (Arena mal graduada)"
        elif pct_finos > 12.0:
            if ll is not None and ip is not None:
                es_arcilloso = (ip > linea_a and ip > 7)
                es_limoso = (ip < linea_a or ip < 4)
                if es_grava:
                    return "GC (Grava arcillosa)" if es_arcilloso else ("GM (Grava limosa)" if es_limoso else "GC-GM")
                else:
                    return "SC (Arena arcillosa)" if es_arcilloso else ("SM (Arena limosa)" if es_limoso else "SC-SM")
            return "Grava con finos" if es_grava else "Arena con finos"
        else:
            es_bien_grad = False
            if es_grava and (cu and cu >= 4.0) and (cc and 1.0 <= cc <= 3.0): es_bien_grad = True
            elif not es_grava and (cu and cu >= 6.0) and (cc and 1.0 <= cc <= 3.0): es_bien_grad = True
            if ll is not None and ip is not None:
                es_arcilloso = (ip > linea_a and ip > 7)
                return f"{'GW' if es_bien_grad else 'GP'}-{'GC' if es_arcilloso else 'GM'}" if es_grava else f"{'SW' if es_bien_grad else 'SP'}-{'SC' if es_arcilloso else 'SM'}"
            return "Grava/Arena con finos (Doble símbolo)"
    else:
        if ll is None or ip is None: return "Fino sin clasificar"
        if 4 <= ip <= 7 and (ip >= linea_a or abs(ip - linea_a) <= 1): return "CL-ML"
        if ll >= 50.0: return "CH (Arcilla de alta plasticidad)" if ip > linea_a else "MH (Limo de alta plasticidad)"
        else: return "CL (Arcilla de baja plasticidad)" if ip > linea_a else "ML (Limo de baja plasticidad)"

def calcular_humedad(m_recipiente, m_humeda_rec, m_seca_rec):
    m_agua = m_humeda_rec - m_seca_rec
    m_suelo_seco = m_seca_rec - m_recipiente
    return round((m_agua / m_suelo_seco) * 100.0, 2) if m_suelo_seco > 0 else 0.0

def calcular_proctor(puntos_proctor, volumen_molde_cm3=943.3):
    puntos_res = []
    for p in puntos_proctor:
        w_pct = float(p.get("humedad_pct", 0.0))
        m_hum = float(p.get("masa_humeda_g", 0.0))
        m_mol = float(p.get("masa_molde_g", 0.0))
        m_suelo_hum = m_hum - m_mol
        densidad_humeda = m_suelo_hum / volumen_molde_cm3
        densidad_seca = densidad_humeda / (1.0 + (w_pct / 100.0))
        puntos_res.append({
            "humedad_pct": round(w_pct, 2),
            "densidad_humeda_gcm3": round(densidad_humeda, 3),
            "densidad_seca_gcm3": round(densidad_seca, 3),
            "densidad_seca_kgm3": round(densidad_seca * 1000.0, 1)
        })
    puntos_res.sort(key=lambda x: x["humedad_pct"])
    max_densidad = max((p["densidad_seca_gcm3"] for p in puntos_res), default=0.0)
    w_optima = next((p["humedad_pct"] for p in puntos_res if p["densidad_seca_gcm3"] == max_densidad), 0.0)
    return {
        "puntos": puntos_res,
        "densidad_seca_maxima_gcm3": round(max_densidad, 3),
        "densidad_seca_maxima_kgm3": round(max_densidad * 1000.0, 1),
        "humedad_optima_pct": round(w_optima, 2)
    }
