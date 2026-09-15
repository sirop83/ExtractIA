import fitz  # Importation de la bibliothèque PyMuPDF (fitz)

# Chemin du fichier PDF à ouvrir
pdf_path = 'data/arret.pdf'

# Ouvrir le document PDF
document = fitz.open(pdf_path)  # Utilisation de fitz pour ouvrir le PDF

# Sélectionner la première page du document
first_page = document.load_page(0)  # Charger la première page (index 0)

# Extraire le texte brut de la première page
text = first_page.get_text("text")  # Extraction du texte en format brut

# Afficher le texte extrait dans la console
print(text)  # Utiliser print() pour afficher le texte

# Fermer le document
document.close()  # Important : fermer le document pour libérer les ressources