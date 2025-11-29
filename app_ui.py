# app_ui.py
import streamlit as st
import requests
import database as db
import time

# --- AYARLAR ---
API_URL = "http://127.0.0.1:8000/chat"

# Sayfa Yapılandırması
st.set_page_config(page_title="Psikoloji AI", page_icon="🧠", layout="wide")

# --- OTURUM YÖNETİMİ ---
if "user" not in st.session_state:
    st.session_state.user = None
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 1. GİRİŞ / KAYIT EKRANI ---
def login_page():
    st.markdown("<h1 style='text-align: center;'>🧠 Psikoloji AI Asistanı</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Giriş Yap", "Kayıt Ol"])

    with tab1:
        username = st.text_input("Kullanıcı Adı", key="login_user")
        password = st.text_input("Şifre", type="password", key="login_pass")
        if st.button("Giriş Yap", use_container_width=True):
            user = db.login_user(username, password)
            if user:
                st.session_state.user = user # (id, username)
                st.success(f"Hoş geldin {username}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Kullanıcı adı veya şifre hatalı.")

    with tab2:
        new_user = st.text_input("Yeni Kullanıcı Adı", key="reg_user")
        new_pass = st.text_input("Yeni Şifre", type="password", key="reg_pass")
        if st.button("Kayıt Ol", use_container_width=True):
            if db.register_user(new_user, new_pass):
                st.success("Kayıt başarılı! Şimdi giriş yapabilirsin.")
            else:
                st.error("Bu kullanıcı adı zaten alınmış.")

# --- 2. ANA SOHBET EKRANI ---
def chat_page():
    # --- A) SOL MENÜ (GEÇMİŞ) ---
    with st.sidebar:
        st.title(f"👤 {st.session_state.user[1]}")
        if st.button("➕ Yeni Sohbet", use_container_width=True):
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.rerun()
        
        st.divider()
        st.subheader("Geçmiş Sohbetler")
        
        sessions = db.get_user_sessions(st.session_state.user[0])
        for sess in sessions:
            if st.button(f"📄 {sess[1]}", key=sess[0], use_container_width=True):
                # Seçilen sohbeti yükle
                st.session_state.current_session_id = sess[0]
                st.session_state.messages = db.get_session_messages(sess[0])
                st.rerun()
        
        st.divider()
        if st.button("Çıkış Yap", type="primary"):
            st.session_state.user = None
            st.rerun()

    # --- B) SOHBET ALANI ---
    st.title("Psikoloji Destek Asistanı")
    
    # Mesajları Ekrana Bas
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "assistant"
        avatar = "👤" if role == "user" else "🧠"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg["content"])

    # --- C) YENİ MESAJ GÖNDERME ---
    if prompt := st.chat_input("Nasıl hissediyorsun?"):
        # 1. Yeni sohbetse veritabanında oturum aç
        if st.session_state.current_session_id is None:
            # İlk mesajı başlık yap (kısaltarak)
            title = (prompt[:30] + '..') if len(prompt) > 30 else prompt
            session_id = db.create_session(st.session_state.user[0], title)
            st.session_state.current_session_id = session_id
        
        # 2. Kullanıcı mesajını ekle ve kaydet
        st.session_state.messages.append({"role": "user", "content": prompt})
        db.save_message(st.session_state.current_session_id, "user", prompt)
        
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        # 3. API'ye Gönder
        with st.chat_message("assistant", avatar="🧠"):
            with st.spinner("Düşünüyor..."):
                try:
                    # Geçmişi API formatına çevir
                    api_history = [{"role": "user" if m["role"] == "user" else "model", "content": m["content"]} 
                                   for m in st.session_state.messages[:-1]] # Son mesaj hariç geçmiş
                    
                    payload = {"query": prompt, "history": api_history, "k": 3}
                    
                    response = requests.post(API_URL, json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        reply = data["reply"]
                        
                        # Cevabı yazdır
                        st.markdown(reply)
                        
                        # Kaynakları göster (Opsiyonel)
                        if data.get("sources"):
                            with st.expander("📚 Yararlanılan Kaynaklar"):
                                for s in data["sources"]:
                                    st.caption(f"• {s}")
                        
                        # 4. Asistan cevabını kaydet
                        st.session_state.messages.append({"role": "model", "content": reply})
                        db.save_message(st.session_state.current_session_id, "model", reply)
                    else:
                        st.error("Sunucu hatası oluştu.")
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")

# --- 3. YÖNLENDİRME ---
if st.session_state.user:
    chat_page()
else:
    login_page()