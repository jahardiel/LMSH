"""
Motor de Cálculo Geotécnico y Clasificación de Suelos (ASTM D2487 SUCS, ASTM D6913, ASTM D4318, ASTM D698/D1557, ASTM D1883)
Laboratorio de Suelos, Materiales y Concreto Hidráulico - LSMCH
"""

import math

def calcular_granulometria(datos_tamices):
    """
    Calcula retenidos acumulados, % pasa, D10, D30, D60, Cu, Cc.
    datos_tamices: lista de dicts con keys:
       'tamiz': str, 'apertura_mm': float, 'masa_retenida': float
    """
    total_materia = sum(item.get('masa_retenida', 0.0) for item in datos_tamices)
    if total_materia == 0:
        return {"error": "Masa total retenida es 0"}

    ret_acumulado = 0.0
    resultado_tamices = []
    
    for item in datos_tamices:
        m_ret = float(item.get('masa_retenida', 0.0))
        apertura = float(item.get('apertura_mm', 0.0))
        nombre = str(item.get('tamiz', ''))
        
        pct_ret_ind = (m_ret / total_materia) * 100.0
        ret_acumulado += m_ret
        pct_ret_acum = (ret_acumulado / total_materia) * 100.0
        pct_pasa = 100.0 - pct_ret_acum
        if pct_pasa < 0:
            pct_pasa = 0.0
            
        resultado_tamices.append({
            "tamiz": nombre,
            "apertura_mm": apertura,
            "masa_retenida": m_ret,
            "pct_retenido_ind": round(pct_ret_ind, 2),
            "pct_retenido_acum": round(pct_ret_acum, 2),
            "pct_pasa": round(pct_pasa, 2)
        })

    # Interpolar D10, D30, D60 en escala semilog
    def interpolar_d(pct_objetivo):
        for i in range(len(resultado_tamices) - 1):
            p1 = resultado_tamices[i]["pct_pasa"]
            p2 = resultado_tamices[i+1]["pct_pasa"]
            d1 = resultado_tamices[i]["apertura_mm"]
            d2 = resultado_tamices[i+1]["apertura_mm"]
            
            if (p1 >= pct_objetivo >= p2) and d1 > 0 and d2 > 0 and p1 != p2:
                # Log-linear interpolation
                log_d1 = math.log10(d1)
                log_d2 = math.log10(d2)
                log_d = log_d1 + (pct_objetivo - p1) * (log_d2 - log_d1) / (p2 - p1)
                return round(10**log_d, 4)
        return None

    d10 = interpolar_d(10.0)
    d30 = interpolar_d(30.0)
    d60 = interpolar_d(60.0)
    
    cu = round(d60 / d10, 2) if (d60 and d10 and d10 > 0) else None
    cc = round((d30**2) / (d60 * d10), 2) if (d30 and d60 and d10 and (d60 * d10) > 0) else None

    # Porcentajes clave
    # Tamiz #4 (4.75 mm) y Tamiz #200 (0.075 mm)
    pasa_no4 = 100.0
    pasa_no200 = 0.0
    
    for t in resultado_tamices:
        if abs(t["apertura_mm"] - 4.75) < 0.2:
            pasa_no4 = t["pct_pasa"]
        elif abs(t["apertura_mm"] - 0.075) < 0.01:
            pasa_no200 = t["pct_pasa"]

    pct_grava = round(100.0 - pasa_no4, 2)
    pct_arena = round(pasa_no4 - pasa_no200, 2)
    pct_finos = round(pasa_no200, 2)

    return {
        "tamices": resultado_tamices,
        "total_masa": round(total_materia, 2),
        "d10": d10,
        "d30": d30,
        "d60": d60,
        "cu": cu,
        "cc": cc,
        "pct_grava": pct_grava,
        "pct_arena": pct_arena,
        "pct_finos": pct_finos
    }


def clasificar_sucs(pct_finos, pct_grava, pct_arena, ll=None, ip=None, cu=None, cc=None):
    """
    Clasificación automática de suelos según la norma ASTM D2487 (SUCS).
    """
    if pct_finos is None:
        return "Indeterminado (Faltan datos)"

    # Ecuación de la Línea A en la Carta de Plasticidad: IP_linea_A = 0.73 * (LL - 20)
    linea_a = (0.73 * (ll - 20)) if (ll is not None and ll >= 20) else 0.0

    # 1. SUELOS DE GRANO GRUESO (Finos <= 50%)
    if pct_finos < 50.0:
        es_grava = (pct_grava > pct_arena)
        
        # Poco o nada de finos (< 5%)
        if pct_finos < 5.0:
            if es_grava:
                if (cu is not None and cu >= 4.0) and (cc is not None and 1.0 <= cc <= 3.0):
                    return "GW (Grava bien graduada)"
                else:
                    return "GP (Grava mal graduada)"
            else:
                if (cu is not None and cu >= 6.0) and (cc is not None and 1.0 <= cc <= 3.0):
                    return "SW (Arena bien graduada)"
                else:
                    return "SP (Arena mal graduada)"
                    
        # Mucho fino (> 12%)
        elif pct_finos > 12.0:
            if ll is not None and ip is not None:
                es_arcilloso = (ip > linea_a and ip > 7)
                es_limoso = (ip < linea_a or ip < 4)
                if es_grava:
                    if es_arcilloso:
                        return "GC (Grava arcillosa)"
                    elif es_limoso:
                        return "GM (Grava limosa)"
                    else:
                        return "GC-GM (Grava arcillo-limosa)"
                else:
                    if es_arcilloso:
                        return "SC (Arena arcillosa)"
                    elif es_limoso:
                        return "SM (Arena limosa)"
                    else:
                        return "SC-SM (Arena arcillo-limosa)"
            else:
                return "Grava con finos" if es_grava else "Arena con finos"

        # Simbología doble (5% <= Finos <= 12%)
        else:
            es_bien_grad = False
            if es_grava and (cu is not None and cu >= 4.0) and (cc is not None and 1.0 <= cc <= 3.0):
                es_bien_grad = True
            elif not es_grava and (cu is not None and cu >= 6.0) and (cc is not None and 1.0 <= cc <= 3.0):
                es_bien_grad = True
                
            if ll is not None and ip is not None:
                es_arcilloso = (ip > linea_a and ip > 7)
                if es_grava:
                    return f"{'GW' if es_bien_grad else 'GP'}-{'GC' if es_arcilloso else 'GM'}"
                else:
                    return f"{'SW' if es_bien_grad else 'SP'}-{'SC' if es_arcilloso else 'SM'}"
            return "Grava/Arena con finos (Doble símbolo)"

    # 2. SUELOS DE GRANO FINO (Finos >= 50%)
    else:
        if ll is None or ip is None:
            return "Fino sin clasificar (Faltan Límites de Atterberg)"

        # Zona dual de la Carta de Plasticidad (4 <= IP <= 7 y LL entre 12 y 30)
        if 4 <= ip <= 7 and (ip >= linea_a or abs(ip - linea_a) <= 1):
            return "CL-ML (Arcilla limosa de baja plasticidad)"

        # Alta plasticidad (LL >= 50)
        if ll >= 50.0:
            if ip > linea_a:
                return "CH (Arcilla de alta plasticidad)"
            else:
                return "MH (Limo de alta plasticidad / suelo elástico)"
        # Baja o media plasticidad (LL < 50)
        else:
            if ip > linea_a:
                return "CL (Arcilla de baja a media plasticidad)"
            else:
                return "ML (Limo de baja plasticidad)"


def calcular_humedad(m_recipiente, m_humeda_rec, m_seca_rec):
    """Calcula el porcentaje de contenido de humedad (ASTM D2216)."""
    m_agua = m_humeda_rec - m_seca_rec
    m_suelo_seco = m_seca_rec - m_recipiente
    if m_suelo_seco <= 0:
        return 0.0
    return round((m_agua / m_suelo_seco) * 100.0, 2)


def calcular_proctor(puntos_proctor, volumen_molde_cm3=943.3):
    """
    Calcula la curva Proctor y determina γd máx y W óptimo.
    puntos_proctor: lista de dicts con:
      'humedad_pct': float, 'masa_humeda_g': float, 'masa_molde_g': float
    """
    puntos_res = []
    for p in puntos_proctor:
        w_pct = float(p.get("humedad_pct", 0.0))
        m_hum = float(p.get("masa_humeda_g", 0.0))
        m_mol = float(p.get("masa_molde_g", 0.0))
        
        m_suelo_hum = m_hum - m_mol
        densidad_humeda = m_suelo_hum / volumen_molde_cm3  # g/cm3
        densidad_seca = densidad_humeda / (1.0 + (w_pct / 100.0))  # g/cm3
        
        puntos_res.append({
            "humedad_pct": round(w_pct, 2),
            "densidad_humeda_gcm3": round(densidad_humeda, 3),
            "densidad_seca_gcm3": round(densidad_seca, 3),
            "densidad_seca_kgm3": round(densidad_seca * 1000.0, 1)
        })
        
    # Ordenar por humedad
    puntos_res.sort(key=lambda x: x["humedad_pct"])
    
    # Encontrar máximo (aproximación por parábola o punto máximo)
    max_densidad = 0.0
    w_optima = 0.0
    for p in puntos_res:
        if p["densidad_seca_gcm3"] > max_densidad:
            max_densidad = p["densidad_seca_gcm3"]
            w_optima = p["humedad_pct"]

    return {
        "puntos": puntos_res,
        "densidad_seca_maxima_gcm3": round(max_densidad, 3),
        "densidad_seca_maxima_kgm3": round(max_densidad * 1000.0, 1),
        "humedad_optima_pct": round(w_optima, 2)
    }
