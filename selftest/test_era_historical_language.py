from app.eras.era_history import get_eras, get_historical_eras, get_plateau_era, get_modulo_era

def test_historical_eras_do_not_reference_modulo():
    for era in get_historical_eras():
        blob = " ".join([era.title, era.summary, " ".join(era.what_was_possible)]).lower()
        assert "modulo" not in blob

def test_plateau_summary_does_not_reference_modulo():
    era = get_plateau_era()
    blob = " ".join([era.title, era.summary, " ".join(era.what_was_possible)]).lower()
    assert "modulo" not in blob

def test_only_final_era_mentions_modulo():
    eras = get_eras()
    hits = [e.era_id for e in eras if "modulo" in (" ".join([e.title, e.summary, " ".join(e.what_was_possible)]).lower())]
    assert hits == [get_modulo_era().era_id]
