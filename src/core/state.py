"""
@ai-context: Manages the real-time state of the application,
storing and indexing detected UI elements from EasyOCR
for fast retrieval during OS action events.

DÜZELTMELER (v2):
- difflib.SequenceMatcher → rapidfuzz.fuzz.WRatio (3-4x hızlı, daha isabetli)
- Türkçe karakter normalize eklendi: "Müzikler" = "Muzikler" = "muzikier" eşleşir
- Eşik 0.5 → 0.65 (daha az false positive)
- Normalize edilmiş isimle karşılaştırma yapılıyor, orijinal UIElement korunuyor
"""

from pydantic import BaseModel, Field

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    import difflib
    _RAPIDFUZZ_AVAILABLE = False


# ─── Yardımcı fonksiyon ────────────────────────────────────────────────────────

def _normalize_tr(text: str) -> str:
    """
    Türkçe karakterleri ASCII karşılığına çevirir ve küçük harfe alır.
    EasyOCR'ın "Müzikler" → "Muzikier" gibi okuduğu vakalarda
    her iki tarafı da normalize edince fuzzy eşleşme çalışır.
    """
    text = text.lower().strip()
    for tr_char, en_char in {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's',
        'ö': 'o', 'ç': 'c', 'î': 'i', 'â': 'a', 'û': 'u',
    }.items():
        text = text.replace(tr_char, en_char)
    return text


def _similarity(a: str, b: str) -> float:
    """
    İki string arasındaki benzerlik skoru (0.0 – 1.0).
    rapidfuzz varsa WRatio kullanır (token sırası farklı olsa çalışır),
    yoksa difflib fallback'e geçer.
    """
    if _RAPIDFUZZ_AVAILABLE:
        return _fuzz.WRatio(_normalize_tr(a), _normalize_tr(b)) / 100.0
    else:
        return difflib.SequenceMatcher(
            None, _normalize_tr(a), _normalize_tr(b)
        ).ratio()


# ─── Modeller ──────────────────────────────────────────────────────────────────

class UIElement(BaseModel):
    """
    Standardized data model representing a detected UI element on the screen.
    Originates from EasyOCR (text).
    """
    name: str = Field(..., description="Detected text")
    element_type: str = Field(..., description="'text' for OCR detections")
    x: float = Field(..., description="Center X coordinate")
    y: float = Field(..., description="Center Y coordinate")
    width: float = Field(..., description="Width of the bounding box")
    height: float = Field(..., description="Height of the bounding box")
    confidence: float = Field(..., description="Detection confidence score (0.0 to 1.0)")


class ApplicationState:
    """
    Singleton-like central state manager for the application.
    Holds the latest vision data (UI elements) for quick retrieval.
    """

    _instance: "ApplicationState | None" = None

    def __new__(cls) -> "ApplicationState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "elements"):
            self.elements: list[UIElement] = []

    def update_vision_state(self, elements: list[UIElement]) -> None:
        """Overwrites old memory to keep state strictly real-time."""
        self.elements = elements.copy()

    def find_element(self, query: str) -> UIElement | None:
        """
        Searches for an element matching the query.

        Öncelik sırası:
        1. Tam eşleşme (normalize edilmiş) → skor 1.0
        2. İçerme kontrolü (target, element içinde geçiyor mu?)
        3. rapidfuzz WRatio (≥ 0.65 eşiği)

        Eşit skor varsa confidence skoru yüksek olan kazanır.
        """
        if not self.elements:
            return None

        norm_query = _normalize_tr(query)
        best_element: UIElement | None = None
        best_ratio: float = 0.0

        for el in self.elements:
            norm_name = _normalize_tr(el.name)

            # 1. Tam eşleşme
            if norm_query == norm_name:
                ratio = 1.0
            # 2. İçerme (her iki yön)
            elif norm_query in norm_name or norm_name in norm_query:
                # Uzun string içinde kısa string varsa kısmi puan ver
                ratio = 0.9
            # 3. Fuzzy
            else:
                ratio = _similarity(query, el.name)

            # FIX: Eşik 0.5 → 0.65 (false positive azalır)
            if ratio >= 0.65:
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_element = el
                elif ratio == best_ratio and best_element is not None:
                    # Aynı skorda confidence yüksek olanı tercih et
                    if el.confidence > best_element.confidence:
                        best_element = el

        return best_element