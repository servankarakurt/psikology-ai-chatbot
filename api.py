import os
import json
import base64
import time
import threading
import secrets
from datetime import datetime, timedelta, timezone
import faiss
import numpy as np
from typing import List, Optional, Dict
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
import requests
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

# --- GEMINI & KRİZ MODÜLÜ ---
import google.generativeai as genai
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

# --- API ANAHTARLARI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost,http://127.0.0.1").split(",") if origin.strip()]
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
MOBILE_CHAT_RATE_LIMIT_PER_MIN = int(os.getenv("MOBILE_CHAT_RATE_LIMIT_PER_MIN", "12"))

# --- AYARLAR ---
VECTOR_STORE_DIR = "data/vector_store"
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2'
SENTIMENT_MODEL_ID = "savasy/bert-base-turkish-sentiment-cased"

app = FastAPI(title="Psikoloji AI Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
bearer_scheme = HTTPBearer(auto_error=False)
rate_limit_store: Dict[str, deque] = defaultdict(deque)
rate_limit_lock = threading.Lock()

def _enforce_rate_limit(key: str, limit: int, window_seconds: int = 60):
    now = time.time()
    with rate_limit_lock:
        q = rate_limit_store[key]
        while q and (now - q[0]) > window_seconds:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Çok fazla istek gönderildi. Lütfen kısa süre sonra tekrar deneyin.",
            )
        q.append(now)

def create_access_token(user_id: int):
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY tanımlı değil.")

    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: int):
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    db.store_refresh_token(user_id, token, expires_at)
    return token

def _auth_response(user: dict, message: str):
    return {
        "message": message,
        "user": user,
        "access_token": create_access_token(user["id"]),
        "refresh_token": create_refresh_token(user["id"]),
        "token_type": "bearer",
    }

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY tanımlı değil.")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yetkilendirme gerekli.",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Geçersiz token.")
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş token.")

    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
    return user

def assert_session_owner(session_id: int, current_user_id: int):
    owner_id = db.get_session_owner(session_id)
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Sohbet oturumu bulunamadı.")
    if owner_id != current_user_id:
        raise HTTPException(status_code=403, detail="Bu oturuma erişim izniniz yok.")

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
    profession: str = ""
    city: str = ""
    marital_status: str = "Belirtilmedi"
    child_count: int = 0
    chronic_illness: str = ""
    trauma_summary: str = ""

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    age: int
    gender: str
    profession: str = ""
    city: str = ""
    marital_status: str = "Belirtilmedi"
    child_count: int = 0
    chronic_illness: str = ""
    trauma_summary: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class GoogleLoginRequest(BaseModel):
    id_token: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str

class UpdateProfileRequest(BaseModel):
    display_name: str
    age: int
    gender: str
    profession: str = ""
    city: str = ""
    marital_status: str = "Belirtilmedi"
    child_count: int = 0
    chronic_illness: str = ""
    trauma_summary: str = ""
    avatar: str = "default"

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[int] = None
    user_id: Optional[int] = None
    history: List[Message] = Field(default_factory=list)
    user_profile: Optional[UserProfile] = None
    k: int = 3

# --- KİMLİK DOĞRULAMA (AUTH) UÇ NOKTALARI ---
import database as db

@app.post("/auth/register")
async def register_endpoint(req: RegisterRequest):
    user = db.register_user(
        username=req.username,
        password=req.password,
        display_name=req.display_name,
        age=req.age,
        gender=req.gender,
        profession=req.profession,
        city=req.city,
        marital_status=req.marital_status,
        child_count=req.child_count,
        chronic_illness=req.chronic_illness,
        trauma_summary=req.trauma_summary
    )
    if not user:
        raise HTTPException(status_code=400, detail="Kullanıcı adı zaten alınmış veya hata oluştu.")
    return _auth_response(user, "Kayıt başarılı")

@app.post("/auth/login")
async def login_endpoint(req: LoginRequest):
    user = db.login_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Hatalı kullanıcı adı veya şifre.")
    return _auth_response(user, "Giriş başarılı")

def _resolve_google_user(id_token: str):
    if not id_token:
        raise HTTPException(status_code=400, detail="id_token zorunludur.")
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID tanımlı değil.")

    try:
        payload = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Google token doğrulanamadı: {exc}") from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Geçersiz Google token.")

    display_name = payload.get("name") or "Google Kullanıcısı"
    username = f"google_{sub}"
    user = db.get_user_by_username(username)
    if user:
        return user
    return db.create_google_user(username=username, display_name=display_name)

@app.post("/auth/google")
async def google_login_endpoint(req: GoogleLoginRequest):
    user = _resolve_google_user(req.id_token)
    if not user:
        raise HTTPException(status_code=500, detail="Google kullanıcı kaydı oluşturulamadı.")
    return _auth_response(user, "Google girişi başarılı")

@app.post("/auth/refresh")
async def refresh_endpoint(req: RefreshTokenRequest):
    user = db.validate_refresh_token(req.refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş refresh token.")

    # Tek kullanımlık güvenli yaklaşım: eski refresh token iptal edilir, yenisi üretilir.
    db.revoke_refresh_token(req.refresh_token)
    return {
        "access_token": create_access_token(user["id"]),
        "refresh_token": create_refresh_token(user["id"]),
        "token_type": "bearer",
    }

@app.post("/auth/logout")
async def logout_endpoint(req: LogoutRequest):
    revoked = db.revoke_refresh_token(req.refresh_token)
    return {"message": "Çıkış başarılı", "revoked": revoked}

@app.get("/users/{user_id}/profile")
async def get_user_profile(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Bu profile erişim izniniz yok.")
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    return {"user": user}

@app.put("/users/{user_id}/profile")
async def update_user_profile(user_id: int, req: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Bu profili güncelleme izniniz yok.")
    existing_user = db.get_user_by_id(user_id)
    if not existing_user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

    updated_user = db.update_profile(
        user_id=user_id,
        display_name=req.display_name,
        age=req.age,
        gender=req.gender,
        profession=req.profession,
        city=req.city,
        marital_status=req.marital_status,
        child_count=req.child_count,
        chronic_illness=req.chronic_illness,
        trauma_summary=req.trauma_summary,
        avatar=req.avatar,
    )
    return {"message": "Profil güncellendi", "user": updated_user}

def transcribe_with_groq(audio_bytes: bytes, filename: str, content_type: str) -> str:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY tanımlı değil.")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Ses dosyası boş.")

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={
                "file": (filename or "recording.wav", audio_bytes, content_type or "audio/wav")
            },
            data={"model": "whisper-large-v3-turbo"},
            timeout=90,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Groq STT bağlantı hatası: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Groq STT hatası ({response.status_code}): {response.text}",
        )

    data = response.json()
    transcript = data.get("text", "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="Ses metne çevrilemedi.")
    return transcript

def generate_tts_elevenlabs(text: str) -> bytes:
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY tanımlı değil.")
    if not ELEVENLABS_VOICE_ID:
        raise HTTPException(status_code=500, detail="ELEVENLABS_VOICE_ID tanımlı değil.")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Ses üretmek için metin boş olamaz.")

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
    }
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

    try:
        response = requests.post(
            url,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"ElevenLabs bağlantı hatası: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"ElevenLabs TTS hatası ({response.status_code}): {response.text}",
        )
    return response.content

def _build_profile_text(user_profile: Optional[UserProfile]) -> str:
    if not user_profile:
        return ""

    return f"""
    [KULLANICI BİLGİLERİ]
    Adı: {user_profile.name}
    Yaşı: {user_profile.age}
    Cinsiyeti: {user_profile.gender}
    Mesleği: {user_profile.profession}
    Yaşadığı Şehir: {user_profile.city}
    Medeni Durumu: {user_profile.marital_status}
    Çocuk Sayısı: {user_profile.child_count}
    Kronik Rahatsızlığı: {user_profile.chronic_illness}
    Biline Travmaları: {user_profile.trauma_summary}
    
    LÜTFEN TAVSİYELERİNDE VE EMPATİ KURARKEN KULLANICININ MESLEĞİNİN STRESİNİ, YAŞADIĞI ŞEHRİN KÜLTÜRÜNÜ, MEDENİ HALİNİ, ÇOCUK SAYISININ GETİRDİĞİ SORUMLULUKLARI VE KRONİK RAHATSIZLIKLARINI DİKKATE AL.
    """

def _retrieve_context(query: str, k: int):
    sources = []
    context_block = ""
    if not embedding_model or index is None:
        return context_block, sources

    try:
        query_vector = embedding_model.encode([query])
        _, indices = index.search(np.array(query_vector).astype("float32"), k)
        retrieved_texts = []
        if chunk_map:
            for idx in indices[0]:
                if idx == -1:
                    continue
                try:
                    chunk_file = chunk_map[str(idx)] if str(idx) in chunk_map else chunk_map[idx]
                    with open(chunk_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        retrieved_texts.append(f"- {data[0]['text']}")
                        sources.append(os.path.basename(chunk_file))
                except Exception:
                    continue
        context_block = "\n".join(retrieved_texts)
    except Exception as exc:
        print(f"RAG Hatası: {exc}")
    return context_block, sources

def _build_gemini_history(current_session_id: Optional[int], request_history: List[Message]):
    gemini_history = []
    if current_session_id:
        db_history = db.get_session_messages(current_session_id)
        for msg in db_history[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})
    else:
        for msg in request_history:
            role = "user" if msg.role == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg.content]})
    return gemini_history

def _run_chat_flow(
    query: str,
    session_id: Optional[int],
    current_user_id: int,
    history: List[Message],
    user_profile: Optional[UserProfile],
    k: int,
):
    current_session_id = session_id

    if current_session_id:
        assert_session_owner(current_session_id, current_user_id)

    if not current_session_id:
        title = (query[:25] + "..") if len(query) > 25 else query
        current_session_id = db.create_session(current_user_id, title=title)

    if current_session_id:
        db.save_message(current_session_id, "user", query)

    is_crisis, confidence = detect_crisis(query)
    if is_crisis:
        print(f"🚨 KRİZ TESPİT EDİLDİ! Skor: {confidence:.4f}")
        reply_text = (
            "⚠️ **ÖNEMLİ UYARI:** Yazdıklarınızdan zor bir süreçten geçtiğiniz anlaşılıyor. "
            "Lütfen yalnız kalmayın.\n\n"
            "**Acil Destek:**\n"
            "- 📞 **112** Acil Çağrı\n"
            "- 📞 **ALO 183** Sosyal Destek"
        )
        if current_session_id:
            db.save_message(current_session_id, "model", reply_text)
        return {
            "reply": reply_text,
            "sources": ["KRİZ PROTOKOLÜ"],
            "is_crisis": True,
            "session_id": current_session_id,
        }

    context_block, sources = _retrieve_context(query, k)
    profile_text = _build_profile_text(user_profile)

    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY tanımlı değil.")
    genai.configure(api_key=GEMINI_API_KEY)

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

    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
    gemini_history = _build_gemini_history(current_session_id, history)

    try:
        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(query)
        ai_reply = response.text
    except Exception as exc:
        ai_reply = f"Bağlantı hatası oluştu: {str(exc)}"

    if current_session_id:
        db.save_message(current_session_id, "model", ai_reply)

    return {
        "reply": ai_reply,
        "sources": list(set(sources)),
        "is_crisis": False,
        "session_id": current_session_id,
    }

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    return _run_chat_flow(
        query=request.query,
        session_id=request.session_id,
        current_user_id=current_user["id"],
        history=request.history,
        user_profile=request.user_profile,
        k=request.k,
    )

@app.post("/mobile-chat")
async def mobile_chat_endpoint(
    audio_file: UploadFile = File(...),
    user_name: str = Form("Kullanıcı"),
    age: int = Form(0),
    gender: str = Form("Belirtilmedi"),
    profession: str = Form(""),
    city: str = Form(""),
    marital_status: str = Form("Belirtilmedi"),
    child_count: int = Form(0),
    chronic_illness: str = Form(""),
    trauma_summary: str = Form(""),
    session_id: Optional[int] = Form(None),
    k: int = Form(3),
    current_user: dict = Depends(get_current_user),
):
    _enforce_rate_limit(
        key=f"mobile-chat:{current_user['id']}",
        limit=MOBILE_CHAT_RATE_LIMIT_PER_MIN,
        window_seconds=60,
    )

    audio_bytes = await audio_file.read()
    transcript = transcribe_with_groq(audio_bytes, audio_file.filename or "audio.wav", audio_file.content_type or "audio/wav")

    user_profile = UserProfile(
        name=user_name,
        age=age,
        gender=gender,
        profession=profession,
        city=city,
        marital_status=marital_status,
        child_count=child_count,
        chronic_illness=chronic_illness,
        trauma_summary=trauma_summary,
    )

    chat_result = _run_chat_flow(
        query=transcript,
        session_id=session_id,
        current_user_id=current_user["id"],
        history=[],
        user_profile=user_profile,
        k=k,
    )

    audio_base64 = None
    tts_error = None
    try:
        audio_bytes_reply = generate_tts_elevenlabs(chat_result["reply"])
        audio_base64 = base64.b64encode(audio_bytes_reply).decode("utf-8")
    except HTTPException as exc:
        tts_error = exc.detail

    return {
        "reply": chat_result["reply"],
        "transcript": transcript,
        "sources": chat_result["sources"],
        "is_crisis": chat_result["is_crisis"],
        "session_id": chat_result["session_id"],
        "audio_base64": audio_base64,
        "tts_error": tts_error,
    }

# --- GEÇMİŞ SOHBETLER (HISTORY) UÇ NOKTALARI ---

@app.get("/chat/sessions/{user_id}")
async def get_sessions(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Bu oturumlara erişim izniniz yok.")
    sessions = db.get_user_sessions(user_id)
    return {"sessions": sessions}

@app.get("/chat/history/{session_id}")
async def get_history(session_id: int, current_user: dict = Depends(get_current_user)):
    assert_session_owner(session_id, current_user["id"])
    messages = db.get_session_messages(session_id)
    return {"messages": messages}

@app.post("/chat/sessions")
async def create_new_session(title: str = "Yeni Sohbet", is_voice_session: bool = False, current_user: dict = Depends(get_current_user)):
    session_id = db.create_session(current_user["id"], title, is_voice_session)
    return {"session_id": session_id}

@app.post("/chat/messages")
async def save_chat_message(
    session_id: int,
    role: str,
    content: str,
    audio_url: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    assert_session_owner(session_id, current_user["id"])
    message_id = db.save_message(session_id, role, content, audio_url)
    return {"message_id": message_id}
