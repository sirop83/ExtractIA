
import streamlit as st  # Importation de la bibliothèque Streamlit
import fitz  # Importation de la bibliothèque PyMuPDF (fitz)
import ollama  # Importation de la bibliothèque ollama

# Titre principal de l'application
st.title('Assistant Juridique IA')

# Texte de description
st.write("Cette application permet d'uploader un fichier PDF et de générer un résumé juridique.")

# Module pour l'upload du fichier PDF
uploaded_file = st.file_uploader("Importer un fichier PDF", type=["pdf"])

# Vérification si un fichier a été uploadé
if uploaded_file is not None:
    st.write("Fichier PDF uploadé avec succès.")
    # Afficher le nom du fichier
    st.write(f"Nom du fichier: {uploaded_file.name}")
    
    # Lire le document PDF avec PyMuPDF
    document = fitz.open(stream=uploaded_file.read(), filetype='pdf')  # Ouvrir le fichier PDF uploadé
    
    # Sélectionner la première page du document
    first_page = document.load_page(0)  # Charger la première page (index 0)
    
    # Extraire le texte brut de la première page
    text = first_page.get_text("text")  # Extraction du texte en format brut
    
    # Fermer le document
    document.close()  # Important : fermer le document pour libérer les ressources
    
       # Utiliser ollama pour envoyer le texte au modèle mistral
    response = ollama.chat(
        model='mistral',
        messages=[
            {
                'role': 'system', 
                'content': 'Tu es un expert juridique français. Fais un résumé strict de ce texte en une ou deux phrases maximum. Tu dois IMPÉRATIVEMENT répondre en français.'
            },
            {
                'role': 'user', 
                'content': text
            }
        ]
    )

    # Afficher le résultat sur l'interface avec une belle boîte verte
    st.success(response['message']['content'])
