
import streamlit as st  # Importation de la bibliothèque Streamlit
import fitz  # Importation de la bibliothèque PyMuPDF (fitz)
import ollama  # Importation de la bibliothèque ollama


st.set_page_config(page_title="NotarIA", page_icon="⚖️")


hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


# Titre principal de l'application
st.title('Assistant Juridique IA')

# Texte de description
st.write("Cette application permet d'uploader un fichier PDF et de générer un résumé juridique.")

# Module pour l'upload du fichier PDF
uploaded_file = st.file_uploader("Importer un fichier PDF", type=["pdf"])

# Vérification si un fichier a été uploadé
if uploaded_file is not None:
    st.info(f"Fichier détecté : **{uploaded_file.name}**")
    
    # Création de l'animation de chargement (le code à l'intérieur s'exécute pendant que la roue tourne)
    with st.spinner("Lecture et analyse juridique en cours par l'IA locale..."):
        
        # 1. Extraction du texte de TOUTES les pages du PDF
        document = fitz.open(stream=uploaded_file.read(), filetype='pdf')
        text = ""
        for page in document:
            text += page.get_text("text") + "\n"
        document.close()

        
                # 2. Interrogation de l'IA locale (Technique du prompt fusionné)
        consigne_stricte = f"""
        Tu es un assistant juridique expert. Ton unique but est de lire l'arrêt ci-dessous et d'en extraire une fiche d'arrêt très claire.
        Tu DOIS OBLIGATOIREMENT structurer ta réponse avec EXACTEMENT ces trois titres en gras, sans rien écrire avant :

        **1. Faits et Procédure :**
        **2. Problème de Droit :**
        **3. Solution de la Cour :**

        Voici le texte de l'arrêt à analyser :
{text}
"""

        response = ollama.chat(
            model='llama3.1',
            messages=[
                {'role': 'user', 'content': consigne_stricte}
            ]
        )
        
    #st.balloons() # L'effet waouh caché de Streamlit mdrr
    
    st.success("Analyse terminée avec succès !")
    
    st.subheader("Synthèse de l'arrêt")
    st.write(response['message']['content'])
    
else:
    # Message par défaut quand aucun fichier n'est mis
    st.warning("Veuillez importer un fichier PDF dans la zone ci-dessus pour commencer l'analyse.")
