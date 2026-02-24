# Export Matrix (Audited)
- generated_utc: `2026-02-24T14:45:45Z`
- behaviors_registered: **83**
- targets_discovered: **18**

## Summary per target
| target | PASS | PREVIEW_ONLY | BLOCKED |
|---|---|---|---|
| arduino_avr_fastled_msgeq7 | 67 | 0 | 16 |
| arduino_avr_fastled_noaudio | 67 | 0 | 16 |
| arduino_avr_fastled_only | 67 | 0 | 16 |
| arduino_avr_matrix_fastled_msgeq7 | 67 | 0 | 16 |
| arduino_mega_fastled_msgeq7 | 67 | 0 | 16 |
| arduino_mega_pio_fastled_msgeq7 | 67 | 0 | 16 |
| arduino_uno_fastled_msgeq7 | 67 | 0 | 16 |
| arduino_uno_pio_fastled_msgeq7 | 67 | 0 | 16 |
| esp32_fastled_msgeq7 | 67 | 0 | 16 |
| esp32_hub75_i2sdma_msgeq7 | 67 | 0 | 16 |
| esp32_neopixelbus_msgeq7 | 67 | 0 | 16 |
| esp8266_fastled_noneaudio | 67 | 0 | 16 |
| rp2040_fastled_noneaudio | 67 | 0 | 16 |
| rp2040_pico_fastled_msgeq7 | 67 | 0 | 16 |
| stm32_fastled_noneaudio | 67 | 0 | 16 |
| teensy40_fastled_msgeq7 | 67 | 0 | 16 |
| teensy41_fastled | 67 | 0 | 16 |
| teensy41_fastled_noneaudio | 67 | 0 | 16 |

## Non-exportable behaviors (must be cleared)
| effect | status | reason |
|---|---|---|
| asteroids_game | blocked | Asteroids (Game) is preview-ready but Arduino export is not wired yet. |
| blocks_ball_game_ino | blocked | Blocks+Ball (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter. |
| breakout_game | blocked | Breakout (Game) is preview-ready but Arduino export is not wired yet. |
| brians_brain | blocked | Export not yet supported for Brian's Brain (preview only for now). |
| elementary_ca | blocked | Export not yet supported for Elementary CA (preview only for now). |
| game_of_life | blocked | Export not yet supported for Game of Life (preview only for now). |
| langtons_ant | blocked | Export not yet supported for Langton's Ant (preview only for now). |
| mariobros_clockface | preview-only | Mario clockface uses tilemap/sprite tables not yet exported. |
| msgeq7_reactive_ino | blocked | MSGEQ7 Reactive (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter. |
| msgeq7_visualizer_575 | blocked | MSGEQ7 Visualizer (575) is preview-ready but Arduino export is not wired yet. |
| red_hat_runner | preview-only | Red Hat Runner is a preview-only stateful demo (sprite blitter + tables not yet exported). |
| shooter_game_ino | blocked | Shooter (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter. |
| snake_game | blocked | Snake (Game) is preview-ready but Arduino export is not wired yet. |
| snake_game_ino | blocked | Snake (INO Port) is preview-ready but Arduino export is not yet wired into the multi-layer exporter. |
| space_invaders_game | blocked | Space Invaders (Game) is preview-ready but Arduino export is not wired yet. |
| tilemap_sprite | preview-only | Tilemap+sprite engine not yet exported. |