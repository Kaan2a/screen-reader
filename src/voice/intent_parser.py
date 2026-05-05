"""
@ai-context: Parses natural language strings into structured
ParsedCommand objects. Cleans Turkish suffixes to ensure exact
keyword matching with the Vision map state.
"""

import re

from pydantic import BaseModel, Field


class ParsedCommand(BaseModel):
    """Standardized data model representing a parsed voice command."""

    action: str = Field(
        ...,
        description="The intended action (e.g., 'click', 'double_click')",
    )
    target: str = Field(
        ...,
        description="The cleaned target name without Turkish suffixes",
    )


class CommandParser:
    """Parses raw spoken text into actionable intents."""

    def __init__(self) -> None:
        """Initializes the parser."""

    def _clean_target_name(self, target: str) -> str:
        """Removes common Turkish suffixes from the target name."""
        target = re.sub(r"'\w+", "", target)

        words: list[str] = target.split()
        if not words:
            return target

        last_word: str = words[-1]

        if len(last_word) > 4:
            if last_word.endswith(("ya", "ye", "yi", "yu", "yu")):
                words[-1] = last_word[:-2]
            elif last_word.endswith(("na", "ne", "ni", "nu", "nu")):
                words[-1] = last_word[:-2]

        return " ".join(words).strip()

    def parse(self, raw_text: str) -> ParsedCommand | None:
        """Analyzes raw text to extract action and target."""
        if not raw_text:
            return None

        text_lower: str = raw_text.lower().strip()
        # Noktalama işaretlerini temizle (Whisper genellikle sonuna nokta ekler)
        text_lower = re.sub(r"[^\w\s]", "", text_lower)
        action: str = "double_click"  # Varsayılan olarak uygulama açmak için çift tıklama kullan

        if "cift" in text_lower or "iki kere" in text_lower:
            action = "double_click"
        elif "ac" in text_lower or "calistir" in text_lower:
            action = "double_click"
        elif "sag tikla" in text_lower:
            action = "right_click"
        elif "tikla" in text_lower or "bas" in text_lower:
            action = "click"
        elif "yaz" in text_lower:
            action = "type"

        cleaned_text: str = text_lower
        action_verbs: list[str] = [
            "cift tikla",
            "iki kere tikla",
            "sag tikla",
            "tikla",
            "bas",
            "ac",
            "calistir",
            "yaz",
            "lutfen",
        ]

        for verb in action_verbs:
            cleaned_text = cleaned_text.replace(verb, "")

        raw_target: str = cleaned_text.strip()

        if not raw_target:
            return None

        cleaned_target: str = self._clean_target_name(raw_target)

        return ParsedCommand(action=action, target=cleaned_target)


if __name__ == "__main__":
    print("Initializing CommandParser...")
    parser: CommandParser = CommandParser()

    test_commands: list[str] = [
        "Chrome'a cift tikla",
        "Excel'i ac",
        "Dosyaya tikla",
        "hesap makinesini calistir",
        "Geri donusum kutusuna sag tikla",
    ]

    for cmd in test_commands:
        print(f"\nHam Metin: '{cmd}'")
        parsed: ParsedCommand | None = parser.parse(cmd)
        if parsed:
            print(f"Ayristirilan: Action={parsed.action}, Target={parsed.target}")
        else:
            print("Ayristirilamadi.")
