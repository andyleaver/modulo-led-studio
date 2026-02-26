// Firmware behavior runtime template
//
// 1) Add a BEHAVIOR_ID in the exporter/runtime switch
// 2) Keep it deterministic (fixed-step tick, no floating randomness without seed)
// 3) Use purpose params (PF0.., PI0..) for rule-driven control

typedef struct {
  // state variables
  uint32_t t;
} behavior_state_t;

static inline void behavior_init(behavior_state_t* s) {
  s->t = 0;
}

static inline void behavior_tick(behavior_state_t* s) {
  s->t++;
}

static inline void behavior_render(behavior_state_t* s) {
  // write into framebuffer here
}
