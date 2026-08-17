"""
Motor de Cálculo Geotécnico Completo según Formato Oficial HC-LSMCH-006 (ASTM D6913 / D2487)
Laboratorio de Suelos y Materiales de Chiriquí (LSMCH) - Universidad Tecnológica de Panamá
"""

import math

# Lista oficial de tamices según norma ASTM D6913 / HC-LSMCH-006
TAMICES_OFICIALES = [
    {"tamiz": '3"', "apertura_mm": 75.000},
    {"tamiz": '2"', "apertura_mm": 50.000},
    {"tamiz": '1 1/2"', "apertura_mm": 38.100},
    {"tamiz": '1"', "apertura_mm": 25.000},
    {"tamiz": '3/4"', "apertura_mm": 19.000},
    {"tamiz": '3/8"', "apertura_mm": 9.500},
    {"tamiz": 'No. 4', "apertura_mm": 4.750},
    {"tamiz": 'No. 10', "apertura_mm": 2.000},
    {"tamiz": 'No. 20', "apertura_mm": 0.850},
    {"tamiz": 'No. 40', "apertura_mm": 0.425},
    {"tamiz": 'No. 60', "apertura_mm": 0.250},
    {"tamiz": 'No. 100', "apertura_mm": 0.150},
    {"tamiz": 'No. 140', "apertura_mm": 0.105},
    {"tamiz": 'No. 200', "apertura_mm": 0.075},
    {"tamiz": 'Fondo', "apertura_mm": 0.000}
]

def calcular_granulometria_hc006(datos):
    """
    Cálculo metrológico completo para la hoja de cálculo HC-LSMCH-006 (ASTM D6913).
    Soporta Tamizado Compuesto Método "A" o Tamizado Simple.
    """
    m_humeda_total = float(datos.get("masa_total_humeda_g", 1942.7))
    m_seca_total = float(datos.get("masa_total_seca_g", 1246.3))

    m_hum_sep_gruesa = float(datos.get("m_humeda_gruesa_g", 121.4))
    m_sec_sep_gruesa = float(datos.get("m_seca_gruesa_g", 77.9))

    m_hum_frac_fina = float(datos.get("m_humeda_fina_g", 1821.3))
    m_sec_frac_fina = float(datos.get("m_seca_fina_g", 84.6))
    
    tamices_input = datos.get("tamices", [])
    
    resultado_tamices = []
    ret_acumulada_pct = 0.0

    for t_def in TAMICES_OFICIALES:
        nombre = t_def["tamiz"]
        apertura = t_def["apertura_mm"]
        
        item_in = next((x for x in tamices_input if x.get("tamiz") == nombre), {})
        m_ret_gruesa = float(item_in.get("fgruesa_g", 0.0))
        m_ret_fina = float(item_in.get("ffina_g", item_in.get("masa_retenida", 0.0)))
        
        if m_seca_total > 0:
            pct_ret_ind = (m_ret_fina / m_seca_total) * 100.0 if m_ret_fina > 0 else (m_ret_gruesa / m_seca_total) * 100.0
        else:
            pct_ret_ind = 0.0
            
        ret_acumulada_pct += pct_ret_ind
        pct_pasa = 100.0 - ret_acumulada_pct
        if pct_pasa < 0: pct_pasa = 0.0
        
        resultado_tamices.append({
            "tamiz": nombre,
            "apertura_mm": apertura,
            "fgruesa_g": m_ret_gruesa,
            "ffina_g": m_ret_fina,
            "pct_retenido_ind": round(pct_ret_ind, 2),
            "pct_acumulado_ret": round(ret_acumulada_pct, 2),
            "pct_pasa": round(pct_pasa, 2)
        })

    def interpolar_d_exacto(pct_objetivo):
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

    d10 = interpolar_d_exacto(10.0)
    d15 = interpolar_d_exacto(15.0)
    d30 = interpolar_d_exacto(30.0)
    d50 = interpolar_d_exacto(50.0)
    d60 = interpolar_d_exacto(60.0)
    d85 = interpolar_d_exacto(85.0)

    cu = round(d60 / d10, 2) if (d60 and d10 and d10 > 0) else None
    cc = round((d30**2) / (d60 * d10), 2) if (d30 and d60 and d10 and (d60 * d10) > 0) else None

    pasa_no4 = 100.0
    pasa_no200 = 0.0
    
    for t in resultado_tamices:
        if t["tamiz"] == 'No. 4': pasa_no4 = t["pct_pasa"]
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

    ll = datos.get("ll")
    lp = datos.get("lp")
    ip = round(float(ll) - float(lp), 2) if (ll is not None and lp is not None) else None
    
    sucs = clasificar_sucs(pct_finos, pct_grava, pct_arena, ll=float(ll) if ll is not None else None, ip=ip, cu=cu, cc=cc)

    return {
        "formato": "HC-LSMCH-006",
        "norma": "ASTM D6913",
        "tamices": resultado_tamices,
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
    """Compatibilidad con llamadas previas."""
    if isinstance(datos_tamices, dict):
        return calcular_granulometria_hc006(datos_tamices)
    return calcular_granulometria_hc006({"tamices": datos_tamices})

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
