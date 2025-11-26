import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import time

# --- 1. AYARLAR VE SABİTLER ---

# Okunacak chunk'ların ve kaydedilecek vektörlerin klasör yolları
CHUNKS_DIR = "data/chunks"
VECTOR_STORE_DIR = "data/vector_store"

# Kullanacağımız Embedding Modeli
# Bu model çok dilli ve Türkçe için oldukça başarılı.
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2'

# --- 2. GEREKLİ KLASÖRÜN OLUŞTURULMASI ---

# Eğer vektör deposu klasörü yoksa, oluştur.
if not os.path.exists(VECTOR_STORE_DIR):
    os.makedirs(VECTOR_STORE_DIR)
    print(f"Klasör oluşturuldu: {VECTOR_STORE_DIR}")

# --- 3. EMBEDDING MODELİNİ YÜKLEME ---

print(f"'{MODEL_NAME}' modeli yükleniyor...")
# Bu satır, modeli Hugging Face'ten indirip belleğe yükler.
# İlk çalıştırmada internet bağlantısı gerekir ve biraz uzun sürebilir.
model = SentenceTransformer(MODEL_NAME)
print("Model başarıyla yüklendi.")

# --- 4. CHUNK'LARI OKUMA VE VEKTÖRE DÖNÜŞTÜRME ---

# Chunk metinlerini ve dosya yollarını saklamak için boş listeler
all_texts = []
chunk_file_paths = []

print(f"'{CHUNKS_DIR}' klasöründeki chunk'lar okunuyor...")

# Chunk klasöründeki tüm dosyaları al ve sırala (sıralama önemli!)
chunk_files = sorted(os.listdir(CHUNKS_DIR))

# Her bir json dosyası için işlem yap
for filename in chunk_files:
    if filename.endswith(".json"):
        filepath = os.path.join(CHUNKS_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_texts.append(data[0]) 
            chunk_file_paths.append(filepath)

if not all_texts:
    print("HATA: Chunk klasöründe işlenecek metin bulunamadı. Lütfen bir önceki adımı kontrol et.")
else:
    print(f"Toplam {len(all_texts)} adet chunk bulundu. Embedding işlemi başlıyor...")
    start_time = time.time()
    
    # İşte sihirli an! Tüm metin listesini modele verip embedding'leri oluşturuyoruz.
    # Bu işlem, chunk sayısına ve bilgisayarının CPU gücüne bağlı olarak zaman alabilir.
    embeddings = model.encode(all_texts, show_progress_bar=True)
    
    end_time = time.time()
    print(f"Embedding işlemi {end_time - start_time:.2f} saniyede tamamlandı.")

    # --- 5. FAISS VERİTABANINI OLUŞTURMA VE KAYDETME ---
    
    # NumPy array'ine dönüştürmek FAISS için daha verimlidir.
    embeddings_np = np.array(embeddings).astype('float32')

    # Vektörlerin boyutunu (dimension) al (bu model için 768 olmalı)
    d = embeddings_np.shape[1]

    # FAISS index'ini oluşturuyoruz. IndexFlatL2 en temel ve güçlü index türlerinden biridir.
    # Vektörler arasındaki 'Euclidean' mesafeyi kullanarak arama yapar.
    index = faiss.IndexFlatL2(d)
    
    print("FAISS index'i oluşturuldu.")

    # Tüm embedding'leri FAISS index'ine ekliyoruz.
    index.add(embeddings_np)

    print(f"Toplam {index.ntotal} vektör FAISS index'ine eklendi.")

    # --- 6. OLUŞTURULAN VERİLERİ KAYDETME ---
    
    # FAISS index'ini diske kaydediyoruz.
    faiss.write_index(index, os.path.join(VECTOR_STORE_DIR, "vector_store.index"))
    
    # Vektörlerin hangi chunk'a ait olduğunu bilmek için dosya yollarını da kaydediyoruz.
    with open(os.path.join(VECTOR_STORE_DIR, "chunk_map.json"), 'w', encoding='utf-8') as f:
        json.dump(chunk_file_paths, f)
        
    print("FAISS index'i ('vector_store.index') ve chunk haritası ('chunk_map.json') başarıyla kaydedildi.")
    print("3. Adım başarıyla tamamlandı!")