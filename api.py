# api.py
import os
import json
import faiss
import numpy as np
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import ollama

# --- 1. AYARLAR ---
VECTOR_STORE_DIR = "data/vector_store"
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2'

# DÜZELTME: Senin modelinin adı buraya geldi
LLM_MODEL = "llama3.1" 

app = FastAPI(title="Psikoloji AI Chatbot API (Local Llama 3.1)")

# --- CORS İZİNLERİ ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global değişkenler
embedding_model = None
index = None
chunk_map = None

# --- 2. BAŞLATMA ---
@app.on_event("startup")
def load_resources():
    global embedding_model, index, chunk_map
    print(f"⏳ Sistem başlatılıyor... Kullanılan LLM: {LLM_MODEL}")
    embedding_model = SentenceTransformer(MODEL_NAME)
    try:
        index = faiss.read_index(os.path.join(VECTOR_STORE_DIR, "vector_store.index"))
        with open(os.path.join(VECTOR_STORE_DIR, "chunk_map.json"), 'r', encoding='utf-8') as f:
            chunk_map = json.load(f)
        print("✅ Veriler yüklendi. Local RAG hazır!")
    except Exception as e:
        print(f"❌ HATA: {e}")

# --- 3. VERİ MODELLERİ ---
class Message(BaseModel):
    role: str   # "user" veya "model"
    content: str

class ChatRequest(BaseModel):
    query: str
    history: List[Message] = []
    k: int = 3

# --- 4. RAG ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not index or not chunk_map:
        raise HTTPException(status_code=500, detail="Sistem hazır değil.")

    # A) RETRIEVAL (Bilgi Getirme)
    query_vector = embedding_model.encode([request.query])
    query_vector_np = np.array(query_vector).astype('float32')
    distances, indices = index.search(query_vector_np, request.k)

    retrieved_texts = []
    sources = []
    
    for i, idx in enumerate(indices[0]):
        if idx == -1: continue
        chunk_file = chunk_map[idx]
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                text = data[0]['text']
                source_name = os.path.basename(chunk_file).replace(".json", "")
                retrieved_texts.append(f"- {text}")
                sources.append(source_name)
        except:
            continue

    context_block = "\n".join(retrieved_texts)

    # B) MESAJLARI HAZIRLAMA (Llama 3.1 İçin)
    messages_payload = []

    # 1. System Prompt (Terapist Rolü)
    system_prompt = f"""
    Sen Bilişsel Davranışçı Terapi (BDT) tekniklerini uygulayan, empatik bir yapay zeka psikoloji asistanısın.
    
    Aşağıdaki KİTAP BİLGİLERİNİ (CONTEXT) referans alarak cevap ver:
    {context_block}

    KURALLAR:
    1. Sohbet geçmişine bakarak tutarlı ol.
    2. ASLA "Kitapta şöyle yazar" deme, bilgiyi sohbetin içine doğal bir şekilde yedir.
    3. Kullanıcıya Sokratik sorular sorarak (örn: "Bu düşüncenin kanıtı ne?") farkındalık kazandır.
    4. Empatik, sıcak ve yargısız ol.
    5. ASLA tıbbi teşhis koyma. İntihar eğilimi sezersen 112'ye yönlendir.
    """
    
    messages_payload.append({'role': 'system', 'content': system_prompt})

    # 2. Geçmiş Sohbeti Ekle
    for msg in request.history:
        # Bizim modelimizde 'model' rolü var, Ollama 'assistant' istiyor.
        ollama_role = 'assistant' if msg.role == 'model' else 'user'
        messages_payload.append({'role': ollama_role, 'content': msg.content})

    # 3. Son Soruyu Ekle
    messages_payload.append({'role': 'user', 'content': request.query})

    # C) GENERATION (Ollama - Llama 3.1)
    try:
        response = ollama.chat(model=LLM_MODEL, messages=messages_payload)
        ai_reply = response['message']['content']
    except Exception as e:
        ai_reply = f"Llama 3.1 Hatası: {str(e)}. (Ollama uygulamasının açık ve 'llama3.1' modelinin yüklü olduğundan emin ol)"

    return {
        "reply": ai_reply,
        "sources": list(set(sources))
    }