import os
import json
import faiss
import numpy as np
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# --- GEMINI & KRİZ MODÜLÜ ---
import google.generativeai as genai
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

# ==========================================
# 🔑 API KEY AYARI
# (Kendi anahtarını tırnak içine yapıştır)
# ==========================================
GEMINI_API_KEY = ""

# --- AYARLAR ---
VECTOR_STORE_DIR = "data/vector_store"
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2'
SENTIMENT_MODEL_ID = "savasy/bert-base-turkish-sentiment-cased"

app = FastAPI(title="Psikoloji AI Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Değişkenler
embedding_model = None
index = None
chunk_map = None
sentiment_tokenizer = None
sentiment_model = None

@app.on_event("startup")
def load_resources():
    global embedding_model, index, chunk_map, sentiment_tokenizer, sentiment_model
    print("🚀 SİSTEM BAŞLATILIYOR...")
    
    # 1. Embedding Model (CPU - Bilgisayarı yormaz)
    print("📦 1. Embedding Modeli (CPU) Yükleniyor...")
    embedding_model = SentenceTransformer(MODEL_NAME, device='cpu')
    
    try:
        index = faiss.read_index(os.path.join(VECTOR_STORE_DIR, "vector_store.index"))
        with open(os.path.join(VECTOR_STORE_DIR, "chunk_map.json"), 'r', encoding='utf-8') as f:
            chunk_map = json.load(f)
        print("✅ RAG Veritabanı Hazır!")
    except Exception as e:
        print(f"❌ RAG Yükleme Hatası: {e}")

    # 2. Kriz Modeli (CPU)
    try:
        print("📦 2. Kriz Modeli (CPU) Yükleniyor...")
        sentiment_tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL_ID)
        sentiment_model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL_ID).to("cpu")
        print("✅ Kriz Modeli Hazır!")
    except Exception as e:
        print(f"❌ Kriz Modeli Hatası: {e}")

# --- GELİŞMİŞ KRİZ TESPİTİ (Filtreli) ---
def detect_crisis(text):
    if not sentiment_model or not sentiment_tokenizer:
        return False, 0.0

    # 1. ADIM: HIZLI FİLTRE (Keywords)
    # Eğer bu kelimeler yoksa, modeli boşuna çalıştırma ve alarm verme.
    risk_keywords = [
        "ölmek", "intihar", "canıma kıy", "dayanamıyorum", "bıktım", "hap iç", 
        "kendimi kes", "yaşamak istemiyorum", "her şey bitsin", "veda", 
        "artık son", "kimse beni sevmiyor", "kurtulmak istiyorum"
    ]
    
    text_lower = text.lower()
    keyword_hit = any(word in text_lower for word in risk_keywords)

    # Eğer riskli kelime HİÇ yoksa, direkt güvenli kabul et.
    if not keyword_hit:
        return False, 0.0

    # 2. ADIM: DERİN ANALİZ (Model)
    # Sadece riskli kelime varsa buraya girer.
    inputs = sentiment_tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
    inputs = {key: val.to("cpu") for key, val in inputs.items()}

    with torch.no_grad():
        logits = sentiment_model(**inputs).logits
    
    probabilities = torch.softmax(logits, dim=1)
    
    # savasy modelinde genelde: Index 0 -> Negatif, Index 1 -> Pozitif olabilir
    # Ancak biz keyword kontrolü yaptığımız için sadece negatif skora bakacağız.
    # Genelde Index 0 negatiftir bu modelde.
    negative_score = probabilities[0][0].item() 

    print(f"🔍 Kriz Analizi: '{text}' | Kelime: Var | Negatiflik: {negative_score:.4f}")

    # KURAL: Hem kelime geçecek HEM DE model %70 üstü negatif diyecek.
    # Veya kelime çok net "intihar" ise skora bakmadan uyar.
    is_crisis = False
    
    if negative_score > 0.70:
        is_crisis = True
    elif "intihar" in text_lower or "ölmek" in text_lower:
        is_crisis = True
        
    return is_crisis, negative_score

# --- VERİ MODELLERİ ---
class Message(BaseModel):
    role: str
    content: str

class UserProfile(BaseModel):
    name: str = "Kullanıcı"
    age: int = 0
    gender: str = "Belirtilmedi"

class ChatRequest(BaseModel):
    query: str
    history: List[Message] = []
    user_profile: Optional[UserProfile] = None
    k: int = 3

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    # 1. KRİZ KONTROLÜ
    is_crisis, confidence = detect_crisis(request.query)
    
    if is_crisis:
        print(f"🚨 KRİZ TESPİT EDİLDİ! Skor: {confidence:.4f}")
        return {
            "reply": (
                "⚠️ **ÖNEMLİ UYARI:** Yazdıklarınızdan zor bir süreçten geçtiğiniz anlaşılıyor. "
                "Lütfen yalnız kalmayın.\n\n"
                "**Acil Destek:**\n"
                "- 📞 **112** Acil Çağrı\n"
                "- 📞 **ALO 183** Sosyal Destek"
            ),
            "sources": ["KRİZ PROTOKOLÜ"],
            "is_crisis": True 
        }

    # 2. RAG ARAMASI
    try:
        query_vector = embedding_model.encode([request.query])
        distances, indices = index.search(np.array(query_vector).astype('float32'), request.k)

        retrieved_texts = []
        sources = []
        if chunk_map:
            for i, idx in enumerate(indices[0]):
                if idx == -1: continue
                try:
                    # JSON keyleri string olabilir, int'e çeviriyoruz veya tam tersi
                    chunk_file = chunk_map[str(idx)] if str(idx) in chunk_map else chunk_map[idx]
                    
                    with open(chunk_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        retrieved_texts.append(f"- {data[0]['text']}")
                        sources.append(os.path.basename(chunk_file))
                except: continue
        
        context_block = "\n".join(retrieved_texts)
    except Exception as e:
        print(f"RAG Hatası: {e}")
        context_block = ""

    # 3. GEMINI HAZIRLIĞI
    genai.configure(api_key=GEMINI_API_KEY)
    
    profile_text = ""
    if request.user_profile:
        p = request.user_profile
        profile_text = f"KULLANICI PROFİLİ: Adı: {p.name}, Yaşı: {p.age}, Cinsiyeti: {p.gender}."

    system_instruction = f"""
    Sen Bilişsel Davranışçı Terapi (BDT) konusunda uzman, empatik bir yapay zeka psikoloji asistanısın.
    
    {profile_text}
    
    AŞAĞIDAKİ KAYNAK BİLGİLERİ (CONTEXT) KULLANARAK CEVAP VER:
    {context_block}

    KURALLAR:
    1. Kullanıcıya ismiyle hitap et ve "sen" dili kullan.
    2. Context içindeki bilimsel bilgileri sohbetin içine doğalca yedir.
    3. Kullanıcıya tavsiye vermek yerine, onu düşündürecek sorular sor (Sokratik Sorgulama).
    4. Samimi ve kısa tut.
    5. Cevaplarında "Yapay zeka", "Dil modeli", "Bilgi kesilme tarihi" gibi robotik ifadeler KULLANMA.
    """

    # Model İsmi Düzeltildi: gemini-2.5-flash
    model = genai.GenerativeModel(
        'gemini-2.5-flash',
        system_instruction=system_instruction
    )

    gemini_history = []
    for msg in request.history:
        role = 'user' if msg.role == 'user' else 'model'
        gemini_history.append({'role': role, 'parts': [msg.content]})

    try:
        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(request.query)
        ai_reply = response.text
    except Exception as e:
        ai_reply = f"Bağlantı hatası oluştu: {str(e)}"

    return {"reply": ai_reply, "sources": list(set(sources)), "is_crisis": False}
