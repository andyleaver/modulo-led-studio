from app.eras.era_history import get_eras, get_historical_eras, get_plateau_era, get_modulo_era, get_workbench_for_era

def _blob(era):
    wb = get_workbench_for_era(era)
    parts = [era.title, era.summary, " ".join(era.what_was_possible)]
    if wb is not None:
        parts.append(wb.goal)
        parts.append(" ".join(wb.verify_steps))
    return " ".join(parts).lower()

def test_historical_and_plateau_workbench_copy_do_not_reference_modulo():
    for era in list(get_historical_eras()) + [get_plateau_era()]:
        assert "modulo" not in _blob(era)

def test_only_modulo_era_lacks_historical_workbench_and_mentions_modulo():
    modulo = get_modulo_era()
    assert get_workbench_for_era(modulo) is None
    assert "modulo" in _blob(modulo)

def test_indicator_eras_do_not_teach_dimming_before_alert_and_lighting_eras():
    era_1962 = next(e for e in get_eras() if e.era_id == "era_1962_red")
    era_1972 = next(e for e in get_eras() if e.era_id == "era_1972_yellow_green")
    era_1980s = next(e for e in get_eras() if e.era_id == "era_1980s_high_brightness")
    era_1996 = next(e for e in get_eras() if e.era_id == "era_1996_white")

    assert "dim" not in _blob(era_1962)
    assert "dim" not in _blob(era_1972)
    assert "brightness" in _blob(era_1980s)
    assert "dim" in _blob(era_1996)

def test_rgb_era_requires_mixed_hue_not_forced_white_demo():
    era_1993 = next(e for e in get_eras() if e.era_id == "era_1993_blue")
    blob = _blob(era_1993)
    assert "mixed hue" in blob
    assert "make white" not in blob
