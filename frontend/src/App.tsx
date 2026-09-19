import { useState, useRef, useEffect } from 'react'
import { LuFileText, LuFolder, LuSettings, LuChevronLeft, LuUpload, LuFile, LuX, LuPlus, LuSearch, LuCalendar, LuTrash, LuFileSearch } from 'react-icons/lu'

// ==========================================
// 0. FORMATAGE DU TEXTE & BOUTONS SOURCE 2.0
// ==========================================
const FormattedText = ({ text, onPageClick }: { text: string, onPageClick: (page: number) => void }) => {
  return (
    <div style={{ fontFamily: 'system-ui, -apple-system, sans-serif', fontSize: '14px', lineHeight: '1.7', color: '#334155' }}>
      {text.split('\n').map((line, i) => {
        if (line.trim() === '') return <div key={i} style={{ height: '8px' }} />;
        
        const isBullet = line.trim().startsWith('-');
        const content = isBullet ? line.trim().substring(1).trim() : line.trim();
        
        const parts = content.split(/(\*\*.*?\*\*|\(Page \d+\))/gi);
        
        const formattedLine = parts.map((part, j) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={j} style={{ color: '#0f172a' }}>{part.slice(2, -2)}</strong>;
          }
          const pageMatch = part.match(/^\(Page (\d+)\)$/i);
          if (pageMatch) {
            return (
              <button 
                key={j} 
                onClick={() => onPageClick(parseInt(pageMatch[1], 10))}
                title="Aller à cette page"
                style={{ 
                  marginLeft: '8px', fontSize: '11px', padding: '4px 8px', borderRadius: '12px', 
                  backgroundColor: '#e0e7ff', color: '#4338ca', border: '1px solid #c7d2fe', 
                  cursor: 'pointer', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px',
                  transform: 'translateY(-1px)', transition: 'all 0.2s'
                }}
              >
                <LuFileSearch size={12} /> P.{pageMatch[1]}
              </button>
            );
          }
          return <span key={j}>{part}</span>;
        });

        if (isBullet) {
          return <li key={i} style={{ marginLeft: '20px', marginBottom: '8px' }}>{formattedLine}</li>;
        }
        
        if (content.startsWith('**') || /^\d+\./.test(content)) {
          return <div key={i} style={{ marginTop: '16px', marginBottom: '8px', fontSize: '15px' }}>{formattedLine}</div>;
        }

        return <div key={i} style={{ marginBottom: '6px' }}>{formattedLine}</div>;
      })}
    </div>
  );
}

// ==========================================
// 1. ZONE BROUILLON : ANALYSE RAPIDE
// ==========================================
const AnalyseRapide = ({ isActive }: { isActive: boolean }) => {
  const [documents, setDocuments] = useState<{ id: string, file: File, url: string, name: string }[]>([])
  const [activeTab, setActiveTab] = useState<string | null>(null)
  const [analyses, setAnalyses] = useState<Record<string, { status: 'idle' | 'loading' | 'success' | 'error', type: string, text: string }>>({})
  
  const [isDragging, setIsDragging] = useState(false)
  
  // GESTION DU SAUT DE PAGE FORCE
  const [targetPage, setTargetPage] = useState<number>(1)
  const [iframeTrigger, setIframeTrigger] = useState<number>(0)
  
  const fileInputRef = useRef<HTMLInputElement>(null)
  const abortControllers = useRef<Record<string, AbortController>>({})

  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false)
  const [dossiersList, setDossiersList] = useState<any[]>([])
  const [selectedDossier, setSelectedDossier] = useState<string>('')
  const [newDossierName, setNewDossierName] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (!isActive) return;
    let dragCounter = 0;
    const handleDragEnter = (e: DragEvent) => { e.preventDefault(); dragCounter++; if (e.dataTransfer) setIsDragging(true); };
    const handleDragLeave = (e: DragEvent) => { e.preventDefault(); dragCounter--; if (dragCounter <= 0) { setIsDragging(false); dragCounter = 0; } };
    const handleDragOver = (e: DragEvent) => { e.preventDefault(); };
    const handleDrop = (e: DragEvent) => { e.preventDefault(); dragCounter = 0; setIsDragging(false); const file = e.dataTransfer?.files?.[0]; if (file) processFile(file); };

    window.addEventListener('dragenter', handleDragEnter); window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('dragover', handleDragOver); window.addEventListener('drop', handleDrop);
    return () => {
      window.removeEventListener('dragenter', handleDragEnter); window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('dragover', handleDragOver); window.removeEventListener('drop', handleDrop);
    };
  }, [isActive]);

  const processFile = (file: File) => {
    if (file.type !== "application/pdf") { alert("Veuillez sélectionner un fichier PDF."); return; }
    const docId = "draft_" + Date.now();
    const fileUrl = URL.createObjectURL(file)
    setDocuments(prev => [...prev, { id: docId, file, url: fileUrl, name: file.name }])
    setAnalyses(prev => ({ ...prev, [docId]: { status: 'idle', type: '', text: '' } }))
    setActiveTab(docId)
    setTargetPage(1)
    setIframeTrigger(Date.now()) // Force l'iframe à charger la page 1
  }

  const handleTabSwitch = (docId: string) => {
    setActiveTab(docId);
    setTargetPage(1); 
    setIframeTrigger(Date.now()) // Force le rafraîchissement au changement d'onglet
  }

  const launchAnalysis = async (docId: string, file: File) => {
    const controller = new AbortController()
    abortControllers.current[docId] = controller
    setAnalyses(prev => ({ ...prev, [docId]: { status: 'loading', type: 'Détection...', text: '' } }))

    const formData = new FormData()
    formData.append("file", file)

    try {
      const response = await fetch("http://localhost:8000/api/analyse", { method: "POST", body: formData, signal: controller.signal })
      if (!response.ok) throw new Error("Erreur HTTP")
      const data = await response.json()
      setAnalyses(prev => ({ ...prev, [docId]: { status: 'success', type: data.type_detecte, text: data.synthese } }))
    } catch (error: any) {
      if (error.name === 'AbortError') { setAnalyses(prev => ({ ...prev, [docId]: { status: 'idle', type: '', text: '' } })) } 
      else { setAnalyses(prev => ({ ...prev, [docId]: { status: 'error', type: 'Erreur', text: "Erreur serveur." } })) }
    } finally { delete abortControllers.current[docId] }
  }

  const cancelAnalysis = (docId: string) => {
    if (abortControllers.current[docId]) abortControllers.current[docId].abort()
  }

  const closeTab = (e: React.MouseEvent, docId: string) => {
    e.stopPropagation()
    cancelAnalysis(docId)
    setDocuments(prev => prev.filter(d => d.id !== docId))
    setAnalyses(prev => { const newAnalyses = { ...prev }; delete newAnalyses[docId]; return newAnalyses; })
    if (activeTab === docId) setActiveTab(null)
  }

  const handleOpenSaveModal = async () => {
    setIsSaveModalOpen(true); setNewDossierName('');
    try {
      const res = await fetch("http://localhost:8000/api/dossiers")
      const data = await res.json()
      if (Array.isArray(data)) {
        setDossiersList(data)
        if (data.length > 0) setSelectedDossier(data[0].id.toString())
        else setSelectedDossier("NEW")
      }
    } catch (e) {}
  }

  const handleSaveDocument = async () => {
    const activeDoc = documents.find(d => d.id === activeTab)
    const activeAnalysis = activeTab ? analyses[activeTab] : null
    if (!activeDoc || !activeAnalysis) return;

    setIsSaving(true)
    let finalDossierId = selectedDossier;

    try {
      if (selectedDossier === "NEW") {
        if (!newDossierName.trim()) { alert("Donnez un nom au nouveau dossier."); setIsSaving(false); return; }
        const fdDossier = new FormData(); fdDossier.append("nom", newDossierName);
        const resDossier = await fetch("http://localhost:8000/api/dossiers", { method: "POST", body: fdDossier })
        const dataDossier = await resDossier.json()
        finalDossierId = dataDossier.id.toString()
      }

      const formData = new FormData()
      formData.append("dossier_id", finalDossierId)
      formData.append("type_detecte", activeAnalysis.type)
      formData.append("synthese", activeAnalysis.text)
      formData.append("file", activeDoc.file)

      const res = await fetch("http://localhost:8000/api/documents", { method: "POST", body: formData })
      if (res.ok) {
        alert("Enregistré avec succès dans vos dossiers !")
        setIsSaveModalOpen(false)
      } else { alert("Erreur lors de la sauvegarde.") }
    } catch (e) { alert("Erreur réseau.") }
    finally { setIsSaving(false) }
  }

  const activeDoc = documents.find(d => d.id === activeTab)
  const activeAnalysis = activeTab ? analyses[activeTab] : null

  return (
    <div style={{ display: 'flex', gap: '20px', height: '100%', padding: '16px 20px 16px 20px', boxSizing: 'border-box' }}>
      <div style={{ flex: 1, backgroundColor: 'white', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', display: 'flex', flexDirection: 'column', overflow: 'hidden', border: '1px solid #e2e8f0', position: 'relative' }}>
        <div style={{ padding: '15px 20px', borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc', fontWeight: 600, color: '#334155' }}>
          Zone de Brouillon {activeDoc ? `- ${activeDoc.name}` : ''}
        </div>
        {activeDoc ? (
          <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%' }}>
            <iframe key={activeDoc.id + "_" + targetPage + "_" + iframeTrigger} src={`${activeDoc.url}#page=${targetPage}&view=FitH`} style={{ width: '100%', height: '100%', border: 'none', pointerEvents: isDragging ? 'none' : 'auto' }} />
          </div>
        ) : (
          <div onClick={() => fileInputRef.current?.click()} style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f1f5f9', padding: '20px' }}>
             <div style={{ border: '2px dashed #cbd5e1', padding: '40px', borderRadius: '12px', textAlign: 'center', backgroundColor: 'white', cursor: 'pointer', width: '100%', maxWidth: '400px' }}>
               <LuFile size={48} color="#94a3b8" style={{ margin: '0 auto' }} />
               <div style={{ color: '#475569', fontWeight: 600, marginTop: '16px' }}>Cliquez ou glissez un PDF pour l'inspecter</div>
             </div>
          </div>
        )}
        {isDragging && (
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.7)', backdropFilter: 'blur(4px)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
             <div style={{ border: '2px dashed #60a5fa', padding: '40px 60px', borderRadius: '20px', textAlign: 'center', backgroundColor: 'white', transform: 'scale(1.05)' }}>
               <LuUpload size={56} color="#3b82f6" style={{ margin: '0 auto' }} />
               <div style={{ color: '#0f172a', fontSize: '20px', fontWeight: 'bold', marginTop: '16px' }}>Relâchez pour analyser à la volée</div>
             </div>
          </div>
        )}
        <input type="file" accept="application/pdf" ref={fileInputRef} onChange={(e) => { if (e.target.files?.[0]) processFile(e.target.files[0]) }} style={{ display: 'none' }} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', minWidth: 0 }}>
        <div style={{ display: 'flex', gap: '8px', backgroundColor: '#f8fafc', padding: '6px', borderRadius: '12px', border: '1px solid #e2e8f0', minHeight: '52px', overflowX: 'auto' }}>
          {documents.map(doc => (
            <div key={doc.id} onClick={() => handleTabSwitch(doc.id)} style={{ display: 'flex', alignItems: 'center', minWidth: '120px', maxWidth: '220px', flexShrink: 0, padding: '8px 12px', borderRadius: '8px', backgroundColor: activeTab === doc.id ? 'white' : 'transparent', boxShadow: activeTab === doc.id ? '0 1px 3px rgb(0 0 0 / 0.1)' : 'none', cursor: 'pointer' }}>
              <span style={{ flex: 1, color: activeTab === doc.id ? '#0f172a' : '#64748b', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '13px' }}>{doc.name}</span>
              <button onClick={(e) => closeTab(e, doc.id)} style={{ marginLeft: '8px', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><LuX size={14} /></button>
            </div>
          ))}
          <button onClick={() => fileInputRef.current?.click()} style={{ padding: '8px 15px', borderRadius: '8px', border: '1px dashed #cbd5e1', background: 'transparent', color: '#64748b', fontWeight: 600, cursor: 'pointer', fontSize: '13px', flexShrink: 0 }}>+ Analyser un autre</button>
        </div>

        <div style={{ flex: 1, backgroundColor: 'white', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', padding: '24px', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '2px solid #f1f5f9', paddingBottom: '15px' }}>
            <h3 style={{ margin: 0, color: '#0f172a', fontSize: '18px' }}>Synthèse Structurée</h3>
            {activeAnalysis && activeAnalysis.status !== 'idle' && activeAnalysis.status !== 'loading' && (
              <span style={{ fontSize: '12px', backgroundColor: '#dbeafe', color: '#1e40af', padding: '6px 12px', borderRadius: '20px', fontWeight: 700 }}>{activeAnalysis.type}</span>
            )}
          </div>
          <div style={{ flex: 1, overflowY: 'auto', paddingRight: '8px' }}>
            {!activeDoc ? ( <p style={{ color: '#94a3b8', fontStyle: 'italic', textAlign: 'center', marginTop: '40px' }}>Chargez un document pour commencer.</p> ) : activeAnalysis?.status === 'idle' ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', marginTop: '20px' }}>
                <p style={{ color: '#64748b', marginBottom: '20px' }}>Le document est prêt. Lancer l'analyse et l'enregistrement ?</p>
                <button onClick={() => launchAnalysis(activeDoc.id, activeDoc.file)} style={{ padding: '12px 24px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}>Lancer l'extraction IA</button>
              </div>
            ) : activeAnalysis?.status === 'loading' ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', marginTop: '20px' }}>
                <div style={{ width: '40px', height: '40px', border: '3px solid #e2e8f0', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '20px' }} />
                <p style={{ color: '#3b82f6', fontWeight: 600 }}>Lecture intégrale par l'IA...</p>
                <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '8px', marginBottom: '24px' }}>Vous pouvez naviguer ailleurs, l'analyse continue.</p>
                <button onClick={() => cancelAnalysis(activeDoc.id)} style={{ padding: '8px 20px', backgroundColor: '#fee2e2', color: '#ef4444', border: '1px solid #fca5a5', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}>Annuler</button>
              </div>
            ) : ( 
              <FormattedText text={activeAnalysis?.text || ''} onPageClick={(page) => { setTargetPage(page); setIframeTrigger(Date.now()); }} /> 
            )}
          </div>
          {activeDoc && activeAnalysis?.status === 'success' && (
            <div style={{ marginTop: '20px', borderTop: '1px solid #e2e8f0', paddingTop: '15px', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
               <button onClick={handleOpenSaveModal} style={{ padding: '8px 16px', backgroundColor: '#10b981', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                 <LuFolder size={16} /> Enregistrer sous...
               </button>
               <button onClick={() => launchAnalysis(activeDoc.id, activeDoc.file)} style={{ padding: '8px 16px', backgroundColor: '#f1f5f9', color: '#475569', border: 'none', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}>Régénérer</button>
            </div>
          )}
        </div>
      </div>

      {isSaveModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', padding: '30px', borderRadius: '16px', width: '100%', maxWidth: '400px' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#0f172a', fontSize: '20px' }}>Enregistrer l'analyse</h3>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: '#475569', marginBottom: '8px' }}>Emplacement du document :</label>
            <select value={selectedDossier} onChange={(e) => setSelectedDossier(e.target.value)} style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #cbd5e1', outline: 'none', marginBottom: selectedDossier === "NEW" ? '10px' : '20px' }}>
              {dossiersList.map(d => ( <option key={d.id} value={d.id}>{d.nom}</option> ))}
              <option value="NEW" style={{ fontWeight: 'bold', color: '#3b82f6' }}>+ Créer un nouveau dossier...</option>
            </select>
            {selectedDossier === "NEW" && (
              <div style={{ marginBottom: '20px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px dashed #cbd5e1' }}>
                <input type="text" autoFocus placeholder="Ex: Succession Martin" value={newDossierName} onChange={(e) => setNewDossierName(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', outline: 'none', boxSizing: 'border-box' }} />
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button onClick={() => setIsSaveModalOpen(false)} style={{ padding: '10px 16px', backgroundColor: '#f1f5f9', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>Annuler</button>
              <button disabled={isSaving} onClick={handleSaveDocument} style={{ padding: '10px 16px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>
                {isSaving ? "Sauvegarde..." : "Valider"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ==========================================
// 2. ESPACE DE TRAVAIL D'UN DOSSIER (Persistant)
// ==========================================
const DossierView = ({ dossierId, onBack, isActive }: { dossierId: number, onBack: () => void, isActive: boolean }) => {
  const [dossierInfo, setDossierInfo] = useState<any>(null)
  const [documents, setDocuments] = useState<{ id: string | number, name: string, url: string, file?: File, isSaved: boolean }[]>([])
  const [analyses, setAnalyses] = useState<Record<string, { status: 'idle' | 'loading' | 'success' | 'error', type: string, text: string }>>({})
  const [activeTab, setActiveTab] = useState<string | number | null>(null)
  
  const [isDragging, setIsDragging] = useState(false)
  
  // GESTION DU SAUT DE PAGE FORCE
  const [targetPage, setTargetPage] = useState<number>(1)
  const [iframeTrigger, setIframeTrigger] = useState<number>(0)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const abortControllers = useRef<Record<string, AbortController>>({})
  const prevDossierId = useRef<number | null>(null)

  const fetchDossier = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/dossiers/${dossierId}`)
      const data = await res.json()
      setDossierInfo(data.dossier)
      
      if (Array.isArray(data.documents)) {
        const dbDocs = data.documents.map((d: any) => ({ id: d.id, name: d.nom_fichier, url: d.chemin_fichier, isSaved: true }))
        const dbAnalyses: any = {}
        data.documents.forEach((d: any) => { dbAnalyses[d.id] = { status: 'success', type: d.type_detecte, text: d.synthese } })
        
        setDocuments(prev => {
          const unsavedDocs = prev.filter(doc => !doc.isSaved);
          return [...dbDocs, ...unsavedDocs];
        });
        
        setAnalyses(prev => {
          const newAnalyses = { ...dbAnalyses };
          Object.keys(prev).forEach(k => { if (k.toString().startsWith('temp_')) newAnalyses[k] = prev[k]; });
          return newAnalyses;
        });

        setActiveTab(currentTab => {
          if (!currentTab && dbDocs.length > 0) {
            setTargetPage(1);
            setIframeTrigger(Date.now());
            return dbDocs[dbDocs.length - 1].id;
          }
          return currentTab;
        });
      }
    } catch(e) {}
  }

  useEffect(() => {
    if (dossierId !== prevDossierId.current) {
      setDocuments([]); setAnalyses({}); setActiveTab(null); setTargetPage(1); setIframeTrigger(Date.now());
      Object.values(abortControllers.current).forEach(c => c.abort());
      abortControllers.current = {};
      prevDossierId.current = dossierId;
    }
    if (isActive) fetchDossier();
  }, [dossierId, isActive])

  useEffect(() => {
    if (!isActive) return;
    let dragCounter = 0;
    const handleDragEnter = (e: DragEvent) => { e.preventDefault(); dragCounter++; if (e.dataTransfer) setIsDragging(true); };
    const handleDragLeave = (e: DragEvent) => { e.preventDefault(); dragCounter--; if (dragCounter <= 0) { setIsDragging(false); dragCounter = 0; } };
    const handleDragOver = (e: DragEvent) => { e.preventDefault(); };
    const handleDrop = (e: DragEvent) => { e.preventDefault(); dragCounter = 0; setIsDragging(false); const file = e.dataTransfer?.files?.[0]; if (file) processFile(file); };

    window.addEventListener('dragenter', handleDragEnter); window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('dragover', handleDragOver); window.addEventListener('drop', handleDrop);
    return () => {
      window.removeEventListener('dragenter', handleDragEnter); window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('dragover', handleDragOver); window.removeEventListener('drop', handleDrop);
    };
  }, [isActive]);

  const handleTabSwitch = (docId: string | number) => {
    setActiveTab(docId);
    setTargetPage(1);
    setIframeTrigger(Date.now());
  }

  const processFile = (file: File) => {
    if (file.type !== "application/pdf") { alert("Veuillez sélectionner un fichier PDF."); return; }
    const tempId = "temp_" + Date.now();
    const fileUrl = URL.createObjectURL(file);
    setDocuments(prev => [...prev, { id: tempId, name: file.name, url: fileUrl, file, isSaved: false }])
    setAnalyses(prev => ({ ...prev, [tempId]: { status: 'idle', type: '', text: '' } }))
    setActiveTab(tempId)
    setTargetPage(1)
    setIframeTrigger(Date.now())
  }

  const launchAnalysisAndSave = async (docId: string | number, file: File) => {
    const controller = new AbortController()
    abortControllers.current[docId] = controller
    setAnalyses(prev => ({ ...prev, [docId]: { status: 'loading', type: 'Détection...', text: '' } }))

    const formData = new FormData()
    formData.append("file", file)

    try {
      const response = await fetch("http://localhost:8000/api/analyse", { method: "POST", body: formData, signal: controller.signal })
      if (!response.ok) throw new Error("Erreur d'analyse")
      const data = await response.json()
      
      const saveFormData = new FormData();
      saveFormData.append("dossier_id", dossierId.toString());
      saveFormData.append("type_detecte", data.type_detecte);
      saveFormData.append("synthese", data.synthese);
      saveFormData.append("file", file);

      const resSave = await fetch("http://localhost:8000/api/documents", { method: "POST", body: saveFormData });
      if (!resSave.ok) throw new Error("Erreur de sauvegarde DB");
      
      setDocuments(prev => prev.filter(d => d.id !== docId));
      delete abortControllers.current[docId];
      await fetchDossier();
      
    } catch (error: any) {
      if (error.name === 'AbortError') { setAnalyses(prev => ({ ...prev, [docId]: { status: 'idle', type: '', text: '' } })) } 
      else { setAnalyses(prev => ({ ...prev, [docId]: { status: 'error', type: 'Erreur', text: "L'analyse a échoué." } })) }
    } finally { delete abortControllers.current[docId] }
  }

  const cancelAnalysis = (docId: string | number) => {
    if (abortControllers.current[docId]) abortControllers.current[docId].abort()
  }

  const handleDeleteDocument = async (e: React.MouseEvent, docId: string | number, isSaved: boolean) => {
    e.stopPropagation()
    cancelAnalysis(docId)
    
    if (!isSaved) {
      setDocuments(prev => prev.filter(d => d.id !== docId))
      setAnalyses(prev => { const newA = { ...prev }; delete newA[docId]; return newA; })
      if (activeTab === docId) setActiveTab(null)
      return;
    }

    if (window.confirm("Supprimer définitivement ce document du dossier ?")) {
      try {
        const res = await fetch(`http://localhost:8000/api/documents/${docId}`, { method: 'DELETE' })
        if (res.ok) {
          setDocuments(prev => prev.filter(d => d.id !== docId))
          setAnalyses(prev => { const newA = { ...prev }; delete newA[docId]; return newA; })
          if (activeTab === docId) setActiveTab(null)
          fetchDossier();
        }
      } catch (err) { alert("Erreur lors de la suppression.") }
    }
  }

  const activeDoc = documents.find(d => d.id === activeTab)
  const activeAnalysis = activeTab ? analyses[activeTab] : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '16px 20px', boxSizing: 'border-box', backgroundColor: '#f1f5f9' }}>
      
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px', gap: '16px' }}>
        <button onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>
          <LuChevronLeft size={16} /> Retour aux dossiers
        </button>
        <h2 style={{ margin: 0, color: '#0f172a', fontSize: '24px' }}>Dossier : {dossierInfo?.nom || 'Chargement...'}</h2>
      </div>

      <div style={{ display: 'flex', gap: '20px', flex: 1, minHeight: 0 }}>
        
        <div style={{ flex: 1, backgroundColor: 'white', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', display: 'flex', flexDirection: 'column', overflow: 'hidden', border: '1px solid #e2e8f0', position: 'relative' }}>
          <div style={{ padding: '15px 20px', borderBottom: '1px solid #e2e8f0', backgroundColor: '#f8fafc', fontWeight: 600 }}>
            Pièce {activeDoc ? `- ${activeDoc.name}` : ''}
          </div>
          {activeDoc ? (
            <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%' }}>
              <iframe key={activeDoc.id + "_" + targetPage + "_" + iframeTrigger} src={`${activeDoc.url}#page=${targetPage}&view=FitH`} style={{ width: '100%', height: '100%', border: 'none', pointerEvents: isDragging ? 'none' : 'auto' }} />
            </div>
          ) : (
            <div onClick={() => fileInputRef.current?.click()} style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f1f5f9', padding: '20px' }}>
               <div style={{ border: '2px dashed #cbd5e1', padding: '40px', borderRadius: '12px', textAlign: 'center', backgroundColor: 'white', cursor: 'pointer', width: '100%', maxWidth: '400px' }}>
                 <LuFile size={48} color="#94a3b8" style={{ margin: '0 auto' }} />
                 <div style={{ color: '#475569', fontWeight: 600, marginTop: '16px' }}>Cliquez ou glissez un PDF à ajouter au dossier</div>
               </div>
            </div>
          )}

          {isDragging && (
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.7)', backdropFilter: 'blur(4px)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
               <div style={{ border: '2px dashed #60a5fa', padding: '40px 60px', borderRadius: '20px', textAlign: 'center', backgroundColor: 'white', transform: 'scale(1.05)' }}>
                 <LuUpload size={56} color="#3b82f6" style={{ margin: '0 auto' }} />
                 <div style={{ color: '#0f172a', fontSize: '20px', fontWeight: 'bold', marginTop: '16px' }}>Relâchez pour ajouter et analyser</div>
               </div>
            </div>
          )}
          <input type="file" accept="application/pdf" ref={fileInputRef} onChange={(e) => { if (e.target.files?.[0]) processFile(e.target.files[0]) }} style={{ display: 'none' }} />
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', minWidth: 0 }}>
          <div style={{ display: 'flex', gap: '8px', backgroundColor: '#f8fafc', padding: '6px', borderRadius: '12px', border: '1px solid #e2e8f0', minHeight: '52px', overflowX: 'auto' }}>
            {documents.length === 0 && <span style={{ padding: '8px 12px', color: '#94a3b8', fontSize: '13px' }}>Le dossier est vide.</span>}
            {documents.map(doc => (
              <div key={doc.id} onClick={() => handleTabSwitch(doc.id)} style={{ display: 'flex', alignItems: 'center', minWidth: '120px', maxWidth: '220px', flexShrink: 0, padding: '8px 12px', borderRadius: '8px', backgroundColor: activeTab === doc.id ? 'white' : 'transparent', boxShadow: activeTab === doc.id ? '0 1px 3px rgb(0 0 0 / 0.1)' : 'none', cursor: 'pointer' }}>
                <span style={{ flex: 1, color: activeTab === doc.id ? '#0f172a' : '#64748b', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '13px' }}>{doc.name}</span>
                <button onClick={(e) => handleDeleteDocument(e, doc.id, doc.isSaved)} style={{ marginLeft: '8px', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '2px' }}>
                  {doc.isSaved ? <LuTrash size={14} title="Supprimer de la BDD" /> : <LuX size={14} title="Fermer" />}
                </button>
              </div>
            ))}
            <button onClick={() => fileInputRef.current?.click()} style={{ padding: '8px 15px', borderRadius: '8px', border: '1px dashed #cbd5e1', background: 'transparent', color: '#64748b', fontWeight: 600, cursor: 'pointer', fontSize: '13px', flexShrink: 0, marginLeft: 'auto' }}>+ Ajouter un PDF</button>
          </div>

          <div style={{ flex: 1, backgroundColor: 'white', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', padding: '24px', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '2px solid #f1f5f9', paddingBottom: '15px' }}>
              <h3 style={{ margin: 0, color: '#0f172a', fontSize: '18px' }}>Synthèse Enregistrée</h3>
              {activeAnalysis && activeAnalysis.status !== 'idle' && activeAnalysis.status !== 'loading' && (
                <span style={{ fontSize: '12px', backgroundColor: '#dbeafe', color: '#1e40af', padding: '6px 12px', borderRadius: '20px', fontWeight: 700 }}>{activeAnalysis.type}</span>
              )}
            </div>
            
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: '8px' }}>
              {!activeDoc ? ( <p style={{ color: '#94a3b8', fontStyle: 'italic', textAlign: 'center', marginTop: '40px' }}>Sélectionnez ou ajoutez un document.</p> ) 
              : activeAnalysis?.status === 'idle' ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', marginTop: '20px' }}>
                  <p style={{ color: '#64748b', marginBottom: '20px' }}>Le document est prêt. Lancer l'analyse et l'enregistrement ?</p>
                  <button onClick={() => launchAnalysisAndSave(activeDoc.id, activeDoc.file!)} style={{ padding: '12px 24px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}>Lancer l'analyse</button>
                </div>
              ) : activeAnalysis?.status === 'loading' ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', marginTop: '20px' }}>
                  <div style={{ width: '40px', height: '40px', border: '3px solid #e2e8f0', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '20px' }} />
                  <p style={{ color: '#3b82f6', fontWeight: 600 }}>Analyse et sauvegarde en cours...</p>
                  <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '8px', marginBottom: '24px' }}>Vous pouvez naviguer ailleurs, l'opération continue.</p>
                  <button onClick={() => cancelAnalysis(activeDoc.id)} style={{ padding: '8px 20px', backgroundColor: '#fee2e2', color: '#ef4444', border: '1px solid #fca5a5', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}>Annuler</button>
                </div>
              ) : ( 
                <FormattedText text={activeAnalysis?.text || ''} onPageClick={(page) => { setTargetPage(page); setIframeTrigger(Date.now()); }} /> 
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ==========================================
// 3. LA GRILLE DES DOSSIERS
// ==========================================
const Dossiers = ({ onOpenDossier, isActive }: { onOpenDossier: (id: number) => void, isActive: boolean }) => {
  const [listeDossiers, setListeDossiers] = useState<any[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [nouveauNom, setNouveauNom] = useState('')
  const [recherche, setRecherche] = useState('')

  const fetchDossiers = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/dossiers")
      const data = await res.json()
      if (Array.isArray(data)) setListeDossiers(data)
    } catch (e) { setListeDossiers([]) }
  }

  useEffect(() => {
    if (isActive) { fetchDossiers() }
  }, [isActive])

  const handleCreerDossier = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nouveauNom.trim()) return
    const formData = new FormData(); formData.append("nom", nouveauNom)
    try {
      const res = await fetch("http://localhost:8000/api/dossiers", { method: "POST", body: formData })
      if (res.ok) { setNouveauNom(''); setIsModalOpen(false); fetchDossiers(); }
    } catch (e) { alert("Erreur de création") }
  }

  const handleSupprimerDossier = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation() 
    if (window.confirm("Êtes-vous sûr de vouloir supprimer ce dossier et tous ses documents ?")) {
      try {
        const res = await fetch(`http://localhost:8000/api/dossiers/${id}`, { method: 'DELETE' })
        if (res.ok) fetchDossiers()
      } catch (err) { alert("Erreur lors de la suppression.") }
    }
  }

  const dossiersFiltres = Array.isArray(listeDossiers) 
    ? listeDossiers.filter(d => d.nom && d.nom.toLowerCase().includes(recherche.toLowerCase())) 
    : []

  return (
    <div style={{ padding: '32px 40px', height: '100%', boxSizing: 'border-box', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h2 style={{ color: '#0f172a', margin: '0 0 8px 0', fontSize: '28px' }}>Dossiers Clients</h2>
          <p style={{ color: '#64748b', margin: 0, fontSize: '15px' }}>Vos espaces de travail pérennes.</p>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <LuSearch style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} size={18} />
            <input type="text" value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher..." style={{ padding: '10px 16px 10px 40px', borderRadius: '8px', border: '1px solid #e2e8f0', width: '250px', outline: 'none' }} />
          </div>
          <button onClick={() => setIsModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}>
            <LuPlus size={18} /> Nouveau Dossier
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '24px', overflowY: 'auto', paddingBottom: '20px' }}>
        {dossiersFiltres.length === 0 ? (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', color: '#94a3b8', fontStyle: 'italic', padding: '40px' }}>
            Aucun dossier existant.
          </div>
        ) : (
          dossiersFiltres.map(dossier => (
            <div key={dossier.id} onClick={() => onOpenDossier(dossier.id)} style={{ backgroundColor: 'white', borderRadius: '12px', padding: '20px', border: '1px solid #e2e8f0', cursor: 'pointer', display: 'flex', flexDirection: 'column', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div style={{ padding: '10px', backgroundColor: '#eff6ff', borderRadius: '10px', color: '#3b82f6' }}><LuFolder size={24} /></div>
                <button onClick={(e) => handleSupprimerDossier(e, dossier.id)} style={{ padding: '6px', background: '#fee2e2', color: '#ef4444', borderRadius: '8px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                  <LuTrash size={16} />
                </button>
              </div>
              <h3 style={{ margin: '0 0 12px 0', color: '#1e293b', fontSize: '16px', lineHeight: '1.4' }}>{dossier.nom}</h3>
              <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#64748b', fontSize: '13px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><LuCalendar size={14} /> {dossier.date}</div>
                <div style={{ fontWeight: 600, backgroundColor: '#f1f5f9', padding: '4px 10px', borderRadius: '20px' }}>{dossier.docs} doc{dossier.docs > 1 ? 's' : ''}</div>
              </div>
            </div>
          ))
        )}
      </div>

      {isModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', padding: '30px', borderRadius: '16px', width: '100%', maxWidth: '400px' }}>
            <h3 style={{ margin: '0 0 16px 0', color: '#0f172a', fontSize: '20px' }}>Créer un nouveau dossier</h3>
            <form onSubmit={handleCreerDossier}>
              <input type="text" value={nouveauNom} onChange={(e) => setNouveauNom(e.target.value)} placeholder="Ex: Succession Martin" autoFocus style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid #cbd5e1', outline: 'none', boxSizing: 'border-box', marginBottom: '20px' }} />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" onClick={() => setIsModalOpen(false)} style={{ padding: '10px 16px', backgroundColor: '#f1f5f9', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>Annuler</button>
                <button type="submit" style={{ padding: '10px 16px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

// ==========================================
// 4. LE SHELL DE NAVIGATION PRINCIPAL
// ==========================================
function App() {
  const [activePage, setActivePage] = useState('analyse')
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [currentDossierId, setCurrentDossierId] = useState<number | null>(null)
  
  const [iaStatus, setIaStatus] = useState<'online' | 'offline' | 'checking'>('checking')

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/health")
        if (res.ok) setIaStatus('online')
        else setIaStatus('offline')
      } catch { setIaStatus('offline') }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 5000)
    return () => clearInterval(interval)
  }, [])

  const menuItems = [ 
    { id: 'analyse', name: 'Analyse Rapide', icon: <LuFileText size={20} /> }, 
    { id: 'dossiers', name: 'Dossiers', icon: <LuFolder size={20} /> }, 
    { id: 'parametres', name: 'Paramètres', icon: <LuSettings size={20} /> } 
  ]

  const handleMenuClick = (id: string) => {
    setActivePage(id)
  }

  const getStatusColor = () => {
    if (iaStatus === 'online') return '#4ade80';
    if (iaStatus === 'checking') return '#fbbf24';
    return '#ef4444';
  }
  
  const getStatusText = () => {
    if (iaStatus === 'online') return 'Moteur IA Prêt';
    if (iaStatus === 'checking') return 'Vérification...';
    return 'IA Hors-ligne';
  }

  return (
    <div style={{ display: 'flex', position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: '#f1f5f9', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      
      <style>{`
        body, html, #root { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background-color: #f1f5f9; }
        * { box-sizing: border-box; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .sidebar-btn { transition: all 0.2s ease; }
        .sidebar-btn:hover:not(.active) { background-color: #1e293b !important; transform: translateX(4px); color: #f8fafc !important; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .toggle-btn:hover { background-color: #f8fafc !important; color: #0f172a !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.15) !important; }
      `}</style>

      {/* Barre Latérale */}
      <div style={{ 
        width: isSidebarOpen ? '260px' : '72px', 
        transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)', 
        margin: '16px 0 16px 16px',
        borderRadius: '16px',
        backgroundColor: '#0f172a', 
        color: 'white', 
        display: 'flex', 
        flexDirection: 'column', 
        flexShrink: 0,
        boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
        position: 'relative', 
        overflow: 'visible'
      }}>
        
        <button 
          className="toggle-btn"
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          title={isSidebarOpen ? "Réduire le menu" : "Déplier le menu"}
          style={{ 
            position: 'absolute', top: '32px', right: '-14px', width: '28px', height: '28px', borderRadius: '50%', backgroundColor: 'white', border: '1px solid #e2e8f0', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', zIndex: 50, boxShadow: '0 2px 4px rgba(0,0,0,0.1)', transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.2s', transform: isSidebarOpen ? 'rotate(0deg)' : 'rotate(180deg)'
          }}
        >
          <div style={{ display: 'flex', marginLeft: isSidebarOpen ? '-2px' : '0' }}>
            <LuChevronLeft size={14} />
          </div>
        </button>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '24px 20px 16px 20px', display: 'flex', alignItems: 'center', justifyContent: isSidebarOpen ? 'flex-start' : 'center', boxSizing: 'border-box' }}>
            <h1 style={{ margin: 0, fontSize: isSidebarOpen ? '22px' : '24px', fontWeight: 'bold', letterSpacing: '0.5px', color: isSidebarOpen ? '#ffffff' : '#3b82f6', transition: 'color 0.3s' }}>
              {isSidebarOpen ? 'NotarIA' : 'N.'}
            </h1>
          </div>
          
          <div style={{ padding: isSidebarOpen ? '0 24px 24px 24px' : '0 0 24px 0', display: 'flex', alignItems: 'center', justifyContent: isSidebarOpen ? 'flex-start' : 'center', gap: '8px', borderBottom: '1px solid #1e293b', color: getStatusColor() }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: getStatusColor(), boxShadow: iaStatus === 'online' ? `0 0 8px ${getStatusColor()}` : 'none', flexShrink: 0 }}></div>
            <span style={{ fontWeight: 600, fontSize: '11px', letterSpacing: '0.5px', textTransform: 'uppercase', opacity: isSidebarOpen ? 0.9 : 0, whiteSpace: 'nowrap', width: isSidebarOpen ? 'auto' : 0, transition: 'opacity 0.2s' }}>
              {getStatusText()}
            </span>
          </div>
          
          <nav className="no-scrollbar" style={{ flex: 1, padding: isSidebarOpen ? '24px 12px' : '24px 8px', overflowY: 'auto', overflowX: 'hidden' }}>
            {menuItems.map((item) => {
              const isActive = activePage === item.id || (activePage === 'dossier_view' && item.id === 'dossiers');
              return (
                <button 
                  key={item.id} 
                  onClick={() => handleMenuClick(item.id)}
                  title={!isSidebarOpen ? item.name : undefined}
                  className={`sidebar-btn ${isActive ? 'active' : ''}`}
                  style={{ 
                    display: 'flex', alignItems: 'center', justifyContent: isSidebarOpen ? 'flex-start' : 'center', width: '100%', padding: isSidebarOpen ? '12px 16px' : '12px 0', marginBottom: '12px', color: isActive ? '#ffffff' : '#94a3b8', backgroundColor: isActive ? '#3b82f6' : 'transparent', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: 500, fontSize: '14px', boxShadow: isActive ? '0 4px 6px -1px rgb(59 130 246 / 0.3)' : 'none'
                  }}
                >
                  <span style={{ marginRight: isSidebarOpen ? '12px' : '0', display: 'flex', alignItems: 'center', opacity: isActive ? 1 : 0.6, transition: 'margin 0.3s, opacity 0.2s' }}>
                    {item.icon}
                  </span>
                  <span style={{ opacity: isSidebarOpen ? 1 : 0, whiteSpace: 'nowrap', width: isSidebarOpen ? 'auto' : 0, display: isSidebarOpen ? 'block' : 'none' }}>
                    {item.name}
                  </span>
                </button>
              )
            })}
          </nav>
        </div>
      </div>
      
      {/* Routeur Principal */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ display: activePage === 'analyse' ? 'block' : 'none', height: '100%' }}>
          <AnalyseRapide isActive={activePage === 'analyse'} />
        </div>
        
        <div style={{ display: activePage === 'dossiers' ? 'block' : 'none', height: '100%' }}>
          <Dossiers isActive={activePage === 'dossiers'} onOpenDossier={(id) => { setCurrentDossierId(id); setActivePage('dossier_view'); }} />
        </div>
        
        {currentDossierId && (
          <div style={{ display: activePage === 'dossier_view' ? 'block' : 'none', height: '100%' }}>
            <DossierView dossierId={currentDossierId} isActive={activePage === 'dossier_view'} onBack={() => setActivePage('dossiers')} />
          </div>
        )}
        
        <div style={{ display: activePage === 'parametres' ? 'block' : 'none', height: '100%' }}>
          <div style={{ padding: '40px' }}><h2 style={{ color: '#0f172a' }}>Paramètres</h2></div>
        </div>
      </main>
    </div>
  )
}

export default App