from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

print("⏳ Kriz Modeli Test İçin Yükleniyor...")
SENTIMENT_MODEL_ID = "savasy/bert-base-turkish-sentiment-cased" 
tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL_ID)
sentiment_model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL_ID)
print("✅ Model Yüklendi.")

def test_detect_crisis(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
    with torch.no_grad():
        logits = sentiment_model(**inputs).logits
    
    probabilities = torch.softmax(logits, dim=1)
    negative_score = probabilities[0][0].item()
    
    risk_keywords = ["ölmek", "intihar", "canıma", "dayanamıyorum", "bıktım", "hap", "kesmek"]
    keyword_hit = any(word in text.lower() for word in risk_keywords)

    is_crisis = False
    if (negative_score > 0.9) or (negative_score > 0.7 and keyword_hit):
        is_crisis = True
        
    return is_crisis, negative_score

# TEST VERİLERİ
test_sentences = [
    ("Bugün hava çok güzel, kendimi harika hissediyorum.", False), 
    ("Sınavdan düşük aldım biraz moralim bozuk.", False),       
    ("Artık yaşamak istemiyorum, her şey bitti.", True),       
    ("Bu acıya dayanamıyorum, intiharı düşünüyorum.", True),                 
    ("Çok yorgunum ama yarın düzelir diye umuyorum.", False),        
    ("Bıktım artık bu hayattan, kendimi keseceğim.", True)            
]

print("\n--- KRİZ MODÜLÜ DOĞRULUK TESTİ ---\n")
correct = 0
for text, expected in test_sentences:
    prediction, score = test_detect_crisis(text)
    result = "✅" if prediction == expected else "❌"
    if prediction == expected: correct += 1
    
    label = "KRİZ 🚨" if prediction else "NORMAL 😊"
    print(f"Metin: '{text}'")
    print(f"Tahmin: {label} (Negatiflik: {score:.4f}) | Beklenen: {expected}")
    print(f"Sonuç: {result}\n")

acc = (correct / len(test_sentences)) * 100
print(f"Genel Doğruluk: %{acc:.2f}")