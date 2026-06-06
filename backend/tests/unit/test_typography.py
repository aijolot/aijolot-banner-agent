from app.schemas.typography import coerce_pairing, DISPLAY_FONTS, BODY_FONTS

def test_coerce_keeps_allowed_caseinsensitive():
    assert coerce_pairing("fraunces", "dm sans") == ("Fraunces", "DM Sans")

def test_coerce_falls_back_offlist():
    assert coerce_pairing("Comic Sans", "Wingdings") == ("Space Grotesk", "Inter")

def test_allowlists_nonempty():
    assert "Inter" in BODY_FONTS and "Space Grotesk" in DISPLAY_FONTS


def test_clamp_layout_ranges_and_align():
    from app.schemas.typography import ArtDirection, clamp_layout
    ad = ArtDirection(display="Anton", body="Karla", text_x=999, text_w=5, hero_x=-10, text_align="weird")
    L = clamp_layout(ad)
    assert 2 <= L["textX"] <= 60
    assert 24 <= L["textW"] <= 66
    assert 20 <= L["heroX"] <= 98
    assert L["textAlign"] == "left"  # invalid → default
    assert L["aspectRatio"] == 2.4
