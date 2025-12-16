import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# --- VERİLER ---
metrics_data = {
    "Metrik": ["Genel Doğruluk (Accuracy)", "Ortalama Cevap Süresi (Latency)", "Normal Durum F1-Score", "Kriz Durumu F1-Score"],
    "Değer": ["%85.00", "2.64 sn", "0.87", "0.82"]
}

class_data = {
    "Sınıf": ["Normal Durum", "Kriz Durumu"],
    "Precision": [0.77, 1.00],
    "Recall": [1.00, 0.70],
    "F1-Score": [0.87, 0.82]
}

# --- 1. TABLO GÖRSELİ OLUŞTURMA ---
fig, ax = plt.subplots(figsize=(8, 3))
ax.axis('tight')
ax.axis('off')
table_data = [[k, v] for k, v in zip(metrics_data["Metrik"], metrics_data["Değer"])]
table = ax.table(cellText=table_data, colLabels=["Metrik", "Değer"], cellLoc='center', loc='center')
table.auto_set_font_size(False)
table.set_fontsize(12)
table.scale(1.2, 1.8)

# Renklendirme
for (row, col), cell in table.get_celld().items():
    if row == 0:
        cell.set_facecolor('#40466e') # Başlık Rengi (Koyu Mavi)
        cell.set_text_props(color='white', weight='bold')
    elif row > 0:
        cell.set_facecolor('#f1f1f2' if row % 2 == 0 else '#ffffff') # Satır Renkleri

plt.title("Sistem Performans Özeti", fontsize=14, weight='bold', color='#333333')
plt.savefig("performans_tablosu.png", bbox_inches='tight', dpi=300)
print("✅ performans_tablosu.png oluşturuldu.")

# --- 2. GRAFİK OLUŞTURMA (BAR CHART) ---
df = pd.DataFrame(class_data)
labels = df["Sınıf"]
precision = df["Precision"]
recall = df["Recall"]
f1 = df["F1-Score"]

x = np.arange(len(labels))
width = 0.25

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width, precision, width, label='Precision (Kesinlik)', color='#2ecc71')
rects2 = ax.bar(x, recall, width, label='Recall (Duyarlılık)', color='#3498db')
rects3 = ax.bar(x + width, f1, width, label='F1-Score', color='#e67e22')

ax.set_ylabel('Skor (0-1 Arası)')
ax.set_title('Normal vs Kriz Durumu Başarım Analizi', fontsize=14, weight='bold')
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=12)
ax.legend()
ax.set_ylim(0, 1.1)
ax.grid(axis='y', linestyle='--', alpha=0.7)

# Değerleri çubukların üzerine yaz
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.2f}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', weight='bold')

autolabel(rects1)
autolabel(rects2)
autolabel(rects3)

plt.tight_layout()
plt.savefig("siniflandirma_grafigi.png", dpi=300)
print("✅ siniflandirma_grafigi.png oluşturuldu.")