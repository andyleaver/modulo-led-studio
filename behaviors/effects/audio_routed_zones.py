from __future__ import annotations
SHIPPED = True

from typing import List, Tuple
import math
from behaviors.registry import BehaviorDef, register
from audio.routing import compute_zone_levels

RGB = Tuple[int,int,int]
USES = ["brightness","speed","softness","density","width"]

def _clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

def _hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    h=(h%1.0)*6.0
    i=int(h)%6
    f=h-float(i)
    p=v*(1.0-s)
    q=v*(1.0-f*s)
    t=v*(1.0-(1.0-f)*s)
    if i==0: r,g,b=v,t,p
    elif i==1: r,g,b=q,v,p
    elif i==2: r,g,b=p,v,t
    elif i==3: r,g,b=p,q,v
    elif i==4: r,g,b=t,p,v
    else: r,g,b=v,p,q
    return (int(r*255)&255,int(g*255)&255,int(b*255)&255)

def _zones(project: dict, n: int):
    zs = (project or {}).get("zones") or []
    out=[]
    for it in zs:
        try:
            a=int(it.get("start",0)); b=int(it.get("end",0))
            if a>b: a,b=b,a
            a=max(0,min(n-1,a)); b=max(0,min(n-1,b))
            name=str(it.get("name","Zone"))
            out.append((name,a,b))
        except Exception:
            pass
    if out:
        return out
    t1=max(0,(n//3)-1); t2=max(0,(2*n//3)-1)
    return [("Bass",0,t1),("Mid",t1+1,t2),("High",t2+1,n-1)]

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None) -> List[RGB]:
    n=max(1,int(num_leds))
    br=_clamp01(float(params.get("brightness",1.0)))
    speed=max(0.1,float(params.get("speed",1.0)))
    softness=_clamp01(float(params.get("softness",0.45)))
    density=_clamp01(float(params.get("density",0.55)))
    width=_clamp01(float(params.get("width",0.35)))
    project = params.get("_project") or {}
    ev = params.get("_audio_events") or {}
    tp = params.get("_audio_tempo") or {}

    levels = compute_zone_levels(project, ev, tp)
    zs=_zones(project,n)

    feather = max(1, int(1 + width*0.12*n))
    base=(0.02 + 0.10*math.sin(t*(0.25+0.9*speed)))%1.0

    out=[(0,0,0) for _ in range(n)]
    for idx,(name,a,b) in enumerate(zs):
        lv=_clamp01(float(levels.get(name, 0.0) or 0.0))
        # if no routes, default mapping for first 3 zones
        if not levels and idx < 3:
            if idx==0: lv=_clamp01(float(ev.get("l0_level",0.0) or 0.0))
            elif idx==1: lv=_clamp01(float(ev.get("l3_level",0.0) or 0.0))
            else: lv=_clamp01(float(ev.get("l6_level",0.0) or 0.0))

        lv = lv**(0.65+2.2*softness)
        hue=(base + (idx*0.22))%1.0
        for i in range(a,b+1):
            w=1.0
            if i-a < feather: w *= (i-a+1)/feather
            if b-i < feather: w *= (b-i+1)/feather
            v = _clamp01(br * lv * (0.15 + 0.85*w) * (0.65 + 0.35*density))
            out[i]=_hsv_to_rgb(hue,1.0,v)
    return out

def _arduino_emit(*, layout: dict, params: dict) -> str:
    n=int(layout["num_leds"]); pin=int(layout["led_pin"])
    project = params.get("_project") or {}
    zones = (project.get("zones") or [])
    routes = (project.get("audio_routes") or [])

    # target -> latest mapping
    mapping={}
    for r in routes:
        try:
            tgt=str(r.get("target",""))
            src=str(r.get("source","energy_mono"))
            if tgt and src:
                mapping[tgt]=src
        except Exception:
            pass

    baked=[]
    for it in zones[:10]:
        try:
            name=str(it.get("name","Zone"))
            a=int(it.get("start",0)); b=int(it.get("end",0))
            if a>b: a,b=b,a
            a=max(0,min(n-1,a)); b=max(0,min(n-1,b))
            baked.append((name,a,b,mapping.get(name,"energy_mono")))
        except Exception:
            pass
    if not baked:
        t1=max(0,(n//3)-1); t2=max(0,(2*n//3)-1)
        baked=[("Bass",0,t1,"bass"),("Mid",t1+1,t2,"mid"),("High",t2+1,n-1,"high")]

    br=float(params.get("brightness",1.0))
    speed=max(0.1,float(params.get("speed",1.0)))
    softness=float(params.get("softness",0.45))
    density=float(params.get("density",0.55))
    width=float(params.get("width",0.35))
    br=max(0.0,min(1.0,br))
    softness=max(0.0,min(1.0,softness))
    density=max(0.0,min(1.0,density))
    width=max(0.0,min(1.0,width))

    feather = max(1, int(1 + width*0.12*max(1,n)))

    def src_expr(src:str)->str:
        if src=="bass": return "0.25f*(L[0]+L[1]+R[0]+R[1])"
        if src=="mid": return "(L[2]+L[3]+L[4]+R[2]+R[3]+R[4])/6.0f"
        if src=="high": return "(L[5]+L[6]+R[5]+R[6])/4.0f"
        if src.startswith("l") and len(src)==2 and src[1].isdigit(): return f"L[{int(src[1])}]"
        if src.startswith("r") and len(src)==2 and src[1].isdigit(): return f"R[{int(src[1])}]"
        if src=="energy_l": return "lraw"
        if src=="energy_r": return "rraw"
        return "em"

    zone_consts="\n".join([f'const int Z{i}_A={a}; const int Z{i}_B={b};' for i,(_,a,b,_) in enumerate(baked)])
    zone_comments="\n".join([f'// Z{i}: {name} -> {src}' for i,(name,_,_,src) in enumerate(baked)])
    zone_levels="\n".join([f'float z{i}=clamp01({src_expr(src)}); z{i}=powf(z{i}, 0.65f+2.2f*softness);' for i,(_,_,_,src) in enumerate(baked)])
    hue_assign="\n".join([f'float h{i}=fmodf(base + {i}*0.22f, 1.0f);' for i in range(len(baked))])

    # zone paint loops
    loops=[]
    for i,(name,a,b,src) in enumerate(baked):
        loops.append(f'''  for (int j=Z{i}_A; j<=Z{i}_B && j<NUM_LEDS; j++) {{
    float w=feather_w(j,Z{i}_A,Z{i}_B);
    float v=clamp01(br*z{i}*(0.15f + 0.85f*w)*(0.65f + 0.35f*density));
    uint8_t r,g,b; hsv_to_rgb(h{i},1.0f,v,&r,&g,&b);
    leds[j]=CRGB(r,g,b);
  }}''')
    loops_code="\n\n".join(loops)

    return f"""// Generated by Modulo (Audio Routed Zones)
#include <FastLED.h>
#include <math.h>

#define NUM_LEDS {n}
#define LED_PIN {pin}
CRGB leds[NUM_LEDS];

const int RESET_PIN = 5;
const int STROBE_PIN = 4;
const int LEFT_PIN = A0;
const int RIGHT_PIN = A1;

{zone_comments}
{zone_consts}

static inline float clamp01(float x) {{
  if (x<0.0f) return 0.0f;
  if (x>1.0f) return 1.0f;
  return x;
}}
static inline float read01(int pin) {{
  int v=analogRead(pin);
  return clamp01((float)v/1023.0f);
}}
static inline void hsv_to_rgb(float h, float s, float v, uint8_t* r, uint8_t* g, uint8_t* b) {{
  float hh=fmodf(h,1.0f)*6.0f;
  int i=(int)floorf(hh)%6;
  float f=hh-(float)i;
  float p=v*(1.0f-s);
  float q=v*(1.0f-f*s);
  float t=v*(1.0f-(1.0f-f)*s);
  float rr,gg,bb;
  if (i==0) {{ rr=v; gg=t; bb=p; }}
  else if (i==1) {{ rr=q; gg=v; bb=p; }}
  else if (i==2) {{ rr=p; gg=v; bb=t; }}
  else if (i==3) {{ rr=p; gg=q; bb=v; }}
  else if (i==4) {{ rr=t; gg=p; bb=v; }}
  else {{ rr=v; gg=p; bb=q; }}
  *r=(uint8_t)(rr*255.0f); *g=(uint8_t)(gg*255.0f); *b=(uint8_t)(bb*255.0f);
}}
static inline float feather_w(int i, int a, int b) {{
  int f={feather};
  float w=1.0f;
  if (i-a < f) w *= (float)(i-a+1)/(float)f;
  if (b-i < f) w *= (float)(b-i+1)/(float)f;
  return w;
}}

void setup() {{
  FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
  FastLED.setBrightness(255);
  pinMode(RESET_PIN, OUTPUT);
  pinMode(STROBE_PIN, OUTPUT);
  digitalWrite(RESET_PIN, LOW);
  digitalWrite(STROBE_PIN, HIGH);
}}

void loop() {{
  float L[7], R[7];
  digitalWrite(RESET_PIN, HIGH); delayMicroseconds(5); digitalWrite(RESET_PIN, LOW);
  for (int i=0;i<7;i++) {{
    digitalWrite(STROBE_PIN, LOW); delayMicroseconds(30);
    L[i]=read01(LEFT_PIN);
    R[i]=read01(RIGHT_PIN);
    digitalWrite(STROBE_PIN, HIGH);
  }}
  float lsum=0.0f, rsum=0.0f;
  for (int i=0;i<7;i++) {{ lsum+=L[i]; rsum+=R[i]; }}
  float lraw=lsum/7.0f;
  float rraw=rsum/7.0f;
  float em=0.5f*(lraw+rraw);

  float softness=clamp01((float){softness}f);
  float speed=(float){speed}f;
  float density=clamp01((float){density}f);
  float br=clamp01((float){br}f);

  {zone_levels}

  float tt=millis()/1000.0f;
  float base=fmodf(0.02f + 0.10f*sinf(tt*(0.25f+0.9f*speed)), 1.0f);
  {hue_assign}

  for (int i=0;i<NUM_LEDS;i++) leds[i]=CRGB(0,0,0);

{loops_code}

  FastLED.show();
  delay(1);
}}
"""

def register_audio_routed_zones():
    return register(BehaviorDef(
        "audio_routed_zones",
        title="Audio Routed Zones (Bands → Zones)",
        uses=USES,
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    ))
