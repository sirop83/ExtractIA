import os
import shutil
import asyncio
import fitz
import sqlite3
import ollama
import pytesseract
from PIL import Image
import pymupdf4llm
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

# --- 2. VÉRIFICATION D'ÉTAT IA ET EXTRACTION HYBRIDE ---
@app.get("/api/health")
async def health_check():
    try:
        client = ollama.AsyncClient()
        await client.list()
        return {"status": "online"}
    except Exception:
        raise HTTPException(status_code=503, detail="Ollama injoignable")

def extraire_chunks_pdf(file_bytes, pages_par_chunk=3):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    chunks = []
    chunk_actuel = ""
    texte_derniere_page = "" 
    
    for num, page in enumerate(doc):
        texte_test = page.get_text("text").strip()
        
        if len(texte_test) < 50:
            print(f"👀 Page {num + 1} scannée détectée. Lancement de l'OCR (Tesseract)...")
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            texte_page = pytesseract.image_to_string(img, lang="fra").strip()
        else:
            print(f"📄 Page {num + 1} numérique détectée. Extraction Markdown (pymupdf4llm)...")
            texte_page = pymupdf4llm.to_markdown(doc, pages=[num]).strip()

        texte_formate_page = f"\n\n=== DÉBUT PAGE {num + 1} ===\n"
        texte_formate_page += texte_page + "\n"
        texte_formate_page += f"=== FIN PAGE {num + 1} ===\n"
        
        chunk_actuel += texte_formate_page
        texte_derniere_page = texte_formate_page 
        
        if (num + 1) % pages_par_chunk == 0 or (num + 1) == len(doc):
            if chunk_actuel.strip():
                chunks.append(chunk_actuel)
            
            if (num + 1) != len(doc):
                chunk_actuel = texte_derniere_page 
            else:
                chunk_actuel = ""
            
    doc.close()
    return chunks

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

# --- 4. FONCTION AGENT ASYNCHRONE ---
async def executer_agent(client, mission_config: dict, brouillon: str):
    prompt_agent = f"""Tu es un clerc de notaire expert.
Ta mission STRICTE : {mission_config['mission']}

RÈGLES ABSOLUES :
1. Base-toi UNIQUEMENT sur les notes extraites fournies ci-dessous. N'invente rien. Si l'information est introuvable, écris "Non renseigné".
2. GESTION DES CONTRADICTIONS : Si les notes contiennent un historique (plusieurs adresses, plusieurs gérants, anciennes et nouvelles répartitions), tu dois analyser le texte pour déduire la situation ACTUELLE ET FINALE (cherche des mentions comme "nouveau siège", "démission", "cession", etc.). Ne te fie pas aveuglément aux numéros de pages, utilise ton intelligence juridique.
3. Tu dois respecter EXACTEMENT ce format de réponse (recopie le gabarit sans rien ajouter autour) :
{mission_config['gabarit']}
4. SOURÇAGE IMPÉRATIF : Chaque information que tu remplis doit se terminer par la balise exacte (Page X) correspondant à l'endroit où tu as trouvé l'information retenue dans les notes.

Notes brutes extraites du document :
{brouillon}"""

    reponse = await client.chat(
        model='qwen2.5:14b',
        messages=[{"role": "user", "content": prompt_agent}],
        options={'temperature': 0.0, 'num_ctx': 16384}
    )
    return reponse['message']['content'].strip()

# --- 5. ROUTE IA PRINCIPALE (MAP + MULTI-AGENTS REDUCE) ---
@app.post("/api/analyse")
async def analyser_document(request: Request, file: UploadFile = File(...)):
    client = ollama.AsyncClient()
    try:
        # 1. Découpage du PDF (Chunks)
        file_bytes = await file.read()
        chunks = extraire_chunks_pdf(file_bytes, pages_par_chunk=3)

        if not chunks: 
            raise HTTPException(status_code=400, detail="Document scanné détecté.")

        # 2. Classification
        prompt_trieur = f"Analyse cet extrait et détermine sa nature. Tu dois répondre UNIQUEMENT par UN SEUL de ces mots-clés : ARRET, VENTE, BAIL, STATUTS, AUTRE.\nTexte : {chunks[0][:4000]}"
        if await request.is_disconnected(): raise asyncio.CancelledError()

        reponse_trieur = await client.chat(model='qwen2.5:14b', messages=[{'role': 'user', 'content': prompt_trieur}])
        type_doc = reponse_trieur['message']['content'].strip().upper()

        # Configuration des prompts DÉTAILLÉS de l'étape MAP (Aspiration exhaustive)[cite: 19]
        if "ARRET" in type_doc:
            mission_brouillon = "Extrais de manière exhaustive et chronologique les faits matériels à l'origine du litige, les différentes étapes de la procédure judiciaire (jugement, appel, pourvoi), les arguments (thèses ou moyens) soulevés par les parties, le problème de droit posé à la cour, et la solution (décision) finale rendue par la juridiction."
        elif "VENTE" in type_doc:
            mission_brouillon = "Extrais de manière exhaustive toutes les informations concernant l'identité complète des vendeurs et acquéreurs (noms, prénoms, date de naissance, régime matrimonial), la désignation complète des biens immobiliers (adresse exacte, type de bien), les références cadastrales complètes (section, numéro, surface, lots de copropriété), et les conditions financières (prix de vente principal en chiffres et en lettres, modalités de paiement, frais)."
        elif "BAIL" in type_doc:
            mission_brouillon = "Extrais de manière exhaustive l'identité du Bailleur et du Preneur (Locataire), l'adresse complète et la désignation précise des locaux loués (y compris annexes et destination du bail), la durée totale du bail (date de prise d'effet et d'échéance), et les conditions financières complètes (montant du loyer principal, périodicité, provisions pour charges, dépôt de garantie)."
        elif "STATUTS" in type_doc:
            mission_brouillon = """Extrais de manière exhaustive toutes les mentions concernant :
- Dénominations sociales et Numéros SIREN
- Adresses de siège social
- Adresses des biens immobiliers (Copie l'intégralité des tableaux Markdown pour les références cadastrales, sections, surfaces et lots)
- Montants du capital social
- Identité complète des gérants
- Répartitions exactes des parts entre les associés
- Historiques de cession de parts (noms du cédant et cessionnaire, et le PRIX de cession en euros en chiffres ou en toutes lettres)
- Identité des notaires rédacteurs"""
        else:
            mission_brouillon = "Extrais les informations principales et pertinentes."

        # 3. ÉTAPE MAP : Création du brouillon exhaustif
        notes_globales = []
        for index, chunk in enumerate(chunks):
            if await request.is_disconnected(): raise asyncio.CancelledError()
            
            prompt_brouillon_exec = f"""
            Tu es un extracteur de données strict. Voici un extrait d'un document (Partie {index + 1}/{len(chunks)}). Les tableaux y sont formatés en Markdown.
            Mission : {mission_brouillon}
            Règle 1 : S'il y a un historique (ex: plusieurs adresses, gérants, répartitions, instances judiciaires), extrais TOUTES les versions trouvées de manière exhaustive.
            Règle 2 : Tu dois IMPÉRATIVEMENT sourcer chaque ligne extraite. Pour trouver le bon numéro de page, regarde la dernière balise === DÉBUT PAGE X === qui précède l'information. Ajoute (Page X) à la fin.
            
            Texte :
            {chunk}
            """
            
            reponse = await client.chat(
                model='qwen2.5:14b', 
                messages=[{"role": "user", "content": prompt_brouillon_exec}],
                options={'temperature': 0.0}
            )
            notes_globales.append(reponse['message']['content'])

        brouillon_complet = "\n".join(notes_globales)

        # 4. ÉTAPE REDUCE (MULTI-AGENTS) : Configuration des Agents Spécialisés avec frontières strictes
        agents_config = []
        if "STATUTS" in type_doc:
            agents_config = [
                {
                    "mission": "Identifie l'identité de la société. Cherche OBLIGATOIREMENT l'adresse du siège social la plus récente et le capital social final.",
                    "gabarit": "**1. Identification de la Société :**\n- Dénomination sociale : [Dénomination exacte] (Page X)\n- Forme juridique : [Forme, ex: SCI, SARL] (Page X)\n- Numéro SIREN et Greffe (RCS) : [SIREN, Ville du RCS] (Page X)\n- Siège social actuel (le plus récent) : [Adresse complète] (Page X)\n- Capital social : [Montant] (Page X)"
                },
                {
                    "mission": "Identifie la Représentation Légale actuelle. Si des gérants ont démissionné, ignore-les et indique UNIQUEMENT le ou les nouveaux gérants en exercice à la fin du document.",
                    "gabarit": "**2. Représentation Légale (Gérance) :**\n- Gérant(s) en exercice (le plus récent) : [Nom et Prénom] (Page X)"
                },
                {
                    "mission": "Identifie la répartition du capital et la liste des associés à la fin du document. S'il y a eu des cessions de parts successives, donne UNIQUEMENT la nouvelle répartition finale (la plus récente).",
                    "gabarit": "**3. Répartition du Capital / Associés actuels :**\n- Liste des associés actuels et détention : [Nom de l'associé : Nombre de parts en pleine propriété, nue-propriété ou usufruit] (Page X)"
                },
                {
                    "mission": "Identifie le patrimoine immobilier de la société. Cherche les adresses complètes, sections cadastrales, numéros de parcelles et numéros de lots de copropriété. (Les données peuvent se trouver dans des tableaux Markdown).",
                    "gabarit": "**4. Patrimoine Immobilier (Actif de la société) :**\n- Adresse du ou des biens immobiliers : [Adresse complète de l'ensemble immobilier] (Page X)\n- Références cadastrales et Lots : [Section, N°, Numéros des lots de copropriété] (Page X)"
                },
                {
                    "mission": "Retrace l'historique des mutations. S'il y a un ou plusieurs actes de cession de parts, trouve le Cédant (vendeur), le Cessionnaire (acheteur), le prix EXACT de la vente (qui peut être écrit en toutes lettres majuscules) et le nom du Notaire l'ayant reçu.",
                    "gabarit": "**5. Historique : Dernière mutation / Cession de parts (si présente) :**\n- Cédant (vendeur) et Cessionnaire (acheteur) : [Noms] (Page X)\n- Parts cédées et Prix de cession : [Nombre de parts, Montant en euros] (Page X)\n- Notaire ayant reçu l'acte : [Nom du notaire, Ville, Date] (Page X)"
                }
            ]
        elif "ARRET" in type_doc:
            agents_config = [
                {"mission": "Résume UNIQUEMENT les faits matériels à l'origine du litige (ce qui s'est passé avant le procès). Ne mentionne JAMAIS la procédure judiciaire (assignation, jugement, appel) ni la décision des juges dans cette section.", "gabarit": "**1. Faits (qualifiés juridiquement) :**\n- [Insérer la situation factuelle] (Page X)"},
                {"mission": "Retrace chronologiquement la procédure judiciaire (tribunal, cour d'appel, pourvoi) et résume les arguments (thèses/moyens) avancés par les parties.", "gabarit": "**2. Procédure :**\n- [Insérer les étapes judiciaires] (Page X)\n\n**3. Thèses en présence :**\n- [Insérer les arguments des parties] (Page X)"},
                {"mission": "Identifie la question de droit (le problème juridique) posée à la juridiction et la solution finale retenue (cassation, rejet, motifs de la décision).", "gabarit": "**4. Problème de droit :**\n- [Insérer la question de droit] (Page X)\n\n**5. Solution :**\n- [Insérer le sens de la décision] (Page X)"}
            ]
        elif "VENTE" in type_doc:
            agents_config = [
                {"mission": "Identifie formellement le(s) Vendeur(s) (Cédant) et l'Acquéreur(s) (Cessionnaire). Précise leurs noms, prénoms et éventuellement leur régime matrimonial si mentionné.", "gabarit": "**1. Identification des parties :**\n- [Vendeurs, acquéreurs, régime matrimonial] (Page X)"},
                {"mission": "Détaille la désignation complète du bien immobilier objet de la vente, incluant l'adresse précise, les références cadastrales (section, numéro) et les numéros de lots s'il s'agit d'une copropriété.", "gabarit": "**2. Désignation du bien :**\n- [Adresse exacte, références cadastrales, lots] (Page X)"},
                {"mission": "Extrais le prix de vente principal. Attention, le montant peut être exprimé en toutes lettres (ex: DEUX CENT MILLE EUROS) et/ou en chiffres. Indique uniquement le montant du prix.", "gabarit": "**3. Conditions financières :**\n- [Prix de vente en euros] (Page X)"}
            ]
        elif "BAIL" in type_doc:
            agents_config = [
                {"mission": "Identifie le Bailleur (propriétaire) et le Preneur (locataire).", "gabarit": "**1. Identification des parties :**\n- [Bailleur et Preneur] (Page X)"},
                {"mission": "Identifie l'adresse exacte des locaux loués, leur désignation (appartement, local commercial, dépendances) et la destination du bail (usage d'habitation, usage commercial, mixte).", "gabarit": "**2. Locaux et Destination :**\n- [Adresse, désignation, usage] (Page X)"},
                {"mission": "Identifie la durée totale du bail (avec date de début si possible), le montant exact du loyer (en chiffres ou en lettres), sa périodicité (mensuel, trimestriel), et le montant des charges ou du dépôt de garantie.", "gabarit": "**3. Durée du bail :**\n- [Durée totale et prise d'effet] (Page X)\n\n**4. Conditions financières :**\n- [Loyer, périodicité, charges, garantie] (Page X)"}
            ]
        else:
            agents_config = [{"mission": "Extraire les informations juridiques ou financières clés du document.", "gabarit": "**1. Résumé général :**\n- [Résumé des points clés] (Page X)"}]

        # Exécution en parallèle de tous les agents sur le brouillon
        taches_agents = [executer_agent(client, agent, brouillon_complet) for agent in agents_config]
        resultats = await asyncio.gather(*taches_agents)

        # Assemblage de la synthèse finale
        texte_brut = "\n\n".join(resultats)

        return {"statut": "succès", "fichier": file.filename, "type_detecte": type_doc, "synthese": texte_brut}

    except asyncio.CancelledError:
        print(f"🛑 Annulation de l'IA pour : {file.filename}")
        raise HTTPException(status_code=499, detail="Annulation Client")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))