"""Selftest for export.signal_expr_map"""

from export.signal_expr_map import arduino_expr_for_signal


def main():
    assert arduino_expr_for_signal("audio_energy") == "g_energy"
    assert arduino_expr_for_signal("audio_peak") == "g_peak"
    assert arduino_expr_for_signal("audio_mono_0") == "g_mono[0]"
    assert arduino_expr_for_signal("audio_mono_6") == "g_mono[6]"
    assert arduino_expr_for_signal("audio_left_3") == "g_left[3]"
    assert arduino_expr_for_signal("audio_right_5") == "g_right[5]"
    assert arduino_expr_for_signal("audio_mono_7") is None
    assert arduino_expr_for_signal("audio_left_-1") is None
    assert arduino_expr_for_signal("nope") is None
    print("OK: signal_expr_map selftest passed")


if __name__ == "__main__":
    main()
