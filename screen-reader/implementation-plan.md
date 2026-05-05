# Screen Reader - Implementation Plan

Bu doküman, Principal Product Manager ve Architect Software tarafından onaylanmış adım adım geliştirme planını (Checklist) içerir. Tüm adımlar Agentic Workflows prensiplerine ve `%100 AI Native` kodlama standartlarına uygun olarak gerçekleştirilecektir.

## 🏁 Aşama 1: Proje Kurulumu ve Çekirdek Arayüz (Core GUI)
- [ ] Python 3.12+ sanal ortamının (virtual environment) kurulması.
- [ ] Gerekli kütüphanelerin (`customtkinter`, `mss`, `pyautogui`, `ultralytics`, vb.) projeye eklenmesi.
- [ ] AI Native dizin mimarisinin (`src/gui`, `src/vision`, `src/voice`, `src/os_control`) oluşturulması.
- [ ] 100x100px boyutunda, Windows ekranında her zaman üstte kalacak (always-on-top) ana kontrol arayüzünün kodlanması.

## 👁️ Aşama 2: Ekran Analizi ve Görsel İşleme (Vision & OCR)
- [ ] `@ai-context` etiketiyle `src/vision/screen_capture.py` modülünün oluşturulması.
- [ ] `mss` kütüphanesi ile ekran görüntülerinin çok hızlı, donma yapmadan alınmasının sağlanması.
- [ ] YOLOv8/v11 (ultralytics) modelinin projeye entegre edilmesi ve masaüstü/uygulama ikonlarının koordinatlarının (X, Y, W, H) tespit edilmesi.
- [ ] `EasyOCR` veya `pytesseract` ile ekrandaki menü/buton metinlerinin (Text Extraction) ayıklanması.
- [ ] Tespit edilen ikon ve metinlerin uygulamanın anlık durum hafızasına (State) kaydedilmesi.

## 🖱️ Aşama 3: İşletim Sistemi Kontrolü (OS Control & Action)
- [ ] `src/os_control/mouse_actions.py` modülününSRP kurallarına göre oluşturulması.
- [ ] `pyautogui` veya `pynput` kullanılarak hedeflenen (X, Y) koordinatlarına farenin hareket ettirilmesi.
- [ ] Fare ile ikonlar veya metinler üzerine çift tıklama (Double Click) işleminin yazılması.
- [ ] Çözünürlük değişikliklerinde koordinat oranlamasının (Scaling) hatasız hesaplanması.

## 🎤 Aşama 4: Ses Tanıma ve Komut İşleme (Voice & NLP)
- [ ] `src/voice/listener.py` ve `src/voice/parser.py` modüllerinin yazılması.
- [ ] Mikrofon girişinin arka planda asenkron olarak dinlenmesi.
- [ ] Sesin metne (Speech-to-Text) dönüştürülmesi.
- [ ] Söylenen cümlenin (Örn: "Google Chrome'u aç") işlenip, hedefin (Chrome) Vision haritası üzerinde aranacak anahtar kelime olarak belirlenmesi.

## 🤖 Aşama 5: Otonom Entegrasyon ve Akış (Agentic Flow)
- [ ] Ses dinleme -> Metni analiz etme -> Ekranda arama -> Fareyi götürüp çift tıklama akışının birleştirilmesi.
- [ ] GUI üzerinden mikrofonun açık/kapalı durumu ile uygulamanın o an ne yaptığı (Dinliyor, Arıyor, Tıklıyor) bilgisinin gösterilmesi.
- [ ] Hata yönetimi (Error Boundaries): Ses anlaşılamazsa veya ekranda ikon/metin bulunamazsa sistemin çökmesini engelleyecek Guard Clause (Erken dönüş) yapılarının kurulması.

## 🧪 Aşama 6: QA, Performans ve Test (Staff QA Engineer)
- [ ] Tüm kod tabanının strict (katı) Tip Kontrolü (Type Checking) ve Linting aşamalarından geçmesi.
- [ ] `any` tiplerinin temizlenmesi ve tüm fonksiyonlara JSDoc tarzı açıklamaların eklenmesi.
- [ ] YOLO ve OCR süreçlerinin CPU/RAM tüketimlerinin ölçülmesi; arayüzü dondurmayacak şekilde thread optimizasyonu yapılması.
- [ ] Çoklu ekran ve farklı DPI (Ölçekleme) durumlarında tıklama hassasiyetinin (Precision) test edilmesi.
