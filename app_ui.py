import streamlit as st
import requests
import database as db
import time

st.set_page_config(page_title="Psikoloji AI", page_icon="🧠", layout="wide")

API_URL = "http://127.0.0.1:8000/chat"

if "user" not in st.session_state:
    st.session_state.user = None 
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "bg_image" not in st.session_state:
    st.session_state.bg_image = "linear-gradient(to right, #e0eafc, #cfdef3)"

THEMES = {
    "Soft Mavi (Varsayılan)": "linear-gradient(to right, #e0eafc, #cfdef3)",
    "Sıcak Bej": "linear-gradient(to right, #fdfbfb, #ebedee)",
    "Mistik Dağlar": "url('https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1920&q=80')",
    "Sakin Orman": "url('https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1920&q=80')",
    "Huzurlu Okyanus": "url('https://images.unsplash.com/photo-1505118380757-91f5f5632de0?auto=format&fit=crop&w=1920&q=80')",
    "Yıldızlı Gece": "url('https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?auto=format&fit=crop&w=1920&q=80')"
}

st.markdown(f"""
<style>
    /* Ana Arka Plan */
    .stApp {{
        background: {st.session_state.bg_image};
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    /* Yazı Renkleri */
    .stMarkdown, .stText, h1, h2, h3, p {{ color: #333333 !important; }}
    .stTextInput input {{ background-color: #ffffff !important; color: #333333 !important; border: 1px solid #d1d5db; }}
    
    /* Sidebar */
    section[data-testid="stSidebar"] {{ background-color: rgba(255, 255, 255, 0.95) !important; border-right: 1px solid #e5e7eb; }}
    section[data-testid="stSidebar"] * {{ color: #333333 !important; }}

    /* Sohbet Balonları */
    .chat-user {{
        background-color: #2563eb; color: white !important; padding: 15px 20px;
        border-radius: 20px 20px 5px 20px; margin: 10px 0; text-align: right;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); display: inline-block; font-size: 16px;
    }}
    .chat-ai {{
        background-color: #ffffff; color: #1f2937 !important; padding: 15px 20px;
        border-radius: 20px 20px 20px 5px; margin: 10px 0; text-align: left;
        border: 1px solid #f3f4f6; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        display: inline-block; font-size: 16px;
    }}

    /* KRİZ UYARI KUTUSU CSS (YENİ) */
    .crisis-alert {{
        background-color: #fee2e2; 
        color: #991b1b !important;
        padding: 20px;
        border-radius: 10px;
        border-left: 8px solid #ef4444;
        font-weight: bold;
        box-shadow: 0 10px 15px -3px rgba(239, 68, 68, 0.2);
        margin: 10px 0;
        font-size: 16px;
    }}
</style>
""", unsafe_allow_html=True)

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style='background-color: rgba(255, 255, 255, 0.95); padding: 40px; border-radius: 24px; text-align: center; margin-top: 60px;'>
            <h1 style='color:#2563eb; font-size: 3rem;'>🧠 Psikoloji AI</h1>
            <p style='color:#6b7280;'>Güvenli, Gizli ve Empatik Destek Alanınız.</p>
        </div>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Giriş Yap", "Kayıt Ol"])

        with tab1:
            username = st.text_input("Kullanıcı Adı", key="login_user")
            password = st.text_input("Şifre", type="password", key="login_pass")
            if st.button("Giriş Yap", type="primary", use_container_width=True):
                user = db.login_user(username, password)
                if user:
                    st.session_state.user = user
                    st.success(f"Hoş geldin {user[2]}!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Hatalı bilgiler.")

        with tab2:
            new_user = st.text_input("Kullanıcı Adı (Giriş için)", key="reg_user")
            new_pass = st.text_input("Şifre", type="password", key="reg_pass")
            new_name = st.text_input("Görünen Adın", key="reg_name")
            new_age = st.number_input("Yaşın", min_value=10, max_value=99, step=1, key="reg_age")
            new_gender = st.selectbox("Cinsiyet", ["Belirtilmedi", "Kadın", "Erkek"], key="reg_gender")
            
            if st.button("Kayıt Ol", use_container_width=True):
                if new_user and new_pass and new_name:
                    if db.register_user(new_user, new_pass, new_name, new_age, new_gender):
                        st.success("Kayıt Başarılı! Giriş yapabilirsin.")
                    else:
                        st.error("Bu kullanıcı adı dolu.")
                else:
                    st.warning("Lütfen tüm alanları doldur.")

def chat_page():
    user = st.session_state.user
    
    with st.sidebar:
        # Avatar ve Bilgi Kartı
        avatar = '👩' if user[4] == 'Kadın' else '👨' if user[4] == 'Erkek' else '👤'
        st.markdown(f"""
        <div style='text-align:center;padding:20px;background:#f3f4f6;border-radius:15px;margin-bottom:20px; border:1px solid #e5e7eb;'>
            <div style='font-size:50px;'>{avatar}</div>
            <h3 style='margin: 10px 0; color:#1f2937 !important;'>{user[2]}</h3>
            <p style='color:#6b7280 !important; font-size: 0.9rem;'>{user[4]}, {user[3]} Yaşında</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Profil Ayarları (Eski koddan geri geldi)
        with st.expander("⚙️ Profil Ayarları"):
            new_name = st.text_input("Adın", value=user[2])
            new_age = st.number_input("Yaşın", value=user[3])
            
            options = ["Belirtilmedi", "Kadın", "Erkek"]
            try:
                current_idx = options.index(user[4])
            except ValueError:
                current_idx = 0
            new_gender = st.selectbox("Cinsiyet", options, index=current_idx)
            
            if st.button("Güncelle"):
                updated = db.update_profile(user[0], new_name, new_age, new_gender, "default")
                st.session_state.user = updated
                st.success("Güncellendi!")
                time.sleep(0.5)
                st.rerun()

        # Tema Seçici (Eski koddan geri geldi)
        with st.expander("🎨 Görünüm & Atmosfer"):
            selected_theme_name = st.selectbox("Bir Atmosfer Seç:", list(THEMES.keys()))
            if st.button("Uygula"):
                st.session_state.bg_image = THEMES[selected_theme_name]
                st.rerun()

        st.divider()
        st.subheader("🗂️ Sohbet Geçmişi")
        if st.button("➕ Yeni Sohbet Başlat", use_container_width=True):
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.rerun()

        sessions = db.get_user_sessions(user[0])
        for sess in sessions:
            b_type = "primary" if st.session_state.current_session_id == sess[0] else "secondary"
            sess_title = (sess[1][:22] + '..') if len(sess[1]) > 22 else sess[1]
            if st.button(f"📄 {sess_title}", key=sess[0], type=b_type, use_container_width=True):
                st.session_state.current_session_id = sess[0]
                st.session_state.messages = db.get_session_messages(sess[0])
                st.rerun()
        
        st.divider()
        if st.button("Çıkış Yap"):
            st.session_state.user = None
            st.rerun()

    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 30px;'>
        <h2 style='color: #1f2937; margin-bottom: 5px;'>Merhaba {user[2]}, seni dinliyorum.</h2>
        <p style='color: #6b7280; font-size: 0.95rem;'>Bugün zihninden neler geçiyor?</p>
    </div>
    """, unsafe_allow_html=True)
    
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            st.markdown(f"<div style='display:flex;justify-content:flex-end;'><div class='chat-user'>{content}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='display:flex;justify-content:flex-start;'><div style='margin-right:12px; font-size:28px; padding-top:10px;'>🧠</div><div class='chat-ai'>{content}</div></div>", unsafe_allow_html=True)

    if prompt := st.chat_input("Buraya yaz..."):
        if st.session_state.current_session_id is None:
            title = (prompt[:25] + '..') if len(prompt) > 25 else prompt
            sess_id = db.create_session(user[0], title)
            st.session_state.current_session_id = sess_id
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        db.save_message(st.session_state.current_session_id, "user", prompt)
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.spinner("Düşünüyor..."):
            try:
                # Profil ve Geçmiş Hazırlığı
                prof = {"name": user[2], "age": user[3], "gender": user[4]}
                hist = [{"role": "user" if m["role"] == "user" else "model", "content": m["content"]} for m in st.session_state.messages[:-1]]
                
                payload = {
                    "query": st.session_state.messages[-1]["content"],
                    "history": hist,
                    "user_profile": prof,
                    "k": 3
                }
                
            
                response = requests.post(API_URL, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    reply = data["reply"]
                    is_crisis = data.get("is_crisis", False)

                    if is_crisis:
                        st.markdown(f"<div class='crisis-alert'>🚨 {reply}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='display:flex;justify-content:flex-start;'><div style='margin-right:12px; font-size:28px; padding-top:10px;'>🧠</div><div class='chat-ai'>{reply}</div></div>", unsafe_allow_html=True)
                    
                    st.session_state.messages.append({"role": "model", "content": reply})
                    db.save_message(st.session_state.current_session_id, "model", reply)
                else:
                    st.error(f"Sunucu Hatası: {response.status_code}")
            except Exception as e:
                st.error(f"Bağlantı Hatası: {e}")

if st.session_state.user:
    chat_page()
else:
    login_page()