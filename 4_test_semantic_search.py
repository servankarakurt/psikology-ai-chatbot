# 4_test_semantic_search.py

import json
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# --- 1. AYARLAR VE SABİTLER ---

VECTOR_STORE_DIR = "data/vector_store"
MODEL_NAME = 'paraphrase-multilingual-mpnet-base-v2'
K = 5 # Arama sonucunda kaç tane en alakalı chunk'ı getirmek istediğimiz

# --- 2. GEREKLİ DOSYALARI VE MODELİ YÜKLEME ---

print("Gerekli dosyalar ve model yükleniyor...")

# FAISS index'ini yükle
index = faiss.read_index(os.path.join(VECTOR_STORE_DIR, "vector_store.index"))

# Chunk haritasını yükle
with open(os.path.join(VECTOR_STORE_DIR, "chunk_map.json"), 'r', encoding='utf-8') as f:
    chunk_map = json.load(f)

# Embedding modelini yükle
model = SentenceTransformer(MODEL_NAME)

print("Yükleme tamamlandı. Sistem aramaya hazır.")

# --- 3. ARAMA FONKSİYONU ---

def search(query: str, k: int = K):
    """
    Verilen bir sorgu metni için anlamsal arama yapar ve en alakalı
    chunk'ları döndürür.
    """
    print(f"\n🔎 Arama yapılıyor: '{query}'")
    
    # 1. Sorguyu vektöre çevir
    query_vector = model.encode([query])
    query_vector_np = np.array(query_vector).astype('float32')

    # 2. FAISS'te arama yap
    # D: Mesafeler (distances), I: İndeksler (indices)
    distances, indices = index.search(query_vector_np, k)

    print(f"En alakalı {k} sonuç bulundu:")
    
    # 3. Sonuçları işle ve yazdır
    results = []
    for i, idx in enumerate(indices[0]):
        # Bulunan index'e karşılık gelen dosya yolunu haritadan al
        chunk_file = chunk_map[idx]
        
        # O chunk'ın metnini dosyadan oku
        with open(chunk_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            text = data[0]['text']

        result = {
            "rank": i + 1,
            "index": int(idx),
            "distance": float(distances[0][i]),
            "text": text.strip(),
            "source": chunk_file
        }
        results.append(result)

        print("-" * 20)
        print(f"Rank: {result['rank']} | Benzerlik Skoru (Mesafe): {result['distance']:.4f}")
        print(f"Kaynak: {result['source']}")
        print("Bulunan Metin:")
        print(result['text'])
        
    return results

# --- 4. TEST SORGULARI ---

if __name__ == "__main__":
    # Test etmek için bir soru soralım
    # PDF'in içeriğiyle alakalı bir soru sormak en iyi sonucu verir.
    
    # Örnek 1
    search("Bilişsel çarpıtma nedir?")
    
    # Örnek 2
    # search("Depresyonun belirtileri nelerdir?")
    
    # Örnek 3
    # search("Terapide kullanılan temel teknikler hangileridir?")