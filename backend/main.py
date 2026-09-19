import os
import shutil
import asyncio
import fitz
import sqlite3
import ollama
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="NotarIA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. BASE DE DONNÉES & FICHIERS ---
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def init_db():
    conn = sqlite3.connect("notaria.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dossiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            date_creation TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dossier_id INTEGER,
            nom_fichier TEXT NOT NULL,
            chemin_fichier TEXT NOT NULL,
            type_detecte TEXT,
            synthese TEXT,
            date_ajout TEXT NOT NULL,
            FOREIGN KEY (dossier_id) REFERENCES dossiers (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

def get_db_connection():
    conn = sqlite3.connect("notaria.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- 2. VÉRIFICATION D'ÉTAT IA ---
@app.get("/api/health")
async def health_check():
    try:
        client = ollama.AsyncClient()
        await client.list()
        return {"status": "online"}
    except Exception:
        raise HTTPException(status_code=503, detail="Ollama injoignable")

# --- 3. ROUTES DOSSIERS & DOCUMENTS ---
@app.get("/api/dossiers")
def lister_dossiers():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT d.id, d.nom, d.date_creation, COUNT(doc.id) as docs 
        FROM dossiers d 
        LEFT JOIN documents doc ON d.id = doc.dossier_id 
        GROUP BY d.id 
        ORDER BY d.id DESC
    """
    dossiers = cursor.execute(query).fetchall()
    conn.close()
    return [{"id": row["id"], "nom": row["nom"], "date": row["date_creation"], "docs": row["docs"]} for row in dossiers]

@app.post("/api/dossiers")
def creer_dossier(nom: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    date_jour = datetime.now().strftime("%d %b %Y")
    cursor.execute("INSERT INTO dossiers (nom, date_creation) VALUES (?, ?)", (nom, date_jour))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"status": "success", "id": new_id, "nom": nom, "date": date_jour}

@app.get("/api/dossiers/{dossier_id}")
def get_dossier(dossier_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    dossier = cursor.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,)).fetchone()
    documents = cursor.execute("SELECT * FROM documents WHERE dossier_id = ?", (dossier_id,)).fetchall()
    conn.close()
    return {
        "dossier": dict(dossier) if dossier else None,
        "documents": [dict(doc) for doc in documents]
    }

@app.delete("/api/dossiers/{dossier_id}")
def supprimer_dossier(dossier_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("DELETE FROM dossiers WHERE id = ?", (dossier_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/documents/{document_id}")
def supprimer_document(document_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    doc = cursor.execute("SELECT chemin_fichier FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc:
        nom_fichier = doc["chemin_fichier"].split("/")[-1]
        chemin_physique = os.path.join(UPLOAD_DIR, nom_fichier)
        if os.path.exists(chemin_physique): os.remove(chemin_physique)
            
    cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/documents")
def sauvegarder_document(dossier_id: int = Form(...), type_detecte: str = Form(...), synthese: str = Form(...), file: UploadFile = File(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    nom_fichier_propre = file.filename.replace(" ", "_")
    file_path = os.path.join(UPLOAD_DIR, nom_fichier_propre)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    date_ajout = datetime.now().strftime("%d %b %Y")
    url_fichier = f"http://localhost:8000/uploads/{nom_fichier_propre}"
    
    cursor.execute("INSERT INTO documents (dossier_id, nom_fichier, chemin_fichier, type_detecte, synthese, date_ajout) VALUES (?, ?, ?, ?, ?, ?)", 
                   (dossier_id, file.filename, url_fichier, type_detecte, synthese, date_ajout))
    conn.commit()
    conn.close()
    return {"status": "success"}

# --- 4. ROUTE IA (Méthode de marquage par phrase) ---
@app.post("/api/analyse")
async def analyser_document(request: Request, file: UploadFile = File(...)):
    client = ollama.AsyncClient()
    try:
        file_bytes = await file.read()
        document = fitz.open(stream=file_bytes, filetype='pdf')
        
        text = ""
        for num, page in enumerate(document):
            lignes = page.get_text("text").split('\n')
            for ligne in lignes:
                if ligne.strip():
                    # TON SYSTÈME : On colle la balise de page devant chaque phrase !
                    text += f"[Page {num + 1}] {ligne.strip()}\n"
        document.close()

        if not text.strip(): raise HTTPException(status_code=400, detail="Document scanné détecté.")

        prompt_trieur = f"Analyse ce texte et détermine sa nature. Tu dois répondre UNIQUEMENT par UN SEUL de ces mots-clés : ARRET, VENTE, BAIL, STATUTS, AUTRE.\nTexte : {text[:4000]}"
        if await request.is_disconnected(): raise asyncio.CancelledError()

        reponse_trieur = await client.chat(model='qwen2.5:14b', messages=[{'role': 'user', 'content': prompt_trieur}])
        type_doc = reponse_trieur['message']['content'].strip().upper()

        if "ARRET" in type_doc:
            consigne = """**1. Faits (qualifiés juridiquement) :**\n- [Insérer la situation factuelle] (Page X)\n\n**2. Procédure :**\n- [Insérer les étapes] (Page X)\n\n**3. Thèses en présence :**\n- [Insérer les arguments] (Page X)\n\n**4. Problème de droit :**\n- [Insérer la question de droit] (Page X)\n\n**5. Solution :**\n- [Insérer le sens de la décision] (Page X)"""
        elif "VENTE" in type_doc:
            consigne = """**1. Identification des parties :**\n- [Vendeurs, acquéreurs] (Page X)\n\n**2. Désignation du bien :**\n- [Adresse, références cadastrales] (Page X)\n\n**3. Conditions financières :**\n- [Prix de vente] (Page X)"""
        elif "BAIL" in type_doc:
            consigne = """**1. Identification des parties :**\n- [Bailleur et Preneur] (Page X)\n\n**2. Locaux et Destination :**\n- [Adresse, désignation] (Page X)\n\n**3. Durée du bail :**\n- [Durée totale] (Page X)\n\n**4. Conditions financières :**\n- [Loyer, répartition] (Page X)"""
        elif "STATUTS" in type_doc:
            consigne = """**1. Forme et Dénomination :**\n- [Forme juridique, dénomination] (Page X)\n\n**2. Siège et Objet social :**\n- [Adresse complète] (Page X)\n\n**3. Capital social :**\n- [Montant, actions] (Page X)"""
        else:
            consigne = "**1. Résumé général :**\n- [Résumé des points clés] (Page X)"

        # LE PROMPT EXACT DE TON STREAMLIT (adapté à la balise [Page X])
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
6. SOURÇAGE IMPÉRATIF : CHAQUE puce DOIT se terminer par (Page X). Pour déterminer (X), tu DOIS OBLIGATOIREMENT utiliser le numéro indiqué dans la balise "[Page X]" qui précède le texte extrait. Ne numérote pas de façon séquentielle.

GABARIT OBLIGATOIRE :
{consigne}"""
            },
            {'role': 'user', 'content': f"Voici le document à analyser :\n\n{text}"}
        ]
        
        if await request.is_disconnected(): raise asyncio.CancelledError()
            
        stream = await client.chat(model='qwen2.5:14b', messages=messages_expert, options={'temperature': 0.0, 'num_ctx': 32768}, stream=True)
        
        texte_brut = ""
        async for chunk in stream:
            if await request.is_disconnected(): raise asyncio.CancelledError()
            texte_brut += chunk['message']['content']
        
        if "**1. " in texte_brut: texte_brut = texte_brut[texte_brut.find("**1. "):]
        elif "1. " in texte_brut: texte_brut = texte_brut[texte_brut.find("1. "):]

        return {"statut": "succès", "fichier": file.filename, "type_detecte": type_doc, "synthese": texte_brut}

    except asyncio.CancelledError:
        print(f"🛑 Annulation de l'IA pour : {file.filename}")
        raise HTTPException(status_code=499, detail="Annulation Client")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))