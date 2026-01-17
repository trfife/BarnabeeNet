"""Pronunciation corrections for TTS.

Maps words/names to phonetic spellings that Kokoro pronounces correctly.
Add entries here when you discover mispronunciations.
"""

# Family names and custom pronunciations
# Format: "original": "phonetic_spelling"
PRONUNCIATION_MAP = {
    # Family names
    "Viola": "Vyola",
    "viola": "Vyola",
    "VIOLA": "Vyola",
    "Xander": "Zander",
    "xander": "Zander",
    "XANDER": "Zander",
    # Add more as needed:
    # "WiFi": "Why-Fy",
    # "HVAC": "H-V-A-C",
}


def preprocess_text(text: str) -> str:
    """Apply pronunciation corrections to text before TTS.

    Args:
        text: Original text to speak

    Returns:
        Text with pronunciation corrections applied
    """
    result = text
    for original, phonetic in PRONUNCIATION_MAP.items():
        result = result.replace(original, phonetic)
    return result
