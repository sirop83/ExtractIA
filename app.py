import streamlit as st
import fitz  # PyMuPDF
import ollama

st.set_page_config(page_title="NotarIA", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")

hide_st_style = """<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 1. MÉMOIRE DE L'APPLICATION ---
if 'page_actuelle' not in st.session_state:
    st.session_state.page_actuelle = "Fiche" # Page par défaut

# --- 2. MENU LATÉRAL (SIDEBAR) ---
with st.sidebar:
    st.title("⚖️ NotarIA")
    st.markdown("---")
    
    # Boutons de navigation stylisés
    if st.button("📖 Fiche d'arrêt (Cassation)", use_container_width=True):
        st.session_state.page_actuelle = "Fiche"
    if st.button("📝 Audit de Contrat", use_container_width=True):
        st.session_state.page_actuelle = "Audit"
    if st.button("⚙️ Paramètres", use_container_width=True):
        st.session_state.page_actuelle = "Parametres"
    
    st.markdown("---")
    
    try:
        # On tente de joindre le serveur
        modeles_dispos = ollama.list()
        serveur_en_ligne = True
    except Exception:
        # Si ça plante, c'est que le serveur est éteint
        serveur_en_ligne = False

    # Affichage propre selon le résultat
    if serveur_en_ligne:
        st.success("🟢 Serveur local : En ligne")
        # Astuce de pro : on convertit toute la réponse en texte pour chercher "mistral-nemo" 
        # sans se soucier de la structure complexe du dictionnaire
        if 'mistral-nemo' in str(modeles_dispos):
            st.info("🧠 Modèle : Mistral-Nemo (Prêt)")
        else:
            st.warning("⚠️ Llama 3.1 non détecté")
    else:
        st.error("🔴 Serveur local : Hors ligne")
        st.caption("L'application Ollama est fermée.")



# --- 4. AFFICHAGE DES PAGES ---
if st.session_state.page_actuelle == "Fiche":
    
    st.title("Analyse Juridique")
    st.write("Glissez n'importe quel document PDF (Arrêt, Bail, Vente, Statuts).")
    uploaded_file = st.file_uploader("Importer un fichier PDF", type=["pdf"])

    if uploaded_file is not None:
        st.info(f"Fichier détecté : **{uploaded_file.name}**")
        memory_key = f"analyse{uploaded_file.name}_{uploaded_file.size}"
        
        if memory_key not in st.session_state:
            # 1. Extraction du texte
            document = fitz.open(stream=uploaded_file.read(), filetype='pdf')
            text = "".join([page.get_text("text") + "\n" for page in document])
            document.close()
            
            if text.strip() == "":
                st.error("⚠️ Document scanné détecté (OCR non disponible).")
                st.stop()

            # --- ÉTAPE 1 : LE TRIEUR (ROUTER) ---
            with st.spinner("Détection automatique du type de document..."):
                prompt_trieur = f"""
Analyse ce texte et détermine sa nature. Tu dois répondre UNIQUEMENT par UN SEUL de ces mots-clés, sans aucune phrase :
ARRET (si c'est une décision de justice)
VENTE (si c'est un compromis ou promesse de vente)
BAIL (si c'est un contrat de location)
STATUTS (si ce sont des statuts de société)
AUTRE (si ce n'est rien de tout ça)

Texte : {text[:4000]} # On ne donne que le début pour aller vite
"""
                reponse_trieur = ollama.chat(model='mistral-nemo', messages=[{'role': 'user', 'content': prompt_trieur}])
                type_doc = reponse_trieur['message']['content'].strip().upper()

            # --- ÉTAPE 2 : L'EXPERT (PROMPTS SUR MESURE) ---
            with st.spinner(f"🧠 Analyse experte en cours (Type détecté : {type_doc})..."):
                
                # 1. On crée des gabarits "à trous" impossibles à ignorer
                if "ARRET" in type_doc:
                    consigne = "**1. Faits et Procédure :**\n[Insérer les points ici]\n\n**2. Problème de Droit :**\n[Insérer les points ici]\n\n**3. Solution de la Cour :**\n[Insérer les points ici]"
                elif "VENTE" in type_doc:
                    consigne = "**1. Désignation du bien :**\n[Insérer les points ici]\n\n**2. Prix et Frais :**\n[Insérer les points ici]\n\n**3. Conditions suspensives :**\n[Insérer les points ici]"
                elif "BAIL" in type_doc:
                    consigne = "**1. Locaux et Usage :**\n[Insérer les points ici]\n\n**2. Durée du bail :**\n[Insérer les points ici]\n\n**3. Loyer et Dépôt de garantie :**\n[Insérer les points ici]"
                elif "STATUTS" in type_doc:
                    consigne = "**1. Forme et Dénomination :**\n[Insérer les points ici]\n\n**2. Siège et Capital :**\n[Insérer les points ici]\n\n**3. Gérance/Présidence :**\n[Insérer les points ici]"
                else:
                    consigne = "**1. Résumé général :**\n[Insérer les points ici]\n\n**2. Points d'attention :**\n[Insérer les points ici]"

                # 2. Le System Prompt le force à être un "copiste"
                                # 2. Le System Prompt le force à être un "copiste" amoureux des listes à puces
                messages_expert = [
                    {
                        'role': 'system',
                        'content': f"""Tu es un robot copiste sans aucune créativité. 
RÈGLES ABSOLUES :
1. Tu dois RECOPIER EXACTEMENT le gabarit ci-dessous, mot pour mot.
2. Remplace [Insérer les points ici] UNIQUEMENT par des informations extraites du texte.
3. N'ajoute AUCUN texte avant ou après le gabarit, ne supprime AUCUN titre.
4. Tu dois IMPÉRATIVEMENT rédiger tes réponses sous forme de liste à puces (en utilisant des tirets "- ").

GABARIT OBLIGATOIRE :
{consigne}"""
                    },
                    {
                        'role': 'user',
                        'content': f"Voici le document à analyser :\n\n{text}"
                    }
                ]

                
                reponse_expert = ollama.chat(
                    model='mistral-nemo',
                    messages=messages_expert,
                    options={
                        'temperature': 0.0,
                        'num_ctx': 16384 
                    }
                )
                
                texte_brut = reponse_expert['message']['content']
                
                # 🪓 LA GUILLOTINE PYTHON (Sécurité)
                if "**1. " in texte_brut:
                    texte_brut = texte_brut[texte_brut.find("**1. "):]
                elif "1. " in texte_brut:
                    texte_brut = texte_brut[texte_brut.find("1. "):]
                
                st.session_state[memory_key] = texte_brut
                st.session_state[f"type_{memory_key}"] = type_doc




                
        # Affichage du résultat
        resultat_ia = st.session_state[memory_key]
        type_detecte = st.session_state[f"type_{memory_key}"]
        
        st.success(f"Analyse terminée (Document reconnu : **{type_detecte}**)")
        st.subheader("Synthèse")
        st.write(resultat_ia)

        st.download_button("📥 Télécharger la synthèse", data=resultat_ia.replace("**", ""), file_name=f"Synthese_{uploaded_file.name}.txt", mime="text/plain")
