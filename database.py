import sqlite3
import hashlib
from datetime import datetime

DB_NAME = "psychbot.db"

# --- 1. VERİTABANI KURULUMU ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Kullanıcılar Tablosu (Gelişmiş Profil)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE, 
                  password_hash TEXT,
                  display_name TEXT,
                  age INTEGER,
                  gender TEXT,
                  avatar TEXT)''')
    
    # Sohbet Oturumları
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  title TEXT, 
                  created_at TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    # Mesajlar
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  session_id INTEGER, 
                  role TEXT, 
                  content TEXT, 
                  created_at TIMESTAMP,
                  FOREIGN KEY(session_id) REFERENCES sessions(id))''')
    
    conn.commit()
    conn.close()

# --- 2. KULLANICI İŞLEMLERİ ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, display_name, age, gender):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # Varsayılan avatar 'default'
        c.execute("INSERT INTO users (username, password_hash, display_name, age, gender, avatar) VALUES (?, ?, ?, ?, ?, ?)", 
                  (username, hash_password(password), display_name, age, gender, 'default'))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tüm profil bilgilerini çekiyoruz
    c.execute("SELECT id, username, display_name, age, gender, avatar FROM users WHERE username=? AND password_hash=?", 
              (username, hash_password(password)))
    user = c.fetchone()
    conn.close()
    return user # (id, username, display_name, age, gender, avatar)

def update_profile(user_id, display_name, age, gender, avatar):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET display_name=?, age=?, gender=?, avatar=? WHERE id=?", 
              (display_name, age, gender, avatar, user_id))
    conn.commit()
    conn.close()
    
    # Güncel bilgiyi geri döndür
    c = conn.cursor()
    c.execute("SELECT id, username, display_name, age, gender, avatar FROM users WHERE id=?", (user_id,))
    updated_user = c.fetchone()
    conn.close()
    return updated_user

# --- 3. SOHBET İŞLEMLERİ ---
def create_session(user_id, title="Yeni Sohbet"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (user_id, title, created_at) VALUES (?, ?, ?)", 
              (user_id, title, datetime.now()))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def get_user_sessions(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title FROM sessions WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    sessions = c.fetchall()
    conn.close()
    return sessions

def save_message(session_id, role, content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)", 
              (session_id, role, content, datetime.now()))
    conn.commit()
    conn.close()

def get_session_messages(session_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY created_at ASC", (session_id,))
    messages = [{"role": role, "content": content} for role, content in c.fetchall()]
    conn.close()
    return messages

# Dosya import edildiğinde tabloları oluştur
init_db()