# notebooks/process_pdfs.py

from pathlib import Path
import fitz  # PyMuPDF
from tqdm import tqdm
import sys
import re
import json

# --- 1. AYARLAR ---

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_PATH = BASE_DIR / "data" / "raw"
CHUNK_PATH = BASE_DIR / "data" / "chunks"
RAW_PATH.mkdir(parents=True, exist_ok=True)
CHUNK_PATH.mkdir(parents=True, exist_ok=True)

# --- SENİN İSTEĞİN ÜZERİNE YENİ KONTROL MERKEZİ ---
# Her bir PDF için hangi sayfaların işleneceğini buradan belirliyoruz.
# 'start_page': Metin işlemeye başlanacak sayfa (sayfa 1'den başlar).
# 'skip_end_pages': Kitabın sonundan atlanacak sayfa sayısı (kaynakça, dizin vb. için).
PDF_PROCESSING_RULES = {
    "bilissel_terapi_1.pdf": {"start_page": 15, "skip_end_pages": 10},
    "bilissel_terapi_2.pdf": {"start_page": 20, "skip_end_pages": 15},
    "bilissel_terapi_3_ocr.pdf": {"start_page": 15, "skip_end_pages": 20}
}
# EĞER SONUÇLAR İYİ OLMAZSA, İLK OLARAK BU SAYILARI DEĞİŞTİRMEK GEREKİR.

# Chunk ayarları
CHUNK_SIZE_IN_WORDS = 450
CHUNK_OVERLAP_IN_WORDS = 50

# Bilinen OCR hataları
OCR_CORRECTIONS = {
    'ý': 'ı', 'ð': 'ğ', 'þ': 'ş', 'Ý': 'İ', 'Ð': 'Ğ', 'Þ': 'Ş',
    'ýn': 'ın', 'ýz': 'ız', 'ým': 'ım', 'ýl': 'ıl', 'Cf§)': '', '•': '',
    'yaµ;umkırı': 'yaşamları', 'bn´vuranların qüncel': 'başvuranların güncel',
    'ar.ılı.klan uzatm~': 'aralıkları uzatma',
}

# --- 2. YARDIMCI FONKSİYONLAR (DEĞİŞİKLİK YOK) ---

def correct_ocr_errors(text):
    for wrong, right in OCR_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text

def clean_text_basic(text):
    text = correct_ocr_errors(text)
    text = re.sub(r'-\s*\n', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text, chunk_size, overlap):
    words = text.split()
    if not words: return []
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
    return chunks

# --- 3. ANA İŞLEM AKIŞI (TAMAMEN YENİLENDİ) ---

# Başlamadan önce eski chunk'ları temizle
print("Eski chunk dosyaları temizleniyor...")
for file in CHUNK_PATH.glob("*.json"):
    file.unlink()

pdfs = list(RAW_PATH.glob("*.pdf"))
if not pdfs:
    print("HATA: data/raw içinde PDF bulunamadı.")
    sys.exit(1)

for pdf_path in tqdm(pdfs, desc="PDF'ler işleniyor"):
    pdf_name = pdf_path.name
    
    # Kural setinde bu PDF için bir kural var mı kontrol et
    if pdf_name not in PDF_PROCESSING_RULES:
        print(f"\nUYARI: '{pdf_name}' için bir işleme kuralı bulunamadı. Bu dosya atlanıyor.")
        continue

    try:
        doc = fitz.open(pdf_path)
        
        # Sayfa numarası kuralını al
        rules = PDF_PROCESSING_RULES[pdf_name]
        start_page = rules['start_page'] - 1  # fitz 0'dan başlar
        end_page = len(doc) - rules['skip_end_pages']
        
        print(f"\n'{pdf_name}' işleniyor: Sayfa {start_page + 1}'den Sayfa {end_page}'e kadar.")
        
        # Sadece belirlenen aralıktaki sayfaları oku
        full_text = ""
        for page_num in range(start_page, end_page):
            if page_num < len(doc):
                full_text += doc[page_num].get_text("text", sort=True)
        
        # Metni temizle
        prepared_text = clean_text_basic(full_text)
        
        # Metni parçalara ayır
        chunks = chunk_text(prepared_text, CHUNK_SIZE_IN_WORDS, CHUNK_OVERLAP_IN_WORDS)
        
        if not chunks:
            print(f"UYARI: {pdf_name} için hiç chunk oluşturulamadı.")
            continue
            
        # Chunk'ları JSON'a yaz
        items = []
        for i, c in enumerate(chunks):
            items.append({
                "text": c,
                "source": str(pdf_name),
                "chunk_id": f"{pdf_path.stem}_{i}"
            })
            
        out_file = CHUNK_PATH / (pdf_path.stem + ".json")
        out_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    except Exception as e:
        print(f"HATA: {pdf_name} işlenirken bir hata oluştu: {e}")

print("\n✅ Sayfa numarası kontrollü veri işleme ve parçalama tamamlandı!")
print(f"Oluşturulan chunk dosyaları: {CHUNK_PATH}")