import os
import json
import faiss
import numpy as np
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import ollama

# --- AYARLAR ---
VECTOR_STORE_DIR = "data/vector_store"
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2'
LLM_MODEL = "llama3.1" # Senin yerel modelin

app = FastAPI(title="Psikoloji AI Chatbot API")

# CORS İzinleri
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedding_model = None
index = None
chunk_map = None

@app.on_event("startup")
def load_resources():
    global embedding_model, index, chunk_map
    print(f"⏳ Sistem başlatılıyor... LLM: {LLM_MODEL}")
    embedding_model = SentenceTransformer(MODEL_NAME)
    try:
        index = faiss.read_index(os.path.join(VECTOR_STORE_DIR, "vector_store.index"))
        with open(os.path.join(VECTOR_STORE_DIR, "chunk_map.json"), 'r', encoding='utf-8') as f:
            chunk_map = json.load(f)
        print("✅ RAG Sistemi Hazır!")
    except Exception as e:
        print(f"❌ Veri yükleme hatası: {e}")

# --- MODELLER ---
class Message(BaseModel):
    role: str
    content: str

# Kullanıcı Profil Bilgisi
class UserProfile(BaseModel):
    name: str = "Kullanıcı"
    age: int = 0
    gender: str = "Belirtilmedi"

class ChatRequest(BaseModel):
    query: str
    history: List[Message] = []
    user_profile: Optional[UserProfile] = None # Profil opsiyonel
    k: int = 3

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not index or not chunk_map:
        raise HTTPException(status_code=500, detail="Sistem hazır değil.")

    # 1. RAG ARAMASI
    query_vector = embedding_model.encode([request.query])
    distances, indices = index.search(np.array(query_vector).astype('float32'), request.k)

    retrieved_texts = []
    sources = []
    for i, idx in enumerate(indices[0]):
        if idx == -1: continue
        try:
            chunk_file = chunk_map[idx]
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                retrieved_texts.append(f"- {data[0]['text']}")
                sources.append(os.path.basename(chunk_file))
        except: continue

    context_block = "\n".join(retrieved_texts)

    # 2. PROFİL BİLGİSİNİ PROMPT'A İŞLEME
    profile_text = ""
    if request.user_profile:
        p = request.user_profile
        gender_text = p.gender if p.gender != "Belirtilmedi" else "bilinmiyor"
        age_text = str(p.age) if p.age > 0 else "bilinmiyor"
        
        profile_text = f"""
        ŞU AN KONUŞTUĞUN KİŞİNİN PROFİLİ:
        - Adı: {p.name}
        - Yaşı: {age_text}
        - Cinsiyeti: {gender_text}
        
        Lütfen cevabında kullanıcıya ismiyle hitap et. Yaşına ve cinsiyetine uygun, saygılı ve empatik bir dil kullan.
        """

    # 3. SYSTEM PROMPT
    system_prompt = f"""
    Sen Bilişsel Davranışçı Terapi (BDT) tekniklerini uygulayan, empatik ve profesyonel bir yapay zeka psikoloji asistanısın.
    
    {profile_text}
    
    AŞAĞIDAKİ KİTAP BİLGİLERİNİ (CONTEXT) TEMEL AL:
    {context_block}

    KURALLAR:
    1. Kullanıcıyı tanı, ismiyle hitap et, samimi ol.
    2. ASLA "Kitapta şöyle yazar" deme, bilgiyi sohbetin akışına yedir.
    3. Kullanıcıya doğrudan tavsiye vermek yerine, Sokratik sorular sorarak (örn: "Bu düşüncenin kanıtı ne?") farkındalık kazandır.
    4. Tıbbi teşhis koyma. İntihar eğilimi sezersen 112'ye yönlendir.
    """
    
    # 4. OLLAMA MESAJ LİSTESİ
    messages_payload = [{'role': 'system', 'content': system_prompt}]
    
    for msg in request.history:
        role = 'assistant' if msg.role == 'model' else 'user'
        messages_payload.append({'role': role, 'content': msg.content})
        
    messages_payload.append({'role': 'user', 'content': request.query})

    # 5. LLAMA 3 ÇAĞRISI
    try:
        response = ollama.chat(model=LLM_MODEL, messages=messages_payload)
        ai_reply = response['message']['content']
    except Exception as e:
        ai_reply = f"Model Hatası: {str(e)}"

    return {"reply": ai_reply, "sources": list(set(sources))}