import os
import sys
import pandas as pd
from database_manager import DatabaseManager
from gum_calculator import GUMCalculator
from uncertainty_plots import generar_graficos_incertidumbre

def mostrar_menu():
    print("\n" + "="*70)
    print(" ESTIMADOR DE INCERTIDUMBRE DE MEDICIÓN DE TEMPERATURA DEL CONCRETO")
    print("                     (Según Guía GUM - ISO/IEC Guide 98-3)")
    print("="*70)
    print(" 1. Ver termómetros y certificados registrados en la base de datos")
    print(" 2. Registrar un nuevo termómetro y sus puntos de calibración")
    print(" 3. Estimar incertidumbre de una medición de temperatura de concreto")
    print(" 4. Ejecutar Demostración Automática (Ejemplo Rápido)")
    print(" 5. Salir")
    print("="*70)

def menu_ver_termometros(db: DatabaseManager):
    termometros = db.obtener_termometros()
    print("\n--- TERMÓMETROS REGISTRADOS ---")
    if not termometros:
        print("No hay termómetros en la base de datos.")
        return
    for t in termometros:
        print(f"\n[ID: {t['id']}] Código: {t['codigo']} | Marca: {t['marca']} | Modelo: {t['modelo']} | Serie: {t['numero_serie']}")
        print(f"     Resolución: {t['resolucion']} °C | Deriva estimada: {t['deriva_estimada']} °C | Fecha Calibración: {t['fecha_calibracion']}")
        puntos = db.obtener_puntos_calibracion(t['id'])
        print("     Tabla de Calibración Certificada:")
        print("     " + "-"*55)
        print(f"     {'T. Indicada (°C)':<18} {'T. Patrón (°C)':<18} {'Corrección (°C)':<18} {'U_cal (°C)':<12} {'k':<5}")
        for p in puntos:
            print(f"     {p['temp_indicada']:<18.2f} {p['temp_patron']:<18.2f} {p['correccion']:<18.2f} {p['u_expandida']:<12.2f} {p['factor_k']:<5.2f}")

def menu_agregar_termometro(db: DatabaseManager):
    print("\n--- REGISTRO DE NUEVO TERMÓMETRO Y CERTIFICADO ---")
    codigo = input("Código interno del termómetro (ej. TERM-CONC-02): ").strip()
    marca = input("Marca (ej. Fluke / Testo): ").strip()
    modelo = input("Modelo: ").strip()
    serie = input("Número de Serie: ").strip()
    try:
        resolucion = float(input("Resolución del termómetro en °C (ej. 0.1 o 0.01): "))
        deriva = float(input("Deriva estimada en °C (ej. 0.05): "))
    except ValueError:
        print("Error: Ingrese números válidos para resolución y deriva.")
        return

    fecha = input("Fecha de calibración (YYYY-MM-DD): ").strip()
    lab = input("Laboratorio de calibración: ").strip()

    t_id = db.agregar_termometro(codigo, marca, modelo, serie, resolucion, deriva, fecha, lab)
    print(f"Termómetro '{codigo}' registrado con ID {t_id}.")

    print("\nAhora ingrese los puntos de la tabla del Certificado de Calibración (Presione ENTER en 'Temp Indicada' para finalizar):")
    p = 1
    while True:
        print(f"\nPunto de Calibración #{p}:")
        val_ind = input(" Temp Indicada por el termómetro en °C (o presione ENTER para terminar): ").strip()
        if not val_ind:
            break
        try:
            temp_ind = float(val_ind)
            temp_ref = float(input(" Temp del Patrón / Referencia en °C: "))
            u_exp = float(input(" Incertidumbre Expandida U_cal en °C: "))
            k_cal = float(input(" Factor de Cobertura k (usualmente 2.0): ") or "2.0")
            db.agregar_punto_calibracion(t_id, temp_ind, temp_ref, u_exp, k_cal)
            print(f" Punto #{p} guardado.")
            p += 1
        except ValueError:
            print("Error: Valor numérico no válido. Intente de nuevo este punto.")

def menu_estimar_incertidumbre(db: DatabaseManager):
    termometros = db.obtener_termometros()
    if not termometros:
        print("No hay termómetros registrados. Registre uno primero o use la demostración.")
        return

    print("\nSeleccione el termómetro a utilizar:")
    for t in termometros:
        print(f" [{t['id']}] {t['codigo']} ({t['marca']} {t['modelo']}) - Resolución: {t['resolucion']} °C")

    try:
        t_id = int(input("Ingrese el ID del termómetro: "))
        term_sel = next((t for t in termometros if t['id'] == t_id), None)
        if not term_sel:
            print("ID de termómetro no válido.")
            return
    except ValueError:
        print("ID debe ser un número entero.")
        return

    puntos_cal = db.obtener_puntos_calibracion(t_id)
    if not puntos_cal:
        print("Advertencia: El termómetro no tiene puntos de calibración registrados. Se usarán valores predeterminados.")

    print("\n--- LECTURAS DE TEMPERATURA EN LA MEZCLA DE CONCRETO ---")
    print("Ingrese las lecturas individuales tomadas en el concreto (ejemplo: 24.5 24.6 24.5 24.7 24.5)")
    lecturas_str = input("Lecturas separadas por espacio: ").strip()
    try:
        lecturas = [float(x) for x in lecturas_str.split()]
        if not lecturas:
            raise ValueError
    except ValueError:
        print("Usando lecturas predeterminadas de ejemplo [24.5, 24.6, 24.5, 24.7, 24.5]")
        lecturas = [24.5, 24.6, 24.5, 24.7, 24.5]

    try:
        homog = float(input("Homogeneidad/Gradiente estimado en el concreto en °C (predeterminado 0.10 °C): ") or "0.10")
    except ValueError:
        homog = 0.10

    # Ejecutar cálculo GUM
    res = GUMCalculator.evaluar_incertidumbre(
        lecturas_concreto=lecturas,
        resolucion=term_sel['resolucion'],
        puntos_calibracion=puntos_cal,
        deriva_estimada=term_sel['deriva_estimada'],
        homogeneidad_concreto=homog
    )

    imprimir_reporte(term_sel, res)
    img_name = f"grafico_incertidumbre_{term_sel['codigo']}.png"
    generar_graficos_incertidumbre(res, filename=img_name, show_plot=False)

def imprimir_reporte(termometro: dict, res: dict):
    print("\n" + "="*80)
    print("                       REPORTE DE INCERTIDUMBRE GUM")
    print("="*80)
    print(f"Termómetro Utilizado  : {termometro['codigo']} ({termometro['marca']} {termometro['modelo']})")
    print(f"Resolución Instrumento: {termometro['resolucion']} °C")
    print(f"Lecturas de Campo (°C): {res['lecturas_originales']} (n = {res['num_lecturas']})")
    print(f"Temperatura Media Ind.: {res['temp_media_indicada']:.3f} °C")
    print(f"Corrección Calibración: {res['correccion_aplicada']:+.3f} °C")
    print("-" * 80)
    print(f"TEMPERATURA FINAL ESTIMADA: {res['temp_estimada_final']:.3f} °C")
    print(f"Incertidumbre Estándar Combinada (u_c): {res['u_combinada']:.4f} °C")
    print(f"Grados de Libertad Efectivos (nu_eff) : {res['grados_libertad_efectivos']}")
    print(f"Factor de Cobertura (k) ({res['nivel_confianza_pct']:.2f}%): {res['factor_k']:.3f}")
    print(f"INCERTIDUMBRE EXPANDIDA (U)           : ± {res['incertidumbre_expandida_U']:.4f} °C")
    print("="*80)
    print("\nPRESUPUESTO DE INCERTIDUMBRE (TABLA GUM):")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(res['tabla_presupuesto'].to_string(index=False))
    print("="*80)

def ejecutar_demostración_automatica():
    print("\nEjecutando Demostración Automática...")
    db = DatabaseManager()
    termometros = db.obtener_termometros()
    term_demo = termometros[0]
    puntos_cal = db.obtener_puntos_calibracion(term_demo['id'])

    lecturas_concreto = [23.4, 23.6, 23.5, 23.7, 23.5, 23.4]
    
    res = GUMCalculator.evaluar_incertidumbre(
        lecturas_concreto=lecturas_concreto,
        resolucion=term_demo['resolucion'],
        puntos_calibracion=puntos_cal,
        deriva_estimada=term_demo['deriva_estimada'],
        homogeneidad_concreto=0.10
    )

    imprimir_reporte(term_demo, res)
    archivo_grafico = "grafico_aportacion_incertidumbre_demo.png"
    generar_graficos_incertidumbre(res, filename=archivo_grafico, show_plot=False)
    print(f"\n[ÉXITO] El gráfico de aportación de incertidumbres ha sido generado y guardado en: '{archivo_grafico}'")

def main():
    db = DatabaseManager()
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        ejecutar_demostración_automatica()
        return

    while True:
        mostrar_menu()
        opc = input("Seleccione una opción (1-5): ").strip()
        if opc == '1':
            menu_ver_termometros(db)
        elif opc == '2':
            menu_agregar_termometro(db)
        elif opc == '3':
            menu_estimar_incertidumbre(db)
        elif opc == '4':
            ejecutar_demostración_automatica()
        elif opc == '5':
            print("\n¡Gracias por utilizar el Estimador de Incertidumbre GUM!")
            break
        else:
            print("Opción no válida. Intente de nuevo.")

if __name__ == "__main__":
    main()
