from __future__ import annotations

from export.arduino_exporter_block_common import TOKEN_RE, EXPORT_MARKER

def _runtime_state_h() -> str:
    """Inline Arduino state runtime (single-file export)."""
    return """// ---- Modulo Stateful Runtime (Phase 5S: Generic State Slots) ----
typedef struct {
  uint32_t reserved;
} EffectState;

// Generic per-layer state slots (for deterministic stateful effects)
// - 4 float slots + 4 int slots per layer
// - ST_INIT marks whether a layer has been initialized for its behavior
static float   ST_F[LAYERS][4];
static int16_t ST_I[LAYERS][4];
static uint8_t ST_INIT[LAYERS];

static inline void state_reset_layer(int li){
  for(int k=0;k<4;k++){ ST_F[li][k]=0.0f; ST_I[li][k]=0; }
  ST_INIT[li]=1;
}

"""

__all__ = ["TOKEN_RE", "EXPORT_MARKER", "_runtime_state_h"]
