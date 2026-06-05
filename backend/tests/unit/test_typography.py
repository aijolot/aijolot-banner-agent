from app.schemas.typography import coerce_pairing, DISPLAY_FONTS, BODY_FONTS

def test_coerce_keeps_allowed_caseinsensitive():
    assert coerce_pairing("fraunces", "dm sans") == ("Fraunces", "DM Sans")

def test_coerce_falls_back_offlist():
    assert coerce_pairing("Comic Sans", "Wingdings") == ("Space Grotesk", "Inter")

def test_allowlists_nonempty():
    assert "Inter" in BODY_FONTS and "Space Grotesk" in DISPLAY_FONTS
