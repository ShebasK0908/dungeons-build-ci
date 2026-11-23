#!/usr/bin/env python3
"""Piel de controles de Minecraft Dungeons para el overlay de DmIOS.

Corrección del usuario (2026-11-23): «Yo pensé que ibas a utilizar los
controles que ya tiene el juego». Este parche hace exactamente eso: los
botones virtuales dejan de ser los discos translúcidos de fábrica de
DmGamepad y pasan a ser LOS DISCOS DE COLORES DEL PROPIO JUEGO, extraídos
del port móvil (Dungeons/Content/Mobile de la .apk del usuario, convertidos
a PNG con dungeons-apk/analisis/uexp_texture_to_png.py), cada uno con su
estado pulsado, y el stick izquierdo con el marco y el pomo del juego.

Qué toca (solo dm/ios/Sources/DmGamepad.m + una cabecera generada):
- Genera dm/ios/Sources/dm_skin_dungeons.h con los PNG incrustados en
  base64 y la tabla tecla→arte. Las claves son los B_* del propio archivo,
  así que un reorden del enum no rompe la tabla en silencio: rompe la
  compilación, que es lo que queremos.
- Cada tecla con arte gana una CALayer hermana con la imagen (filtro de
  aumento «nearest»: el pixel art se ve como en el juego); su etiqueta de
  fábrica se oculta y su disco deja de rellenarse. Al pulsar, refresh
  cambia la imagen por la de «pulsado», igual que antes cambiaba el relleno.
- El anillo y el pomo del stick izquierdo se dibujan con el arte del juego;
  la cruceta NO tiene equivalente en el port y conserva el dibujo de
  fábrica, como el botón de menú del lanzador (que no es un botón del juego).
- NO toca geometría (posiciones/tamaños = layout full de fábrica), ni el
  reparto de toques, ni el requisito táctil: el modo de consola lo sigue
  mandando el perfil (variante traducir_y_ajustes_dungeons.py, DM_OPMODE
  intacto). La piel y el táctil son ortogonales por construcción.

Mapeo tecla→acción→arte (pasada 3 del análisis de riesgos; el esquema de
mando lo fija el propio juego, DefaultInput.ini del port):
  X ataque principal → espada roja · B esquiva → flechas verdes ·
  Y arco → arco azul · A interactuar → disco genérico (el port reutiliza
  ese disco para AttackInteract) · ZR poción → frasco morado ·
  ZL/L/R artefactos 1/2/3 → sacos marrones · − mapa · + ajustes ·
  L3 inventario → cofre · R3 sin equivalente → disco genérico.

Los PNG NO viajan en el repo público de CI (son arte del juego): el
workflow los baja de la release privada `game` (controles-dungeons-png.zip)
y pasa --png-dir. En local, el defecto es la carpeta del workspace.

Falla con error si falta un PNG o un ancla (lección Sparking: descubrir la
deriva de upstream en la prueba en seco, no una hora dentro de la build).
Uso: python3 piel_dungeons.py <ruta-al-clon-de-nxnative> [--png-dir <dir>]
"""
import base64
import sys
from pathlib import Path

# nombre en la tabla -> (PNG normal, PNG pulsado)
ART = {
    "attack": ("Attack-Normal.png", "Attack-Pressed.png"),
    "dash": ("Dash-Normal.png", "Dash-Pressed.png"),
    "bow": ("Attack_Bow.png", "Attack_Bow_Pressed.png"),
    "potion": ("Potion-usual.png", "Potion-Pressed.png"),
    "item1": ("Artifact_Normal.png", "Artifact_Pressed.png"),
    "item2": ("Artifact_2.png", "Artifact_2_Pressed.png"),
    "item3": ("Artifact_3.png", "Artifact_3_Pressed.png"),
    "map": ("Map-Normal.png", "Map-Pressed.png"),
    "inv": ("Inv-Normal.png", "Inv-Pressed.png"),
    "settings": ("Settings-Normal.png", "Settings-Pressed.png"),
    "grey": ("Grey-Normal.png", "Grey-Pressed.png"),
    "stick_frame": ("joystick_frame_512.png", None),
    "stick_knob": ("joystick_knob_512.png", None),
}

HEADER_TEMPLATE = """// Generado por tools/piel_dungeons.py a partir de las texturas del propio
// juego (port movil de Minecraft Dungeons del usuario). No editar a mano.
// Piel de los botones del overlay de DmGamepad: los discos de colores del
// juego en vez de los discos de fabrica, cada uno con su estado pulsado.
#import <UIKit/UIKit.h>

static UIImage *dm_skin_img(NSString *name) {
    static NSDictionary<NSString *, NSString *> *b64;
    static NSMutableDictionary<NSString *, UIImage *> *cache;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        b64 = @{
__ENTRIES__
        };
        cache = [NSMutableDictionary dictionary];
    });
    if (!name) return nil;
    UIImage *img = cache[name];
    if (!img) {
        NSString *s = b64[name];
        if (!s) return nil;
        NSData *d = [[NSData alloc] initWithBase64EncodedString:s options:0];
        img = d ? [UIImage imageWithData:d] : nil;
        if (img) cache[name] = img;
    }
    return img;
}

// Que arte lleva cada tecla (las claves son el enum de DmGamepad.m, ya
// definido cuando se importa esta cabecera); nil = dibujo de fabrica.
static NSString *dm_skin_name(int b, BOOL pressed) {
    switch (b) {
        case B_X: return pressed ? @"attack_on" : @"attack";        // ataque principal: espada roja
        case B_B: return pressed ? @"dash_on" : @"dash";            // esquiva / rodar: flechas verdes
        case B_Y: return pressed ? @"bow_on" : @"bow";              // arco: disco azul
        case B_A: return pressed ? @"grey_on" : @"grey";            // interactuar: el port reutiliza el disco generico
        case B_ZR: return pressed ? @"potion_on" : @"potion";       // pocion de vida: frasco morado
        case B_ZL: return pressed ? @"item1_on" : @"item1";         // artefacto 1
        case B_L: return pressed ? @"item2_on" : @"item2";          // artefacto 2
        case B_R: return pressed ? @"item3_on" : @"item3";          // artefacto 3
        case B_MINUS: return pressed ? @"map_on" : @"map";          // mapa
        case B_PLUS: return pressed ? @"settings_on" : @"settings"; // menu / ajustes del juego
        case B_LS: return pressed ? @"inv_on" : @"inv";             // inventario: cofre
        case B_RS: return pressed ? @"grey_on" : @"grey";           // sin equivalente en el port
        default: return nil;                                        // cruceta: dibujo de fabrica
    }
}
"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = Path(args[0])
    png_dir = Path.home() / "workspace/tres-juegos/controles-dungeons-png"
    if "--png-dir" in sys.argv:
        png_dir = Path(sys.argv[sys.argv.index("--png-dir") + 1])

    target = root / "dm/ios/Sources/DmGamepad.m"
    header = root / "dm/ios/Sources/dm_skin_dungeons.h"
    text = target.read_text(encoding="utf-8")
    if "dm_skin_dungeons.h" in text:
        print("ERROR: la piel ya está aplicada en DmGamepad.m (no aplicar dos veces)")
        return 1

    # 1. PNG: todos o ninguno
    entries, faltan = [], []
    for name, (normal, pressed) in sorted(ART.items()):
        for suffix, fname in (("", normal), ("_on", pressed)):
            if fname is None:
                continue
            p = png_dir / fname
            if not p.exists():
                faltan.append(str(p))
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            entries.append(f'            @"{name}{suffix}": @"{b64}",')
    if faltan:
        print("FALTAN PNG (¿se generó controles-dungeons-png?):")
        for f in faltan:
            print(" -", f)
        return 1
    header.write_text(HEADER_TEMPLATE.replace("__ENTRIES__", "\n".join(entries)), encoding="utf-8")

    # 2. Parche de DmGamepad.m por anclas exactas
    missing = []

    def patch(old, new):
        nonlocal text
        if old not in text:
            missing.append(old[:70])
        else:
            text = text.replace(old, new, 1)

    patch("static pthread_mutex_t g_mu = PTHREAD_MUTEX_INITIALIZER;",
          '#import "dm_skin_dungeons.h"   // piel de Dungeons: los botones del propio juego (piel_dungeons.py)\n'
          "static pthread_mutex_t g_mu = PTHREAD_MUTEX_INITIALIZER;")

    patch("    CAShapeLayer *_key[B_N]; CATextLayer *_label[B_N];   // one layer per key",
          "    CAShapeLayer *_key[B_N]; CATextLayer *_label[B_N];   // one layer per key\n"
          "    CALayer *_art[B_N];                                // Dungeons skin: the game's own button pictures over the skinned keys")

    patch("    CAShapeLayer *_ring, *_knob;                   // the left stick (the right one is not drawn)",
          "    CAShapeLayer *_ring, *_knob;                   // the left stick (the right one is not drawn)\n"
          "    CALayer *_ringArt, *_knobArt;                    // Dungeons skin: the game's joystick frame / knob pictures")

    patch("""        for (int b = 0; b < B_N; b++) {
            _key[b] = shape(_controls);
            if (names[b]) _label[b] = label(_key[b], names[b]);   // the D-pad arms carry no label
        }""",
          """        for (int b = 0; b < B_N; b++) {
            _key[b] = shape(_controls);
            if (names[b]) _label[b] = label(_key[b], names[b]);   // the D-pad arms carry no label
        }
        for (int b = 0; b < B_N; b++) {   // Dungeons skin: a picture layer over each skinned key, its factory label hidden under it
            if (!dm_skin_name(b, NO)) continue;
            _art[b] = [CALayer layer]; _art[b].magnificationFilter = kCAFilterNearest; [_controls addSublayer:_art[b]];
            if (_label[b]) _label[b].hidden = YES;
            _key[b].fillColor = nil; _key[b].strokeColor = nil;
        }
        _ringArt = [CALayer layer]; _ringArt.contents = (id)dm_skin_img(@"stick_frame").CGImage; [_controls addSublayer:_ringArt];
        _ring.fillColor = nil; _ring.strokeColor = nil;
        ((CAShapeLayer *)_knob.sublayers.firstObject).hidden = YES;   // the knob's drawn inner ring goes away under its picture
        _knobArt = [CALayer layer]; _knobArt.contents = (id)dm_skin_img(@"stick_knob").CGImage; [_knob addSublayer:_knobArt];
        _knob.fillColor = nil; _knob.strokeColor = nil;""")

    patch("""    for (int b = 0; b < B_N; b++) _key[b].hidden = _tap || (fullOnly(b) && !_full);
    _ring.hidden = _knob.hidden = _tap;""",
          """    for (int b = 0; b < B_N; b++) { _key[b].hidden = _tap || (fullOnly(b) && !_full); if (_art[b]) _art[b].hidden = _key[b].hidden; }
    _ring.hidden = _knob.hidden = _tap;
    if (_ringArt) _ringArt.hidden = _tap;""")

    patch("    for (int b = B_A; b <= B_Y; b++) { CGPoint c = [self facePos:b]; setPath(_key[b], circlePath(c, self.faceR)); placeLabel(_label[b], c, 20 * u); }",
          "    for (int b = B_A; b <= B_Y; b++) { CGPoint c = [self facePos:b]; setPath(_key[b], circlePath(c, self.faceR)); placeLabel(_label[b], c, 20 * u); }\n"
          "    for (int b = B_A; b <= B_Y; b++) if (_art[b]) { CGPoint c = [self facePos:b]; CGFloat s = 2 * self.faceR; _art[b].frame = CGRectMake(c.x - s / 2, c.y - s / 2, s, s); }")

    patch("    static const struct { int b; CGFloat angle; } arms[] = {{B_UP, 0}, {B_RIGHT, M_PI_2}, {B_DOWN, M_PI}, {B_LEFT, -M_PI_2}};   // the same arm in 90° steps",
          """    for (int i = 0; i < (int)(sizeof k_btns / sizeof *k_btns); i++) { int b = k_btns[i]; if (!_art[b]) continue;   // Dungeons skin: the picture sits on the key's own centre, as large as the key
        CGPoint c; CGFloat s;
        if (isDrop(b)) { c = [self dropCenter:b]; s = 2 * [self dropR:b]; }
        else if (isClick(b)) { c = [self clickCenter:b]; s = 2 * K_CLICK_R * u; }
        else { CGRect rc = [self pillRect:b]; c = CGPointMake(CGRectGetMidX(rc), CGRectGetMidY(rc)); s = rc.size.height; }
        _art[b].frame = CGRectMake(c.x - s / 2, c.y - s / 2, s, s); }
    static const struct { int b; CGFloat angle; } arms[] = {{B_UP, 0}, {B_RIGHT, M_PI_2}, {B_DOWN, M_PI}, {B_LEFT, -M_PI_2}};   // the same arm in 90° steps""")

    patch("    setPath(_ring, circlePath(self.stickHome, [self stickR:0]));",
          "    setPath(_ring, circlePath(self.stickHome, [self stickR:0]));\n"
          "    if (_ringArt) { CGFloat rs = 2 * [self stickR:0]; CGPoint hc = self.stickHome; _ringArt.frame = CGRectMake(hc.x - rs / 2, hc.y - rs / 2, rs, rs); }")

    patch("    CGFloat k = K_KNOB_R * u; _knob.bounds = CGRectMake(0, 0, 2 * k, 2 * k);",
          "    CGFloat k = K_KNOB_R * u; _knob.bounds = CGRectMake(0, 0, 2 * k, 2 * k);\n"
          "    if (_knobArt) _knobArt.frame = CGRectMake(0, 0, 2 * k, 2 * k);")

    patch("""    for (int b = 0; b < B_N; b++) { BOOL on = (all >> b) & 1;
        _key[b].fillColor = (on ? k_on : k_idle).CGColor; _label[b].foregroundColor = (on ? k_textOn : k_text).CGColor; }""",
          """    for (int b = 0; b < B_N; b++) { BOOL on = (all >> b) & 1;
        if (_art[b]) { _art[b].contents = (id)dm_skin_img(dm_skin_name(b, on)).CGImage; continue; }   // Dungeons skin: a press swaps the picture, not the fill
        _key[b].fillColor = (on ? k_on : k_idle).CGColor; _label[b].foregroundColor = (on ? k_textOn : k_text).CGColor; }""")

    patch("    _knob.position = CGPointMake(h.x + o.x, h.y + o.y); _knob.fillColor = (_stick[0] ? k_on : k_idle).CGColor;",
          "    _knob.position = CGPointMake(h.x + o.x, h.y + o.y); if (!_knobArt) _knob.fillColor = (_stick[0] ? k_on : k_idle).CGColor;")

    if missing:
        print("FALTAN ANCLAS (¿cambió upstream?):")
        for m in missing:
            print(" -", m)
        return 1
    target.write_text(text, encoding="utf-8")

    # 3. Autocomprobación
    n = text.count("dm_skin")
    marcas = ['#import "dm_skin_dungeons.h"', "CALayer *_art[B_N]",
              "dm_skin_name(b, on)", "_ringArt", "_knobArt"]
    if n < 6 or not header.exists() or any(m not in text for m in marcas):
        print(f"ERROR ESTRUCTURAL: dm_skin aparece {n} veces en DmGamepad.m (esperadas >= 6) "
              f"o falta alguna marca de {marcas}")
        return 1
    print(f"Piel aplicada: {len(entries)} imágenes incrustadas en dm_skin_dungeons.h, DmGamepad.m parcheado ({n} referencias dm_skin).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
