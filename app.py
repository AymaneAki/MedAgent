# app.py

import os
import re
import sys
import time
import glob
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parent
sys.path.append(str(root))

from tools.pdf_reader import read_report
from tools.report_generator import generate_reports
from tools.threshold_checker import check_all
from agents import (
    agent_extractor,
    agent_interpreter,
    agent_alerter,
    agent_writer
)

# Page Configuration
st.set_page_config(
    page_title="MedAgent — Analyse Clinique IA",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700;800&family=Outfit:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Responsive themes using Streamlit native variables */
    .stApp {
        background-color: var(--background-color);
        color: var(--text-color);
    }
    
    .main-title {
        font-family: 'Outfit', sans-serif;
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
        letter-spacing: -1px;
    }
    
    .sub-title {
        color: var(--text-color);
        opacity: 0.85;
        font-size: 1.1rem;
        margin-bottom: 30px;
    }
    
    /* Custom Cards adapt to light/dark themes */
    .dashboard-card {
        background-color: var(--secondary-background-color);
        border-radius: 20px;
        padding: 25px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.15);
        margin-bottom: 25px;
    }
    
    .card-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--text-color);
        margin-bottom: 15px;
        border-bottom: 2px solid rgba(128, 128, 128, 0.1);
        padding-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Emojis & Badges styling */
    .badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 800;
        text-align: center;
    }
    
    .badge-normal {
        background-color: rgba(14, 165, 233, 0.15);
        color: #0ea5e9;
    }
    
    .badge-abnormal {
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
    }
    
    .badge-critical {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        animation: pulse 2s infinite;
    }
    
    /* Emergency Alert box */
    .emergency-alert-box {
        background-color: rgba(239, 68, 68, 0.12);
        border-left: 6px solid #ef4444;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
    }
    
    .emergency-title {
        color: #ef4444;
        font-weight: 800;
        font-size: 1.15rem;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .emergency-desc {
        color: var(--text-color);
        font-size: 0.95rem;
        opacity: 0.95;
    }
    
    /* Custom HTML table styling */
    .clinical-table {
        width: 100%;
        border-collapse: collapse;
        color: var(--text-color);
    }
    
    .clinical-table th {
        background-color: rgba(128, 128, 128, 0.08);
        color: var(--text-color);
        font-weight: 700;
        text-align: left;
        padding: 12px 15px;
        border-bottom: 2px solid rgba(128, 128, 128, 0.15);
    }
    
    .clinical-table td {
        padding: 14px 15px;
        border-bottom: 1px solid rgba(128, 128, 128, 0.1);
        vertical-align: middle;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to guess gender, age, reason from text
def parse_demographics(text: str) -> dict:
    age_match = re.search(r"(?:Âge|Age)\s*:\s*([^\n]+)", text, re.IGNORECASE)
    gender_match = re.search(r"Sexe\s*:\s*([^\n]+)", text, re.IGNORECASE)
    reason_match = re.search(r"Motif\s*:\s*([^\n]+)", text, re.IGNORECASE)
    
    gender_str = "default"
    if gender_match:
        g = gender_match.group(1).lower()
        if "fem" in g or "fém" in g:
            gender_str = "female"
        elif "mas" in g or "hom" in g:
            gender_str = "male"

    return {
        "age": age_match.group(1).strip() if age_match else "Non spécifié",
        "gender": "Féminin" if gender_str == "female" else "Masculin" if gender_str == "male" else "Non spécifié",
        "gender_key": gender_str,
        "reason": reason_match.group(1).strip() if reason_match else "Non spécifié"
    }

# ── Sidebar UI ──
st.sidebar.markdown("<h2 style='font-family: Outfit; font-weight:800; font-size:1.6rem;'>🧬 MedAgent</h2>", unsafe_allow_html=True)
st.sidebar.markdown("Plateforme d'aide à la décision clinique multi-agent.")
st.sidebar.divider()

# Demo File Loader
st.sidebar.subheader("💡 Tester rapidement")
demo_btn = st.sidebar.button("📂 Charger le rapport type (fatigue intense)")
demo_noisy_btn = st.sidebar.button("🚨 Charger le rapport Stress-Test (Bruit)")

# Manual demographics override
st.sidebar.subheader("👤 Profil Patient")
gender_input = st.sidebar.selectbox("Genre pour l'analyse", ["Par défaut (Détection auto)", "Masculin", "Féminin"])
age_input = st.sidebar.text_input("Âge (Facultatif)", placeholder="Ex: 67 ans")

# API Keys Sidebar Config
st.sidebar.subheader("🔑 Clés API de Secours")
gemini_key = st.sidebar.text_input("GEMINI_API_KEY", type="password", help="Optionnel. Si le serveur Docker est hors-ligne.")
openai_key = st.sidebar.text_input("OPENAI_API_KEY", type="password", help="Optionnel. Si le serveur Docker est hors-ligne.")

if gemini_key:
    os.environ["GEMINI_API_KEY"] = gemini_key
if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key

# Output dir setup
output_dir = root / "output" / "summaries"
os.makedirs(output_dir, exist_ok=True)

# ── Main Area UI ──
st.markdown("<h1 class='main-title'>🔬 Console Médicale Multi-Agent</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Analyse biologique intelligente et système d'alerte clinique d'urgence.</p>", unsafe_allow_html=True)

# Initialize Session State for report text
if "report_text" not in st.session_state:
    st.session_state["report_text"] = ""
if "file_name" not in st.session_state:
    st.session_state["file_name"] = ""

if demo_btn:
    try:
        demo_path = root / "data" / "reports" / "report_01.txt"
        st.session_state["report_text"] = read_report(str(demo_path))
        st.session_state["file_name"] = "report_01.txt"
        st.sidebar.success("Rapport type chargé successfully !")
    except Exception as e:
        st.sidebar.error(f"Impossible de charger le rapport type : {e}")

if demo_noisy_btn:
    try:
        demo_path = root / "data" / "reports" / "report_noisy.txt"
        st.session_state["report_text"] = read_report(str(demo_path))
        st.session_state["file_name"] = "report_noisy.txt"
        st.sidebar.success("Rapport de Stress-Test chargé successfully !")
    except Exception as e:
        st.sidebar.error(f"Impossible de charger le rapport de Stress-Test : {e}")

# File Uploader
uploaded_file = st.file_uploader("Importer un rapport d'analyse médicale (PDF ou TXT)", type=["pdf", "txt"])

if uploaded_file:
    # Save temporarily to parse
    temp_dir = root / "scratch"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = temp_dir / uploaded_file.name
    
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    try:
        st.session_state["report_text"] = read_report(str(temp_path))
        st.session_state["file_name"] = uploaded_file.name
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")

# Display active report text area
if st.session_state["report_text"]:
    with st.expander("📄 Contenu brut du rapport importé", expanded=False):
        st.text_area("Contenu du texte", st.session_state["report_text"], height=250, disabled=True)
        
    # Gender decision
    demo_data = parse_demographics(st.session_state["report_text"])
    gender = demo_data["gender_key"]
    if gender_input == "Masculin":
        gender = "male"
    elif gender_input == "Féminin":
        gender = "female"
        
    # Active demographics card
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**Âge détecté / saisi** : {age_input if age_input else demo_data['age']}")
    with col2:
        st.info(f"**Genre configuré** : {'Masculin' if gender == 'male' else 'Féminin' if gender == 'female' else 'Non spécifié'}")
    with col3:
        st.info(f"**Motif clinique suspecté** : {demo_data['reason'][:50]}")

    trigger_btn = st.button("🚀 Lancer l'analyse médicale MedAgent", type="primary")

    if trigger_btn:
        st.divider()
        st.subheader("⚙️ Suivi de l'activité des agents")
        
        # UI Agent Pipeline Tracker
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. Extractor Agent
        status_text.markdown("🔍 **Agent 1 — Extractor** : Extraction des paramètres biologiques en cours...")
        progress_bar.progress(15)
        time.sleep(0.5)
        
        try:
            extracted_params = agent_extractor.run(st.session_state["report_text"])
            st.success(f"✓ Agent 1 — Extractor : {len(extracted_params)} constantes cliniques extraites !")
            
            # 2. Interpreter Agent
            status_text.markdown("🧪 **Agent 2 — Interpreter** : Comparaison avec la base de données clinique de référence...")
            progress_bar.progress(40)
            time.sleep(0.5)
            
            annotated_params = agent_interpreter.run(extracted_params, gender=gender)
            critical_count = sum(1 for p in annotated_params if p["status"] == "CRITICAL")
            abnormal_count = sum(1 for p in annotated_params if p["status"] == "ABNORMAL")
            st.success(f"✓ Agent 2 — Interpreter : Interprétation achevée ({critical_count} critiques, {abnormal_count} anormaux) !")
            
            # 3. Alerter Agent
            status_text.markdown("🚨 **Agent 3 — Alerter** : Génération des alertes et actions d'urgence...")
            progress_bar.progress(70)
            time.sleep(0.5)
            
            alert_report = agent_alerter.run(annotated_params)
            st.success(f"✓ Agent 3 — Alerter : {len(alert_report['alerts'])} fiches d'alerte rédigées !")
            
            # 4. Writer Agent
            status_text.markdown("📋 **Agent 4 — Writer** : Rédaction du rapport de synthèse clinique...")
            progress_bar.progress(90)
            time.sleep(0.5)
            
            summary_text = agent_writer.run(annotated_params, alert_report, st.session_state["report_text"])
            progress_bar.progress(100)
            status_text.markdown("✨ **Pipeline achevé avec succès !**")
            st.success("✓ Agent 4 — Writer : Rapport clinique de synthèse rédigé !")
            
            # Save Deliverables
            file_stem = Path(st.session_state["file_name"]).stem
            output_base = str(output_dir / f"{file_stem}_summary")
            
            # Demographic adjustments
            final_demographics = {
                "age": age_input if age_input else demo_data["age"],
                "gender": "Masculin" if gender == "male" else "Féminin" if gender == "female" else "Non spécifié",
                "reason": demo_data["reason"],
                "history": "Non précisé dans le rapport"
            }
            
            generate_reports(
                patient_info=final_demographics,
                annotated_params=annotated_params,
                alert_report=alert_report,
                summary_text=summary_text,
                output_path_base=output_base
            )
            
            st.balloons()
            st.divider()
            
            # ── Display Dashboard Deliverables ──
            
            # Critical Alert Callout
            if critical_count > 0:
                st.markdown(f"""
                <div class="emergency-alert-box">
                    <div class="emergency-title">🚨 ALERTE CRITIQUE : URGENCE MÉDICALE ACTIVES ({critical_count})</div>
                    <div class="emergency-desc">
                        Certains paramètres biologiques du patient ont franchi les seuils critiques de tolérance clinique. Une évaluation médicale immédiate est vivement recommandée.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Show critical alerts actions list
                st.markdown("**Actions immédiates recommandées :**")
                for alert in alert_report["alerts"]:
                    if alert["status"] == "CRITICAL":
                        st.error(f"• **{alert['parameter'].upper()}** ({alert['value']} {alert['unit']}) : {alert['action']}")
                st.write("")
                
            # Layout tabs for results
            tab_results, tab_summary, tab_charts = st.tabs(["🧪 Résultats Cliniques", "📋 Synthèse de l'Agent", "📊 Graphiques Analytiques"])
            
            with tab_results:
                # Custom CSS styled table
                table_html = """
                <table class="clinical-table">
                    <thead>
                        <tr>
                            <th>Paramètre Biologique</th>
                            <th style="text-align: center;">Valeur Patient</th>
                            <th style="text-align: center;">Unité</th>
                            <th style="text-align: center;">Plage de Référence</th>
                            <th style="text-align: center;">Statut</th>
                            <th>Source brute dans le rapport (survoler)</th>
                            <th>Risque Associé / Commentaire Clinique</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                for p in annotated_params:
                    badge_cls = "badge-critical" if p["status"] == "CRITICAL" else \
                                "badge-abnormal" if p["status"] == "ABNORMAL" else "badge-normal"
                    badge_lbl = "CRITIQUE" if p["status"] == "CRITICAL" else \
                                "ANORMAL" if p["status"] == "ABNORMAL" else "NORMAL"
                    risk = p.get('clinical_risk') or 'Valeur dans les normes de référence.'
                    
                    # Highlight OCR or source context
                    src = p.get('source_context', 'N/A')
                    
                    table_html += f"""
                    <tr>
                        <td style="font-weight: 700; color: var(--text-color);">{p['parameter']}</td>
                        <td style="text-align: center; font-family: monospace; font-size: 1.1rem; font-weight: 700; color: var(--text-color);">{p['value']}</td>
                        <td style="text-align: center; color: var(--text-color); opacity: 0.8; font-weight: 600;">{p['unit']}</td>
                        <td style="text-align: center; font-family: monospace; color: var(--text-color); opacity: 0.9;">{p['normal_range']}</td>
                        <td style="text-align: center;"><span class="badge {badge_cls}">{badge_lbl}</span></td>
                        <td style="font-family: monospace; font-size: 0.8rem; color: #888888; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{src}">{src}</td>
                        <td style="color: var(--text-color); opacity: 0.95; font-size: 0.9rem;">{risk}</td>
                    </tr>
                    """
                table_html += "</tbody></table>"
                st.markdown(table_html, unsafe_allow_html=True)
                
            with tab_summary:
                st.info("Cette synthèse a été rédigée de manière autonome par l'agent Writer sur la base de vos analyses.")
                st.markdown(summary_text)
                
                st.divider()
                st.subheader("📥 Téléchargements")
                
                # Expose generated files via standard download buttons
                try:
                    with open(output_base + ".pdf", "rb") as pdf_file:
                        st.download_button(
                            label="📥 Télécharger le compte-rendu officiel (PDF)",
                            data=pdf_file,
                            file_name=f"{file_stem}_summary.pdf",
                            mime="application/pdf"
                        )
                    with open(output_base + ".html", "rb") as html_file:
                        st.download_button(
                            label="🌐 Télécharger la page Web interactive (HTML)",
                            data=html_file,
                            file_name=f"{file_stem}_summary.html",
                            mime="text/html"
                        )
                    with open(output_base + ".md", "rb") as md_file:
                        st.download_button(
                            label="📝 Télécharger la fiche de synthèse (Markdown)",
                            data=md_file,
                            file_name=f"{file_stem}_summary.md",
                            mime="text/markdown"
                        )
                except Exception as e:
                    st.warning(f"Erreur de chargement des fichiers livrables : {e}")

            with tab_charts:
                # Plot parameters deviation using matplotlib
                st.write("Visualisation des écarts par rapport aux plages normales :")
                
                # Prepare plot data
                plot_data = []
                for p in annotated_params:
                    # Get values
                    val = p["value"]
                    ref_range = p["normal_range"]
                    # Extract min and max
                    match = re.findall(r"([0-9.]+)", ref_range)
                    if len(match) >= 2:
                        ref_min = float(match[0])
                        ref_max = float(match[1])
                        # Calculate percentage deviation from center
                        center = (ref_min + ref_max) / 2
                        span = (ref_max - ref_min) if (ref_max - ref_min) > 0 else 1.0
                        pct = (val - center) / span * 100
                        plot_data.append({
                            "parameter": p["parameter"],
                            "deviation": pct,
                            "status": p["status"],
                            "val": val,
                            "ref": ref_range
                        })
                
                if plot_data:
                    df_plot = pd.DataFrame(plot_data)
                    fig, ax = plt.subplots(figsize=(10, len(plot_data) * 0.6))
                    
                    colors = df_plot["status"].map({
                        "CRITICAL": "#ef4444",
                        "ABNORMAL": "#f59e0b",
                        "NORMAL": "#0ea5e9"
                    }).fillna("#cbd5e1")
                    
                    # Horizontal Bar Chart
                    bars = ax.barh(df_plot["parameter"], df_plot["deviation"], color=colors, height=0.5)
                    
                    # Style details
                    ax.axvline(x=-50, color='#94a3b8', linestyle='--', alpha=0.7, label='Limite basse')
                    ax.axvline(x=50, color='#94a3b8', linestyle='--', alpha=0.7, label='Limite haute')
                    ax.axvline(x=0, color='#e2e8f0', linestyle='-', alpha=0.5)
                    
                    ax.set_title("Écart Clinique Patient par Rapport aux Normes (Normal = -50% à +50%)", fontsize=11, fontweight='bold', pad=15)
                    ax.set_xlabel("Déviation (%)", fontsize=9)
                    
                    # Set X limit for visibility
                    ax.set_xlim(-150, 150)
                    
                    # Add value labels
                    for bar, row in zip(bars, df_plot.itertuples()):
                        width = bar.get_width()
                        align = 'left' if width < 0 else 'right'
                        offset = -5 if width < 0 else 5
                        ax.annotate(
                            f"{row.val}",
                            xy=(width, bar.get_y() + bar.get_height() / 2),
                            xytext=(offset, 0),
                            textcoords="offset points",
                            ha=align, va='center',
                            fontsize=8, fontweight='bold',
                            color='#1e293b'
                        )
                        
                    plt.tight_layout()
                    st.pyplot(fig)
                else:
                    st.info("Pas assez de données valides de référence pour tracer le graphe des déviations.")
                    
        except Exception as e:
            st.error(f"Erreur d'analyse fatale : {e}")
            logging.error(f"Fatal error in App UI: {e}", exc_info=True)

# ── Tab 2: History UI ──
st.divider()
st.subheader("📂 Historique des Analyses Cliniques")

history_files = glob.glob(str(output_dir / "*_summary.md"))
if history_files:
    # Build history records
    records = []
    for f in history_files:
        path = Path(f)
        mtime = os.path.getmtime(f)
        date_str = time.strftime('%d/%m/%Y %H:%M', time.localtime(mtime))
        records.append({
            "Nom du Fichier": path.stem.replace("_summary", ""),
            "Date d'analyse": date_str,
            "Chemin": path
        })
        
    df_history = pd.DataFrame(records)
    st.dataframe(df_history[["Nom du Fichier", "Date d'analyse"]], use_container_width=True)
    
    selected_name = st.selectbox("Recharger un rapport d'historique", df_history["Nom du Fichier"].tolist())
    
    if selected_name:
        record_path = df_history[df_history["Nom du Fichier"] == selected_name]["Chemin"].values[0]
        base_path = str(record_path).replace(".md", "")
        
        st.markdown(f"### Visualisation : {selected_name}")
        with open(str(record_path), "r", encoding="utf-8") as rf:
            st.markdown(rf.read())
            
        col1, col2 = st.columns(2)
        with col1:
            if os.path.exists(base_path + ".pdf"):
                with open(base_path + ".pdf", "rb") as pdf_f:
                    st.download_button("📥 Re-télécharger en PDF", pdf_f, file_name=f"{selected_name}_summary.pdf", mime="application/pdf")
        with col2:
            if os.path.exists(base_path + ".html"):
                with open(base_path + ".html", "rb") as html_f:
                    st.download_button("🌐 Re-télécharger en HTML", html_f, file_name=f"{selected_name}_summary.html", mime="text/html")
else:
    st.info("Aucune analyse enregistrée dans l'historique pour le moment.")
