# 🎙️ Otonom Screen Reader & Commander

**Otonom Screen Reader & Commander**, Windows bilgisayarınızı tamamen sesli komutlar ve yapay zeka görsel analiz yetenekleriyle "eller serbest" (hands-free) kontrol etmenizi sağlayan gelişmiş bir Python uygulamasıdır. Klasik erişilebilirlik araçlarından farklı olarak arka planda modern derin öğrenme modellerini (YOLO ve OCR) kullanır.

## 🎯 Projenin Amacı

Amacımız, ekran üzerinde gördüğümüz ancak işletim sisteminin standart erişilebilirlik API'lerine takılmayan (örneğin resim formatındaki butonlar, oyun içi menüler vb.) her türlü ikonu, logoyu ve yazıyı gerçek zamanlı analiz ederek, sesli komutlarla tetiklenebilir otonom bir asistan yaratmaktır.

Ekranın köşesinde sürekli en üstte duran küçük, mütevazı bir arayüz (100x100px) üzerinden çalışır, ancak arka planda bilgisayarı tamamen kontrol edecek "Agentic" (Otonom) zekaya sahiptir.

## 🚀 Neler Yapabilir?

- **Akıllı İkon Tanıma:** Ekranda yer alan "Google Chrome", "Geri Dönüşüm Kutusu", "Oyun İkonu" gibi sembolleri saniyenin kesirleri içinde YOLO modelleriyle bulur.
- **Metin Okuma (OCR):** Ekrandaki herhangi bir yazıyı, menü seçeneğini okur.
- **Otonom Tıklama:** Sesli olarak "Chrome'u aç" dediğinizde, Chrome ikonunun koordinatlarını bulur, fareyi oraya götürür ve çift tıklar.
- **Menü Gezinmesi:** "Dosya menüsüne tıkla" komutuyla ekrandaki "Dosya" yazısını bulur ve etkileşime girer.
- **Asenkron Çalışma:** Ekran analizi ve ses dinleme işlemleri, sistemi kilitmeden arka planda eş zamanlı çalışır.

---

## ⚙️ Nasıl Çalışır ve Temel Python Event'leri (Olaylar)

Uygulama, kendi içinde "Domain Driven Design" (Alan Odaklı Tasarım) standartlarıyla ayrılmış birbirinden bağımsız modüllerden oluşur. Her bir modül bir "Olay" (Event) tetikler.

### Akış Senaryosu: "Spotify'ı Aç"

Aşağıda uygulamanın arka planda işlettiği Python "Event" (Olay) döngüsü adım adım açıklanmıştır:

1. **`VoiceListenerEvent` (Sesin Dinlenmesi ve Çözümlenmesi)**
   - **Tetiklenme:** Kullanıcı mikrofondan "Spotify'ı aç" der.
   - **İşlem:** Sistem (SpeechRecognition) bu sesi metne dönüştürür. Hedef kelime olarak "Spotify"ı ayıklar.
   - **Çıktı:** `{"action": "double_click", "target": "Spotify"}`

2. **`ScreenCaptureEvent` (Ekranın Fotoğraflanması)**
   - **Tetiklenme:** Yeni bir hedef belirlendiğinde anında devreye girer.
   - **İşlem:** `mss` kütüphanesi CPU'yu yormadan o saniyenin mili-saniyelik ekran görüntüsünü yakalar.
   - **Çıktı:** `numpy.ndarray` formatında görüntü matrisi.

3. **`VisionAnalysisEvent` (Yapay Zeka ile Arama)**
   - **Tetiklenme:** Ekran görüntüsü yakalandığında tetiklenir.
   - **İşlem:**
     - Görüntü `ultralytics` YOLO modeline veya `EasyOCR` a gönderilir.
     - Model tüm ekranı tarar ve Spotify ikonunu/yazısını bulur.
   - **Çıktı:** Bounding Box Koordinatları `(X: 1200, Y: 450, Genişlik: 50, Yükseklik: 50)`

4. **`OSActionEvent` (Fiziksel Eylemin Gerçekleştirilmesi)**
   - **Tetiklenme:** Koordinatlar başarıyla bulunduğunda çalışır.
   - **İşlem:** `pyautogui` kütüphanesi farenin kontrolünü alır. Hızlıca X:1225, Y:475 (merkez nokta) koordinatlarına fareyi taşır.
   - **Çıktı:** Fare işlemi (Çift Tıklama) gerçekleştirilir.

---

## 🛠️ Teknoloji Yığını (Tech Stack)

- **Dil:** Python 3.12+ (Tam tip güvenliği - Type Hints)
- **Arayüz (GUI):** `customtkinter` (Modern, siyah/beyaz mod destekli, Always-on-top yetenekli)
- **Ekran Yakalama:** `mss` (Performans odaklı screenshot kütüphanesi)
- **Bilgisayarlı Görü (CV):** `ultralytics` (YOLOv8/11) ve `OpenCV`
- **Optik Karakter Tanıma (OCR):** `EasyOCR`
- **Ses İşleme (NLP):** `SpeechRecognition`
- **OS Kontrolü:** `pyautogui`

---

## 🧠 Geliştirme Standartları

Bu proje **%100 AI Native** (Yapay Zeka Odaklı) standartlarla geliştirilmiştir:

- Hiçbir değişkende `any` tipi kullanılmaz.
- Tüm fonksiyonlar ne yaptığını tam olarak açıklayan (SRP - Tek Sorumluluk Prensibi) isimlere sahiptir.
- Kod bloğu başlangıçlarında yapay zeka ajanlarının (Agent) bağlamı anlaması için `@ai-context` etiketleri yer alır.
