import fitz  # Importation de la bibliothèque PyMuPDF (fitz)
import ollama  # Importation de la bibliothèque ollama

# Chemin du fichier PDF à ouvrir
pdf_path = 'data/arret.pdf'

# Ouvrir le document PDF
document = fitz.open(pdf_path)  # Utilisation de fitz pour ouvrir le PDF

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
            'content': 'Tu es un expert juridique français. Fais un résumé de ce texte en une ou deux phrases maximum. Tu dois IMPÉRATIVEMENT répondre en français.'
        },
        {
            'role': 'user', 
            'content': text
        }
    ]
)

# Afficher uniquement le texte de la réponse générée par mistral
print(response['message']['content'])
