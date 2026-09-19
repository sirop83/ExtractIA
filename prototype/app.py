import streamlit as st
import fitz  # PyMuPDF
import ollama
import base64

st.set_page_config(page_title="NotarIA", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")

custom_css = """
<style>
    /* Cacher le menu et le footer de base de Streamlit */
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;}
    
    /* Remonter tout l'affichage vers le haut */
    .block-container {
        padding-top: 1rem; 
        padding-bottom: 1rem;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- 1. MÉMOIRE DE L'APPLICATION ---
if 'page_actuelle' not in st.session_state:
    st.session_state.page_actuelle = "Fiche" 

if 'onglet_actif' not in st.session_state:
    st.session_state.onglet_actif = None

# --- 2. MENU LATÉRAL (SIDEBAR) ---
with st.sidebar:
    st.title("⚖️ NotarIA")
    st.markdown("---")
    
    if st.button("📖 Fiche d'arrêt (Cassation)", use_container_width=True):
        st.session_state.page_actuelle = "Fiche"
    if st.button("📝 Audit de Contrat", use_container_width=True):
        st.session_state.page_actuelle = "Audit"
    if st.button("⚙️ Paramètres", use_container_width=True):
        st.session_state.page_actuelle = "Parametres"
    
    st.markdown("---")
    
    try:
        modeles_dispos = ollama.list()
        serveur_en_ligne = True
    except Exception:
        serveur_en_ligne = False

    if serveur_en_ligne:
        st.success("🟢 Serveur local : En ligne")
        if 'qwen2.5:14b' in str(modeles_dispos):
            st.info("🧠 Modèle : qwen2.5:14b (Prêt)")
        else:
            st.warning("⚠️ Llama 3.1 non détecté")
    else:
        st.error("🔴 Serveur local : Hors ligne")
        st.caption("L'application Ollama est fermée.")

# --- 4. AFFICHAGE DES PAGES ---
if st.session_state.page_actuelle == "Fiche":
    
    st.title("Analyse Juridique")
    st.write("Glissez n'importe quel document PDF (Arrêt, Bail, Vente, Statuts).")

    fichier_actuels = st.file_uploader("Importer un ou plusieurs fichiers PDF", type=["pdf"], accept_multiple_files=True)

if fichier_actuels: 
    noms_fichiers = [file.name for file in fichier_actuels]
    
    # Sécurité si l'onglet actif n'est plus dans la liste (ex: on supprime un fichier)
    if st.session_state.onglet_actif not in noms_fichiers:
        st.session_state.onglet_actif = noms_fichiers[0]

    # --- CRÉATION DES FAUX ONGLETS ---
    colonnes_onglets = st.columns(len(noms_fichiers))
    for index, nom in enumerate(noms_fichiers):
        with colonnes_onglets[index]:
            # On met le bouton en rouge (primary) si c'est l'onglet actif, sinon secondaire
            type_bouton = "primary" if st.session_state.onglet_actif == nom else "secondary"
            if st.button(nom, use_container_width=True, type=type_bouton):
                st.session_state.onglet_actif = nom
                st.rerun()

    st.markdown("---")

    # On isole le fichier sélectionné
    fichier_actuel = next(f for f in fichier_actuels if f.name == st.session_state.onglet_actif)
    
    # --- AFFICHAGE DU CONTENU ---
    col_gauche, col_droite = st.columns([1, 1])
    
    with col_gauche:
        st.subheader("📄 Document Original")
        base64_pdf = base64.b64encode(fichier_actuel.getvalue()).decode('utf-8')
    
        # On remet ton lecteur natif parfait
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}#view=FitH" width="100%" height="800" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
    with col_droite:
            st.info(f"Fichier détecté : **{fichier_actuel.name}**")
            memory_key = f"analyse{fichier_actuel.name}_{fichier_actuel.size}"
        
            # L'ANALYSE NE SE LANCE PLUS TOUTE SEULE
            if memory_key not in st.session_state:
                st.warning("L'IA est prête à lire ce document.")
                
                # On ajoute un bouton pour déclencher l'IA manuellement
                if st.button(f"🚀 Lancer l'analyse de {fichier_actuel.name}", key=f"btn_{fichier_actuel.name}"):
                    
                    document = fitz.open(stream=fichier_actuel.read(), filetype='pdf')
                    text = ""
                    for num, page in enumerate(document):
                        # On récupère le texte et on le découpe ligne par ligne
                        lignes = page.get_text("text").split('\n')
                        for ligne in lignes:
                            if ligne.strip():  # On ignore les lignes vides pour ne pas surcharger
                                # On colle la balise de page devant chaque phrase !
                                text += f"[Page {num + 1}] {ligne}\n"
                    document.close()
                    
                    if text.strip() == "":
                        st.error("⚠️ Document scanné détecté (OCR non disponible).")
                        st.stop()

                    with st.spinner("Détection automatique du type de document..."):
                        prompt_trieur = f"Analyse ce texte et détermine sa nature. Tu dois répondre UNIQUEMENT par UN SEUL de ces mots-clés : ARRET, VENTE, BAIL, STATUTS, AUTRE.\nTexte : {text[:4000]}"
                        reponse_trieur = ollama.chat(model='qwen2.5:14b', messages=[{'role': 'user', 'content': prompt_trieur}])
                        type_doc = reponse_trieur['message']['content'].strip().upper()

                    with st.spinner(f"Analyse en cours (Type détecté : {type_doc})..."):
                        
                        if "ARRET" in type_doc:
                            consigne = """**1. Faits (qualifiés juridiquement) :**
- [Insérer la situation factuelle initiale qui a amené au litige] (Page X)

**2. Procédure :**
- [Insérer les étapes et décisions rendues par les juridictions précédentes avant d'arriver à la Cour de cassation] (Page X)

**3. Thèses en présence :**
- [Insérer les arguments précis soulevés par le demandeur au pourvoi] (Page X)
- [Insérer la position retenue par la cour d'appel ou la partie adverse] (Page X)

**4. Problème de droit :**
- [Insérer la question de droit neutre, générale et abstraite posée à la Cour de cassation] (Page X)

**5. Solution :**
- [Insérer le sens de la décision finale : Cassation ou Rejet] (Page X)
- [Insérer l'explication et la règle de droit énoncée par la Cour pour juger] (Page X)"""
                        elif "VENTE" in type_doc:
                            consigne = """**1. Identification des parties :**
                                - [Vendeurs, acquéreurs, états civils et régimes matrimoniaux] (Page X)

                                **2. Désignation du bien :**
                                - [Adresse, références cadastrales, surface et lots de copropriété] (Page X)

                                **3. Conditions financières :**
                                - [Prix de vente, honoraires et versement du séquestre] (Page X)
                                - [Modalités de financement et conditions suspensives de prêt] (Page X)

                                **4. Urbanisme et charges :**
                                - [Droit de préemption, servitudes et diagnostics techniques] (Page X)"""
                        elif "BAIL" in type_doc:
                            consigne = """**1. Identification des parties :**
- [Insérer l'identité complète du Bailleur et du Preneur] (Page X)

**2. Locaux et Destination :**
- [Insérer l'adresse et la désignation précise des locaux loués] (Page X)
- [Insérer la destination du bail / l'usage autorisé des locaux] (Page X)

**3. Durée du bail :**
- [Insérer la durée totale, la date d'effet et les conditions de renouvellement/congé] (Page X)

**4. Conditions financières :**
- [Insérer le montant du loyer, la périodicité et l'indice de révision] (Page X)
- [Insérer la répartition des charges et des impôts comme la taxe foncière] (Page X)

**5. Garanties :**
- [Insérer le montant du dépôt de garantie et les éventuelles cautions] (Page X)"""
                            
                        elif "STATUTS" in type_doc:
                            consigne = """**1. Forme et Dénomination :**
- [Insérer la forme juridique (ex: SCI, SAS, SARL) et la dénomination sociale] (Page X)

**2. Siège et Objet social :**
- [Insérer l'adresse complète du siège social] (Page X)
- [Insérer le résumé principal de l'objet social] (Page X)

**3. Capital social :**
- [Insérer le montant du capital et le nombre de parts/actions] (Page X)
- [Insérer l'identité des associés principaux et leurs apports/tantièmes] (Page X)

**4. Direction et Administration :**
- [Insérer l'identité du ou des premiers dirigeants (Président, Gérant, etc.)] (Page X)"""

                        else:
                            consigne = "**1. Résumé général :**\n- [Insérer un résumé des points clés du document] (Page X)\n\n**2. Points d'attention :** \n- [Insérer les clauses particulières ou risques potentiels] (Page X)"

                        messages_expert = [
                            {
                                'role': 'system',
                                'content': f"""Tu es un robot copiste sans aucune créativité. 
RÈGLES ABSOLUES :
1. Tu dois RECOPIER EXACTEMENT le gabarit ci-dessous.
2. Remplace le texte entre crochets [...] UNIQUEMENT par les informations demandées, extraites strictement des faits du texte.
3. RÈGLE ANTI-VIDE : Si une information est absente, laissée en blanc (pointillés) ou s'il s'agit d'un modèle non rempli, écris explicitement "Non renseigné" à la place.
4. N'ajoute AUCUN texte en dehors du gabarit.
5. Tu dois rédiger tes réponses sous forme de liste à puces (-).
6. SOURÇAGE IMPÉRATIF : CHAQUE puce DOIT se terminer par (Page X). Pour déterminer (X), tu DOIS OBLIGATOIREMENT utiliser le numéro indiqué dans la balise "--- DÉBUT DE LA PAGE X ---" qui précède le texte extrait. Ne numérote pas de façon séquentielle.

GABARIT OBLIGATOIRE :
{consigne}"""
                            },
                            {'role': 'user', 'content': f"Voici le document à analyser :\n\n{text}"}
                        ]
                        
                        reponse_expert = ollama.chat(model='qwen2.5:14b', messages=messages_expert, options={'temperature': 0.0, 'num_ctx': 32768})
                        texte_brut = reponse_expert['message']['content']
                        
                        if "**1. " in texte_brut:
                            texte_brut = texte_brut[texte_brut.find("**1. "):]
                        elif "1. " in texte_brut:
                            texte_brut = texte_brut[texte_brut.find("1. "):]
                        
                        # Sauvegarde en mémoire
                        st.session_state[memory_key] = texte_brut
                        st.session_state[f"type_{memory_key}"] = type_doc
                        
                        # On rafraîchit la page pour faire disparaître le bouton et afficher la synthèse
                        st.rerun()

            # SI L'ANALYSE A DÉJÀ ÉTÉ FAITE, ON AFFICHE LE RÉSULTAT
            else:
                resultat_ia = st.session_state[memory_key]
                type_detecte = st.session_state[f"type_{memory_key}"]
                
                st.success(f"Analyse terminée (Document reconnu : **{type_detecte}**)")
                st.subheader("Synthèse")
                st.write(resultat_ia)

                st.download_button("📥 Télécharger la synthèse", data=resultat_ia.replace("**", ""), file_name=f"Synthese_{fichier_actuel.name}.txt", mime="text/plain", key=f"dl_{st.session_state.onglet_actif}")