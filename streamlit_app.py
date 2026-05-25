import streamlit as st
import pandas as pd
import re
import os

# ==============================================================================
# CONFIGURAZIONE STRUTTURALE DELLA PAGINA WEB
# ==============================================================================
st.set_page_config(page_title="selettore materiale", layout="wide")

st.title("🛡️ Selettore Materiale")
st.write("Filtra il database in tempo reale selezionando solo le feature che ti interessano.")


# ==============================================================================
# FUNZIONE DI PULIZIA GENERICA PER QUALSIASI COLONNA NUMERICA
# ==============================================================================
def pulisci_e_forza_numero(series):
    """Sostituisce le virgole con i punti ed estrae i valori numerici puliti"""
    str_series = series.astype(str).str.replace(',', '.', regex=False)
    str_series = str_series.str.extract(r'([-+]?\d*\.\d+|\d+)')[0]
    return pd.to_numeric(str_series, errors='coerce')


# ==============================================================================
# CARICAMENTO DATABASE (PANDAS CACHED)
# ==============================================================================
@st.cache_data
def carica_e_prepara_database(percorso_csv):
    try:
        df = pd.read_csv(percorso_csv, sep=';')
        return df
    except Exception as e:
        st.error(f"Errore nel caricamento del file CSV: {e}")
        return None

cartella_corrente = os.path.dirname(__file__)
percorso_csv_assoluto = os.path.join(cartella_corrente, "materiali_tecasint.csv")

df_originale = carica_e_prepara_database(percorso_csv_assoluto)

if df_originale is not None:
    # Creiamo una copia di lavoro del database
    df_filtrato = df_originale.copy()
    
    # ==============================================================================
    # 1. SIDEBAR: PARAMETRI CRITICI (FISSA E SEMPRE ATTIVA)
    # ==============================================================================
    st.sidebar.header("🎯 Parametri Termo-Meccanici")
    
    # Filtro Temperatura di esercizio
    col_temp = 'Temperatura di esercizio a lungo termine [°C]'
    if col_temp in df_filtrato.columns:
        df_filtrato[col_temp] = pulisci_e_forza_numero(df_filtrato[col_temp])
        temp_req = st.sidebar.number_input("Temperatura minima a lungo termine [°C]", min_value=0, max_value=400, value=23, step=5)
        df_filtrato = df_filtrato[(df_filtrato[col_temp] >= temp_req) | (df_filtrato[col_temp].isna())]

    # Filtro Meccanico (Trazione vs Compressione)
    tipo_sollecitazione = st.sidebar.radio("Tipo di Sollecitazione Meccanica", ["Trazione", "Compressione"])
    col_traz = 'Resistenza a trazione [MPa]'
    col_compr = 'Resistenza a compressione 1%/2% [MPa]'
    
    col_meccanica_scelta = col_compr if tipo_sollecitazione == "Compressione" else col_traz
    
    if col_meccanica_scelta in df_filtrato.columns:
        df_filtrato[col_meccanica_scelta] = pulisci_e_forza_numero(df_filtrato[col_meccanica_scelta])
        
        # Sforzo geometrico automatico
        usa_geometria = st.sidebar.checkbox("Calcola Sforzo Target da Forza/Sezione", value=False)
        if usa_geometria:
            carico_n = st.sidebar.number_input("Carico applicato [Newton]", min_value=0.0, value=1000.0)
            sezione_mm2 = st.sidebar.number_input("Sezione resistente [mm²]", min_value=1.0, value=500.0)
            sforzo_target = (carico_n / sezione_mm2) * 3
            st.sidebar.info(f"Sforzo limite applicato: **{sforzo_target:.2f} MPa** (Sicurezza x3)")
        else:
            sforzo_target = st.sidebar.number_input("Inserisci Sforzo Limite direttamente [MPa]", min_value=0.0, value=0.0)
            
        if sforzo_target > 0:
            df_filtrato = df_filtrato[(df_filtrato[col_meccanica_scelta] >= sforzo_target) | (df_filtrato[col_meccanica_scelta].isna())]


    # ==============================================================================
    # 2. CORPO CENTRALE: IL FILTRO DINAMICO DELLE ALTRE 30 FEATURE (SENZA SEPARATI CONTROLLI)
    # ==============================================================================
    st.subheader("🧩 Filtri Extra a Scelta")
    st.write("Seleziona una o più colonne dal menu per applicare restrizioni specifiche. L'applicazione adatterà i controlli da sola.")
    
    # Escludiamo le colonne principali già gestite nella sidebar per non fare doppioni
    colonne_escluse = ['Denominazione del materiale', 'Denominazione chimica', col_temp, col_traz, col_compr]
    colonne_disponibili_extra = [c for c in df_originale.columns if c not in colonne_escluse]
    
    # Il multi-selettore magico: l'utente sceglie cosa vuole filtrare tra le restanti 30 colonne
    feature_scelte = st.multiselect("Quali proprietà vuoi vincolare?", options=colonne_disponibili_extra)
    
    if feature_scelte:
        st.write("---")
        # Generiamo dinamicamente colonne grafiche nel browser in base a quante feature ha scelto l'utente
        colonne_layout = st.columns(len(feature_scelte))
        
        # IL CICLO DINAMICO: Controlla le colonne scelte senza scrivere codice per ognuna!
        for i, col_name in enumerate(feature_scelte):
            with colonne_layout[i]:
                # Capisce da solo se la colonna è numerica o di testo (es. controlla se contiene unità di misura o simboli comuni)
                è_numerica = df_originale[col_name].dtype in ['float64', 'int64'] or any(sym in col_name for sym in ['[', ']', '°C', 'MPa', 'g/cm³', '%', 'V', 'K⁻¹'])
                
                if è_numerica:
                    # Se è numerica, pulisce i dati e crea un box per inserire il valore soglia
                    df_filtrato[col_name] = pulisci_e_forza_numero(df_filtrato[col_name])
                    
                    # Chiede se si vuole impostare un limite minimo o massimo per questa feature
                    tipo_limite = st.selectbox(f"Filtro per {col_name}", ["Minimo (≥)", "Massimo (≤)"], key=f"type_{col_name}")
                    valore_soglia = st.number_input(f"Valore per {col_name}", value=0.0, key=f"val_{col_name}")
                    
                    if tipo_limite == "Minimo (≥)":
                        df_filtrato = df_filtrato[(df_filtrato[col_name] >= valore_soglia) | (df_filtrato[col_name].isna())]
                    else:
                        df_filtrato = df_filtrato[(df_filtrato[col_name] <= valore_soglia) | (df_filtrato[col_name].isna())]
                else:
                    # Se è di testo (es. 'Additivi' o 'Infiammabilità'), crea una casella di testo libero
                    testo_cercato = st.text_input(f"Cerca testo in {col_name} (es. PTFE, V0)", value="", key=f"txt_{col_name}")
                    if testo_cercato:
                        df_filtrato = df_filtrato[df_filtrato[col_name].astype(str).str.contains(testo_cercato, case=False, na=False)]
        st.write("---")


    # ==============================================================================
    # 3. REPORT FINALE DEI RISULTATI
    # ==============================================================================
    st.subheader("📊 Risultati Screening Database")
    
    if not df_filtrato.empty:
        st.success(f"Trovati **{len(df_filtrato)}** materiali corrispondenti ai criteri attivi!")
        
        # Colonne base fisse da mostrare per la vista rapida
        colonne_vista_rapida = ['Denominazione del materiale', 'Denominazione chimica', 'Additivi']
        if col_temp in df_filtrato.columns: colonne_vista_rapida.append(col_temp)
        colonne_vista_rapida.append(col_meccanica_scelta)
        
        # Aggiungiamo alla tabella anche le colonne extra che l'utente ha voluto filtrare
        for c in feature_scelte:
            if c not in colonne_vista_rapida:
                colonne_vista_rapida.append(c)
                
        colonne_finali_visibili = [c for c in colonne_vista_rapida if c in df_filtrato.columns]
        
        # Mostra la tabella dei risultati filtrati
        st.dataframe(df_filtrato[colonne_finali_visibili], use_container_width=True)
        
        # Espandibile per vedere proprio tutto l'Excel completo
        with st.expander("👀 Sfoglia l'intero database completo (Tutte le 30+ feature)"):
            st.dataframe(df_filtrato, use_container_width=True)
    else:
        st.error("❌ Nessun materiale a database soddisfa contemporaneamente tutte le condizioni inserite. Prova ad alleggerire le restrizioni.")
