import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Optional

def generar_graficos_incertidumbre(resultados_gum: Dict, filename: str = "grafico_aportacion_incertidumbre.png", show_plot: bool = False):
    """
    Genera y guarda gráficos de alta definición metrológica para el informe oficial HC-LSMCH-012.
    
    Incluye:
    1. Gráfico de Pastel / Donut: Aportación Porcentual a la Varianza (%)
    2. Gráfico de Barras: Comparativa de Incertidumbres Estándar u_i(y) vs Combinada (u_c) y Expandida (U)
    """
    unidad = resultados_gum.get("unidad", "°C")

    # Configurar estilo visual profesional para informe imprimible de gran formato
    plt.style.use('default')
    fig = plt.figure(figsize=(14, 6.2), dpi=250)
    fig.patch.set_facecolor('#ffffff')

    fuentes = resultados_gum["fuentes"]
    fuentes_ordenadas = sorted(fuentes, key=lambda x: x["contribucion_pct"], reverse=True)

    nombres = [f["fuente"] for f in fuentes_ordenadas]
    pcts = [f["contribucion_pct"] for f in fuentes_ordenadas]
    u_vals = [f["u_i_y"] for f in fuentes_ordenadas]

    colores = ['#84cc16', '#0284c7', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

    # --- SUBPLOT 1: Gráfico de Pastel 3D (Aportación Porcentual %) ---
    ax1 = fig.add_subplot(1, 2, 1)
    ax1.set_facecolor('#ffffff')
    
    # Filtrar fuentes con contribución > 0.01%
    pcts_pie = [p for p in pcts if p >= 0.01]
    nombres_pie = [nombres[i] for i, p in enumerate(pcts) if p >= 0.01]
    
    # Explode para la fuente principal como en el formato oficial
    explode = [0.06 if i == 0 else 0.0 for i in range(len(pcts_pie))]

    wedges, texts, autotexts = ax1.pie(
        pcts_pie,
        labels=nombres_pie,
        autopct='%1.1f%%',
        startangle=140,
        explode=explode,
        shadow=True,
        colors=colores[:len(pcts_pie)],
        wedgeprops=dict(edgecolor='#ffffff', linewidth=1.5),
        pctdistance=0.68
    )
    for text in texts:
        text.set_fontsize(9.5)
        text.set_color('#0f172a')
        text.set_fontweight('bold')
    for autotext in autotexts:
        autotext.set_fontsize(9.5)
        autotext.set_fontweight('bold')
        autotext.set_color('#ffffff')

    ax1.set_title("INCERTIDUMBRE APORTADA POR CADA FUENTE", fontsize=12, fontweight='bold', pad=14, color='#1e3a8a')

    # --- SUBPLOT 2: Gráfico de Barras (u_i vs u_c vs U) ---
    ax2 = fig.add_subplot(1, 2, 2)
    ax2.set_facecolor('#f8fafc')
    ax2.grid(True, linestyle='--', alpha=0.5, color='#cbd5e1')
    
    nombres_short = [f.get("simbolo", f"u_{i+1}") for i, f in enumerate(fuentes_ordenadas)] + ["u_c (Comb)", "U (Exp)"]
    u_vals_all = u_vals + [resultados_gum["u_combinada"], resultados_gum["incertidumbre_expandida_U"]]
    colores_bar = ['#334155'] * len(fuentes_ordenadas) + ['#d97706', '#dc2626']

    bars = ax2.bar(nombres_short, u_vals_all, color=colores_bar, width=0.55, edgecolor='#0f172a', linewidth=1.2)
    ax2.set_ylabel(f"Incertidumbre ({unidad})", fontsize=11, fontweight='bold', color='#0f172a')
    ax2.set_title(f"COMPARATIVA DE INCERTIDUMBRES ({unidad})", fontsize=12, fontweight='bold', pad=14, color='#1e3a8a')
    plt.xticks(fontsize=10.5, fontweight='bold', color='#0f172a')
    plt.yticks(fontsize=9.5, color='#334155')

    # Anotar valores arriba de las barras
    max_val = max(u_vals_all) if len(u_vals_all) > 0 else 1.0
    for bar in bars:
        height = bar.get_height()
        ax2.text(
            bar.get_x() + bar.get_width()/2.0, height + (max_val * 0.03),
            f"{height:.4f}",
            ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#0f172a'
        )

    ax2.set_ylim(0, max_val * 1.25)

    plt.tight_layout()
    plt.savefig(filename, dpi=250, bbox_inches='tight', facecolor='#ffffff')
    plt.close()
    return filename

if __name__ == "__main__":
    from gum_calculator import GUMCalculator
    puntos_demo = [
        {"temp_indicada": 0.0, "correccion": 0.02, "u_expandida": 0.04, "factor_k": 2.0},
        {"temp_indicada": 25.0, "correccion": 0.04, "u_expandida": 0.05, "factor_k": 2.0},
        {"temp_indicada": 50.0, "correccion": 0.08, "u_expandida": 0.06, "factor_k": 2.0},
    ]
    res = GUMCalculator.evaluar_incertidumbre(
        lecturas_concreto=[24.5, 24.6, 24.5, 24.7, 24.5],
        resolucion=0.1,
        puntos_calibracion=puntos_demo,
        deriva_estimada=0.05
    )
    generar_graficos_incertidumbre(res, filename="test_grafico_lsmch.png")
    print("Gráfico LSMCH generado.")
