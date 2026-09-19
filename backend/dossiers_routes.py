from fastapi import Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import shutil
import os
from main import app
from database import init_db, get_db_connection, UPLOAD_DIR

@app.on_event("startup")
def startup_event():
    init_db()

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

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
    
    return [
        {"id": row["id"], "nom": row["nom"], "date": row["date_creation"], "docs": row["docs"]} 
        for row in dossiers
    ]

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

@app.post("/api/documents")
def sauvegarder_document(
    dossier_id: int = Form(...),
    type_detecte: str = Form(...),
    synthese: str = Form(...),
    file: UploadFile = File(...)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    nom_fichier_propre = file.filename.replace(" ", "_")
    file_path = os.path.join(UPLOAD_DIR, nom_fichier_propre)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    date_ajout = datetime.now().strftime("%d %b %Y")
    url_fichier = f"http://localhost:8000/uploads/{nom_fichier_propre}"
    
    cursor.execute("""
        INSERT INTO documents (dossier_id, nom_fichier, chemin_fichier, type_detecte, synthese, date_ajout)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (dossier_id, file.filename, url_fichier, type_detecte, synthese, date_ajout))
    
    conn.commit()
    conn.close()
    
    return {"status": "success"}