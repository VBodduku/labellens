"""
Builds the shared fixtures that let all three parts work in isolation:

  sample_label.svg        a realistic packaged-food label (back panel) with known text positions
  scan_result.json        a complete ScanResult for that label + 3 family profiles (covers all 4 verdict states)
  profiles.json           the 3 profiles used above
  catalog.json            the restriction catalog (authoritative list of restriction keys)
  ask_response.json       sample /api/ask answer
  profile_parse.json      sample /api/profile/parse answer
  explain.json            sample /api/explain answer
  health.json             sample /api/health answer

Run from the repo root:   python -m shared.fixtures.build_fixtures
Every JSON file is validated against shared/contract.py before it is written.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from shared.contract import (
    AllergenStatement, AskResponse, Box, ConsistencyCheck, Evidence, ExplainResponse,
    ExtractionMeta, HealthResponse, ImageInfo, ImageQuality, Ingredient, IngredientAnnotation,
    LabelExtraction, Match, NutrientRow, NutrientValue, NutritionAnalysis, NutritionTable, OcrToken,
    Profile, ProfileParseResponse, ProfileReport, Restriction, RestrictionCatalogItem,
    RestrictionResult, RetryRecord, ScanResult, SectionStatus, Threshold, ToolCallTrace,
    UnknownItem, VegMark, VerdictRef, Claim,
)

OUT = Path(__file__).parent
W, H = 1000, 1400
IMG = "img_0"
CHAR_W = 0.6  # monospace advance width as a fraction of font size (enforced with textLength)
MESSAGES = json.loads((OUT.parent / "messages.en.json").read_text(encoding="utf-8"))

tokens: list[OcrToken] = []
svg_text: list[str] = []


def nb(x: float, y: float, w: float, h: float) -> Box:
    return Box(x=round(x / W, 4), y=round(y / H, 4), w=round(w / W, 4), h=round(h / H, 4))


def add_token(text: str, x: float, baseline: float, fs: float, weight: str = "normal",
              conf: float = 0.97, fill: str = "#1d1d1b") -> OcrToken:
    w = len(text) * fs * CHAR_W
    t = OcrToken(token_id=f"{IMG}:t{len(tokens)}", image_id=IMG, text=text.replace(" ", " "),
                 box=nb(x, baseline - fs * 0.82, w, fs * 1.05), confidence=conf)
    tokens.append(t)
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg_text.append(
        f'<text x="{x:.1f}" y="{baseline:.1f}" font-size="{fs}" font-weight="{weight}" fill="{fill}" '
        f'textLength="{w:.1f}" lengthAdjust="spacingAndGlyphs">{esc}</text>'
    )
    return t


def paragraph(text: str, x0: float, y0: float, max_w: float, fs: float, lh: float, weight="normal"):
    """Lay out words left-to-right with wrapping. Returns [(token, char_start, char_end)] and next y."""
    out = []
    x, y = x0, y0
    for m in re.finditer(r"\S+", text):
        word = m.group()
        w = len(word) * fs * CHAR_W
        if x + w > x0 + max_w and x > x0:
            x, y = x0, y + lh
        t = add_token(word, x, y, fs, weight)
        out.append((t, m.start(), m.end()))
        x += w + fs * CHAR_W
    return out, y + lh


def union(ts: list[OcrToken]) -> Box:
    x0 = min(t.box.x for t in ts); y0 = min(t.box.y for t in ts)
    x1 = max(t.box.x + t.box.w for t in ts); y1 = max(t.box.y + t.box.h for t in ts)
    return Box(x=round(x0, 4), y=round(y0, 4), w=round(x1 - x0, 4), h=round(y1 - y0, 4))


def evidence_for_span(laid, start: int, end: int, text: str) -> list[Evidence]:
    """One Evidence per printed line the span touches (ingredients wrap across lines)."""
    hit = [t for (t, s, e) in laid if s < end and e > start]
    lines: dict[float, list[OcrToken]] = {}
    for t in hit:
        lines.setdefault(t.box.y, []).append(t)
    return [Evidence(image_id=IMG, text=text if len(lines) == 1 else " ".join(t.text for t in ts),
                     box=union(ts), token_ids=[t.token_id for t in ts], match_score=0.96,
                     status="verified") for ts in lines.values()]


def split_top_level(s: str) -> list[tuple[str, int, int]]:
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(s):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append((start, i)); start = i + 1
    parts.append((start, len(s)))
    out = []
    for a, b in parts:
        seg = s[a:b]
        lead = len(seg) - len(seg.lstrip())
        seg = seg.strip().rstrip(".")
        out.append((seg, a + lead, a + lead + len(seg)))
    return out


NAMES = {  # English display names used to render `explanation`; params themselves stay as ids
    "peanut": "peanut", "tree_nut": "tree nut", "onion": "onion", "garlic": "garlic",
    "total_sugars_g": "Total sugars", "sodium_mg": "Sodium", "per_100g": "100 g",
}


def msg(key: str, **params) -> str:
    text = MESSAGES[key]
    for k, v in params.items():
        if k == "category":
            v = " or ".join(NAMES.get(c, c) for c in str(v).split("|"))
        elif k in ("nutrient", "basis"):
            v = NAMES.get(str(v), v)
        text = text.replace("{" + k + "}", str(v))
    return text


# ------------------------------------------------------------------------------------------
# 1. Draw the label
# ------------------------------------------------------------------------------------------
add_token("NUVO", 60, 95, 44, "bold", fill="#7a2e1c")
add_token("CHOCO", 60, 150, 34, "bold")
add_token("NUT", 190, 150, 34, "bold")
add_token("CRUNCH", 273, 150, 34, "bold")
add_token("BAR", 416, 150, 34, "bold")
c1 = add_token("HIGH", 60, 200, 24, "bold", fill="#2f6b3a")
c2 = add_token("PROTEIN", 140, 200, 24, "bold", fill="#2f6b3a")
nw = [add_token("Net", 640, 200, 24), add_token("Wt.", 703, 200, 24), add_token("120", 766, 200, 24),
      add_token("g", 829, 200, 24)]

ING_TEXT = ("Sugar, Peanuts (22%), Milk Solids (12%), Refined Wheat Flour (Maida), Cocoa Butter, "
            "Edible Vegetable Oil (Palm), Invert Sugar Syrup, Emulsifier (INS 322 [Soy]), Iodised Salt, "
            "Raising Agent (INS 500(ii)), Natural Flavours.")
add_token("INGREDIENTS:", 60, 290, 26, "bold")
laid_ing, y = paragraph(ING_TEXT, 60, 330, 880, 26, 38)

ALG1 = "CONTAINS: PEANUT, MILK, WHEAT, SOY."
ALG2 = "MAY CONTAIN TRACES OF TREE NUTS."
laid_a1, y = paragraph(ALG1, 60, y + 22, 880, 26, 38, "bold")
laid_a2, y = paragraph(ALG2, 60, y, 880, 26, 38, "bold")

# Nutrition table
ty = y + 40
add_token("NUTRITION", 60, ty, 28, "bold"); add_token("INFORMATION", 230, ty, 28, "bold")
add_token("(Approx.)", 433, ty, 28)
ss = [add_token(w, x, ty + 42, 22) for w, x in
      [("Serving", 60), ("size:", 156), ("40", 230), ("g", 264), ("|", 300), ("Servings", 330),
       ("per", 440), ("pack:", 487), ("3", 562)]]
hy = ty + 92
add_token("Nutrient", 60, hy, 24, "bold"); add_token("Per", 600, hy, 24, "bold")
add_token("100", 650, hy, 24, "bold"); add_token("g", 709, hy, 24, "bold")
add_token("Per", 790, hy, 24, "bold"); add_token("serving", 840, hy, 24, "bold")

ROWS = [  # key, printed label, per100 text, per serving text, unit, per100 value, per serving value
    ("energy_kcal", "Energy", "520", "208", "kcal", 520.0, 208.0),
    ("protein_g", "Protein", "9.5", "3.8", "g", 9.5, 3.8),
    ("carbohydrate_g", "Carbohydrate", "58.0", "23.2", "g", 58.0, 23.2),
    ("total_sugars_g", "Total Sugars", "38.0", "15.2", "g", 38.0, 15.2),
    ("added_sugars_g", "Added Sugars", "30.0", "12.0", "g", 30.0, 12.0),
    ("total_fat_g", "Total Fat", "28.0", "11.2", "g", 28.0, 11.2),
    ("saturated_fat_g", "Saturated Fat", "14.0", "5.6", "g", 14.0, 5.6),
    ("trans_fat_g", "Trans Fat", "0.1", "0.0", "g", 0.1, 0.0),
    ("sodium_mg", "Sodium", "?", "?", "mg", None, None),
]
rows: list[NutrientRow] = []
row_ev: dict[str, Evidence] = {}
sodium_region: Evidence | None = None
ry = hy + 46
svg_lines = []
for key, label, a, b, unit, va, vb in ROWS:
    svg_lines.append(f'<line x1="60" y1="{ry - 32}" x2="940" y2="{ry - 32}" stroke="#1d1d1b" stroke-width="1.5"/>')
    lt = []
    x = 60
    for w in label.split():
        lt.append(add_token(w, x, ry, 24)); x += (len(w) + 1) * 24 * CHAR_W
    if va is None:
        # smudged value: drawn under a blot, low OCR confidence, unreadable
        ta = add_token("1?5", 650, ry, 24, conf=0.21)
        tb = add_token("??", 840, ry, 24, conf=0.18)
        sodium_region = Evidence(image_id=IMG, text="", box=union([ta, tb]), token_ids=[ta.token_id, tb.token_id],
                                 match_score=0.0, status="verified")
        vals = [
            NutrientValue(basis="per_100g", amount=None, unit=unit, raw_text="", readability="unreadable",
                          evidence=Evidence(image_id=IMG, text="", box=ta.box, token_ids=[ta.token_id],
                                            match_score=0.0, status="verified")),
            NutrientValue(basis="per_serving", amount=None, unit=unit, raw_text="", readability="unreadable",
                          evidence=Evidence(image_id=IMG, text="", box=tb.box, token_ids=[tb.token_id],
                                            match_score=0.0, status="verified")),
        ]
    else:
        ta = add_token(f"{a}\u00a0{unit}", 650, ry, 24)
        tb = add_token(f"{b}\u00a0{unit}", 840, ry, 24)
        vals = [
            NutrientValue(basis="per_100g", amount=va, unit=unit, raw_text=ta.text.replace("\u00a0", " "),
                          evidence=Evidence(image_id=IMG, text=ta.text.replace("\u00a0", " "), box=ta.box,
                                            token_ids=[ta.token_id], match_score=0.98, status="verified")),
            NutrientValue(basis="per_serving", amount=vb, unit=unit, raw_text=tb.text.replace("\u00a0", " "),
                          evidence=Evidence(image_id=IMG, text=tb.text.replace("\u00a0", " "), box=tb.box,
                                            token_ids=[tb.token_id], match_score=0.98, status="verified")),
        ]
    row_ev[key] = Evidence(image_id=IMG, text=f"{label} {a} {unit}", box=union(lt + [ta, tb]),
                           token_ids=[t.token_id for t in lt + [ta, tb]], match_score=0.97, status="verified")
    rows.append(NutrientRow(key=key, raw_label=label, values=vals))
    ry += 46
svg_lines.append(f'<line x1="60" y1="{ry - 32}" x2="940" y2="{ry - 32}" stroke="#1d1d1b" stroke-width="1.5"/>')

foot_y = ry + 20
add_token("Mfd.", 60, foot_y, 20); add_token("by:", 116, foot_y, 20); add_token("Nuvo", 160, foot_y, 20)
add_token("Foods,", 216, foot_y, 20); add_token("Hyderabad.", 290, foot_y, 20)

# Veg mark (FSSAI green square with a green dot) — not text, so not an OCR token
veg_box = nb(860, 40, 80, 80)
sx, sy = 860, 40
blot_cx = (sodium_region.box.x + sodium_region.box.w / 2) * W
blot_cy = (sodium_region.box.y + sodium_region.box.h / 2) * H
blot_rx = sodium_region.box.w * W / 2 + 40

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
  font-family="'Courier New', 'DejaVu Sans Mono', monospace">
  <defs>
    <filter id="blot" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
    <linearGradient id="paper" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fbf6ea"/><stop offset="1" stop-color="#f1e8d4"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#paper)"/>
  <rect x="30" y="30" width="{W-60}" height="{H-60}" fill="none" stroke="#1d1d1b" stroke-width="3" rx="6"/>
  <rect x="{sx}" y="{sy}" width="80" height="80" fill="#fff" stroke="#1f8a3b" stroke-width="6"/>
  <circle cx="{sx+40}" cy="{sy+40}" r="22" fill="#1f8a3b"/>
  {"".join(svg_lines)}
  {"".join(svg_text)}
  <ellipse cx="{blot_cx:.1f}" cy="{blot_cy:.1f}" rx="{blot_rx:.1f}" ry="24" fill="#5a4a32" opacity="0.72" filter="url(#blot)"/>
</svg>'''
(OUT / "sample_label.svg").write_text(svg, encoding="utf-8")

# ------------------------------------------------------------------------------------------
# 2. Extraction
# ------------------------------------------------------------------------------------------
ingredients: list[Ingredient] = []
for n, (seg, s, e) in enumerate(split_top_level(ING_TEXT.rstrip("."))):
    pct = re.search(r"\((\d+(?:\.\d+)?)%\)", seg)
    ingredients.append(Ingredient(
        id=f"ing_{n}", raw_text=seg, name=seg, percentage=float(pct.group(1)) if pct else None,
        evidence=evidence_for_span(laid_ing, s, e, seg), readability="clear", confidence=0.95,
    ))
ING = {i.name.split(" (")[0]: i for i in ingredients}


def statement(sid, typ, raw, items, laid):
    return AllergenStatement(id=sid, type=typ, raw_text=raw, items=items,
                             evidence=evidence_for_span(laid, 0, len(raw), raw))


statements = [
    statement("alg_0", "contains", ALG1, ["Peanut", "Milk", "Wheat", "Soy"], laid_a1),
    statement("alg_1", "may_contain", ALG2, ["Tree Nuts"], laid_a2),
]

veg_ev = Evidence(image_id=IMG, text="Green vegetarian mark", box=veg_box, match_score=0.0, status="approximate")
claim = Claim(id="clm_0", raw_text="HIGH PROTEIN",
              evidence=[Evidence(image_id=IMG, text="HIGH PROTEIN", box=union([c1, c2]),
                                 token_ids=[c1.token_id, c2.token_id], match_score=0.99, status="verified")])

extraction = LabelExtraction(
    scan_id="scan_demo_0001",
    images=[ImageInfo(image_id=IMG, width=W, height=H, panel_hint="back",
                      quality=ImageQuality(ok=True, blur_score=812.4, glare_ratio=0.004, brightness=214.0))],
    ocr_tokens=tokens,
    product_name="Nuvo Choco Nut Crunch Bar",
    languages_detected=["en"],
    ingredients=ingredients,
    ingredients_section=SectionStatus(presence="found", complete=True),
    nutrition=NutritionTable(serving_size=40, serving_unit="g", servings_per_pack=3, pack_size=120,
                             pack_unit="g", rows=rows),
    nutrition_section=SectionStatus(presence="found", complete=False, issues=["unreadable_span"],
                                    unreadable_regions=[sodium_region]),
    allergen_statements=statements,
    allergen_section=SectionStatus(presence="found", complete=True),
    veg_mark=VegMark(value="veg", evidence=veg_ev),
    claims=[claim],
    meta=ExtractionMeta(provider="fixture", model="fixture", attempts=2, duration_ms=4120, retries=[
        RetryRecord(reason="nutrition_value_unreadable:sodium_mg", action="reread_region:img_0",
                    outcome="unchanged"),
    ]),
)

# ------------------------------------------------------------------------------------------
# 3. Profiles + catalog
# ------------------------------------------------------------------------------------------
FSA = "UK FSA front-of-pack 'high' threshold"
catalog = [
    *[RestrictionCatalogItem(key=k, kind="allergy", label_en=l, default_severity="strict", categories=c,
                             description_en=d) for k, l, c, d in [
        ("peanut", "Peanut allergy", ["peanut"], "Peanuts, groundnuts and peanut-derived ingredients."),
        ("tree_nut", "Tree nut allergy", ["tree_nut"], "Almond, cashew, walnut, pistachio, hazelnut and similar."),
        ("milk", "Milk allergy", ["milk"], "Milk and milk-derived ingredients such as whey and casein."),
        ("egg", "Egg allergy", ["egg"], "Egg and egg-derived ingredients."),
        ("wheat", "Wheat allergy", ["wheat"], "Wheat, maida, atta, semolina, durum."),
        ("soy", "Soy allergy", ["soy"], "Soybean and soy-derived ingredients."),
        ("sesame", "Sesame allergy", ["sesame"], "Sesame seeds, til, sesame oil."),
        ("fish", "Fish allergy", ["fish"], "Fish and fish-derived ingredients."),
        ("crustacean", "Shellfish (crustacean) allergy", ["crustacean"], "Prawn, shrimp, crab, lobster."),
        ("mustard", "Mustard allergy", ["mustard"], "Mustard seed, mustard oil, rai."),
        ("sulphite", "Sulphite sensitivity", ["sulphite"], "Sulphites and sulphur dioxide (INS 220-228)."),
    ]],
    RestrictionCatalogItem(key="lactose", kind="intolerance", label_en="Lactose intolerance",
                           default_severity="preference", categories=["milk"],
                           description_en="Milk-derived ingredients that may contain lactose."),
    RestrictionCatalogItem(key="gluten", kind="intolerance", label_en="Gluten-free (coeliac)",
                           default_severity="strict", categories=["gluten", "wheat"],
                           description_en="Wheat, barley, rye and oats unless labelled gluten-free."),
    RestrictionCatalogItem(key="vegetarian", kind="diet", label_en="Vegetarian (no egg)", default_severity="strict",
                           categories=["meat", "poultry", "fish_derived", "egg_derived", "gelatin", "animal_derived",
                                       "insect_derived"],
                           description_en="Indian vegetarian: no meat, fish, egg, gelatin or insect-derived colours."),
    RestrictionCatalogItem(key="eggetarian", kind="diet", label_en="Vegetarian (egg OK)", default_severity="strict",
                           categories=["meat", "poultry", "fish_derived", "gelatin", "animal_derived", "insect_derived"],
                           description_en="Vegetarian that allows egg."),
    RestrictionCatalogItem(key="vegan", kind="diet", label_en="Vegan", default_severity="strict",
                           categories=["meat", "poultry", "fish_derived", "egg_derived", "gelatin", "animal_derived",
                                       "insect_derived", "dairy", "honey"],
                           description_en="No animal-derived ingredients at all."),
    RestrictionCatalogItem(key="jain", kind="diet", label_en="Jain", default_severity="strict",
                           categories=["meat", "poultry", "fish_derived", "egg_derived", "gelatin", "animal_derived",
                                       "insect_derived", "honey", "onion", "garlic", "root_vegetable", "alcohol"],
                           description_en="Vegetarian, plus no onion, garlic, root vegetables, honey or alcohol."),
    RestrictionCatalogItem(key="no_onion_garlic", kind="diet", label_en="No onion / garlic",
                           default_severity="strict", categories=["onion", "garlic"],
                           description_en="Avoids onion and garlic in any form."),
    RestrictionCatalogItem(key="diabetes_sugar", kind="health_limit", label_en="Diabetic: limit sugar",
                           default_severity="strict", categories=["added_sugar", "sugar_alias"], needs_threshold=True,
                           default_threshold=Threshold(nutrient="total_sugars_g", max_value=22.5, source_note=FSA),
                           description_en="Flags sugar above your limit per 100 g and hidden sugar ingredients."),
    RestrictionCatalogItem(key="low_sodium", kind="health_limit", label_en="Low sodium (BP)",
                           default_severity="strict", categories=[], needs_threshold=True,
                           default_threshold=Threshold(nutrient="sodium_mg", max_value=600, source_note=FSA),
                           description_en="Flags sodium above your limit per 100 g."),
    RestrictionCatalogItem(key="low_sat_fat", kind="health_limit", label_en="Limit saturated fat",
                           default_severity="preference", categories=[], needs_threshold=True,
                           default_threshold=Threshold(nutrient="saturated_fat_g", max_value=5, source_note=FSA),
                           description_en="Flags saturated fat above your limit per 100 g."),
    *[RestrictionCatalogItem(key=k, kind="avoid", label_en=l, default_severity="preference", categories=c,
                             description_en=d) for k, l, c, d in [
        ("palm_oil", "Avoid palm oil", ["palm_oil"], "Palm oil, palmolein and palm fat."),
        ("artificial_sweetener", "Avoid artificial sweeteners", ["artificial_sweetener"],
         "Aspartame, sucralose, acesulfame-K, saccharin and similar."),
        ("caffeine", "Avoid caffeine", ["caffeine"], "Caffeine, coffee, guarana."),
        ("added_msg", "Avoid MSG", ["added_msg"], "Monosodium glutamate (INS 621) and added glutamates."),
        ("alcohol", "Avoid alcohol", ["alcohol"], "Alcohol and alcohol-based flavourings when declared."),
    ]],
]
CAT = {c.key: c for c in catalog}


def restr(rid, key, label=None, severity=None, threshold=None):
    c = CAT[key]
    return Restriction(id=rid, kind=c.kind, key=key, label=label or c.label_en,
                       severity=severity or c.default_severity, threshold=threshold or c.default_threshold)


profiles = [
    Profile(profile_id="p_aarav", name="Aarav", color="#ff7a59",
            restrictions=[restr("r_aarav_peanut", "peanut"), restr("r_aarav_treenut", "tree_nut")]),
    Profile(profile_id="p_thatha", name="Thatha", color="#7c9cff",
            restrictions=[restr("r_thatha_sugar", "diabetes_sugar"), restr("r_thatha_sodium", "low_sodium")]),
    Profile(profile_id="p_lakshmi", name="Lakshmi", color="#5fd3a5",
            restrictions=[restr("r_lakshmi_jain", "jain"), restr("r_lakshmi_sesame", "sesame")]),
]

# ------------------------------------------------------------------------------------------
# 4. Engine output (hand-written truth for this label)
# ------------------------------------------------------------------------------------------
ANN = {
    "Sugar": (["sugar"], ["added_sugar"], "plant"),
    "Peanuts": (["peanut"], ["peanut"], "plant"),
    "Milk Solids": (["milk_solids"], ["milk", "dairy"], "animal"),
    "Refined Wheat Flour": (["wheat_flour"], ["wheat", "gluten"], "plant"),
    "Cocoa Butter": (["cocoa_butter"], [], "plant"),
    "Edible Vegetable Oil": (["palm_oil"], ["palm_oil"], "plant"),
    "Invert Sugar Syrup": (["invert_sugar"], ["added_sugar", "sugar_alias"], "plant"),
    "Emulsifier": (["ins_322"], ["soy"], "plant"),
    "Iodised Salt": (["salt"], [], "mineral"),
    "Raising Agent": (["ins_500"], [], "mineral"),
    "Natural Flavours": (["natural_flavours"], [], "varies"),
}
annotations = [IngredientAnnotation(
    ingredient_id=ING[k].id, canonical_ids=v[0], categories=v[1], origin=v[2], source="kb",
    note="Source not declared on label" if v[2] == "varies" else None) for k, v in ANN.items()]


def result(rid, state, code, key, params, evidence, matches, unknown_kind=None, conf=1.0):
    return RestrictionResult(restriction_id=rid, state=state, unknown_kind=unknown_kind, reason_code=code,
                             message_key=key, message_params=params, explanation=msg(key, **params),
                             evidence=evidence, matches=matches, confidence=conf)


pea = ING["Peanuts"]
sug = ING["Sugar"]; inv = ING["Invert Sugar Syrup"]; nat = ING["Natural Flavours"]
reports = [
    ProfileReport(profile_id="p_aarav", overall="conflict", results=[
        result("r_aarav_peanut", "conflict", "CONFLICT_INGREDIENT", "verdict.conflict.ingredient",
               {"term": "Peanuts (22%)", "category": "peanut"}, pea.evidence + statements[0].evidence,
               [Match(ingredient_id=pea.id, term="Peanuts", canonical_id="peanut", category="peanut", source="kb"),
                Match(term="PEANUT", category="peanut", source="allergen_statement")]),
        result("r_aarav_treenut", "possible", "POSSIBLE_MAY_CONTAIN", "verdict.possible.may_contain",
               {"item": "TREE NUTS"}, statements[1].evidence,
               [Match(term="TREE NUTS", category="tree_nut", source="allergen_statement")]),
    ]),
    ProfileReport(profile_id="p_thatha", overall="conflict", results=[
        result("r_thatha_sugar", "conflict", "CONFLICT_THRESHOLD", "verdict.conflict.threshold",
               {"nutrient": "total_sugars_g", "value": 38.0, "unit": "g", "basis": "per_100g", "limit": 22.5},
               [row_ev["total_sugars_g"]] + sug.evidence + inv.evidence,
               [Match(term="Total Sugars 38.0 g", category="added_sugar", source="nutrition"),
                Match(ingredient_id=sug.id, term="Sugar", canonical_id="sugar", category="added_sugar", source="kb"),
                Match(ingredient_id=inv.id, term="Invert Sugar Syrup", canonical_id="invert_sugar",
                      category="sugar_alias", source="kb")]),
        result("r_thatha_sodium", "unknown", "UNKNOWN_NUTRIENT_MISSING", "verdict.unknown.nutrient_missing",
               {"nutrient": "sodium_mg"}, [sodium_region], [], unknown_kind="undeterminable"),
    ]),
    ProfileReport(profile_id="p_lakshmi", overall="possible", results=[
        result("r_lakshmi_jain", "possible", "POSSIBLE_AMBIGUOUS_SOURCE", "verdict.possible.ambiguous_source",
               {"term": "Natural Flavours", "category": "onion|garlic"}, nat.evidence + [veg_ev],
               [Match(ingredient_id=nat.id, term="Natural Flavours", canonical_id="natural_flavours", source="kb",
                      note="Green veg mark rules out meat/egg; onion/garlic/root vegetables cannot be ruled out.")],
               conf=0.7),
        result("r_lakshmi_sesame", "not_listed", "NOT_LISTED_COMPLETE", "verdict.not_listed.complete", {},
               [], []),
    ]),
]
for rep in reports:
    rep.summary = {
        "p_aarav": "Conflict for Aarav: it contains peanuts, and the label warns it may contain tree nuts.",
        "p_thatha": "Conflict for Thatha: 38 g sugar per 100 g, above the 22.5 g limit. Sodium couldn't be read.",
        "p_lakshmi": "Check this for Lakshmi: sesame is not listed, but for Jain rules 'natural flavours' "
                     "doesn't say what it is made from.",
    }[rep.profile_id]
    rep.summary_lang = "en"

declared, computed = 520.0, 9.5 * 4 + 58.0 * 4 + 28.0 * 9
nutrition_analysis = NutritionAnalysis(
    per_100={k: v for k, _, _, _, _, v, _ in ROWS if v is not None},
    per_pack={k: round(v * 1.2, 2) for k, _, _, _, _, v, _ in ROWS if v is not None},
    servings_per_pack=3,
    consistency=ConsistencyCheck(status="consistent", declared_kcal=declared, computed_kcal=computed,
                                 deviation_pct=round(abs(computed - declared) / declared * 100, 2),
                                 message_key="nutrition.consistency.ok"),
    notes=["nutrition.serving_small"],
)

scan = ScanResult(
    scan_id="scan_demo_0001", lang="en", created_at="2026-10-16T13:00:00+05:30",
    extraction=extraction, annotations=annotations, nutrition_analysis=nutrition_analysis, reports=reports,
    unknowns=[UnknownItem(section="nutrition", message_key="unknown.unreadable_span", detail="Sodium row",
                          region=sodium_region)],
)

# ------------------------------------------------------------------------------------------
# 5. Other endpoint samples
# ------------------------------------------------------------------------------------------
ask = AskResponse(
    answer="No, this isn't a good fit for Thatha. It has 38 g of total sugars per 100 g, above his 22.5 g "
           "limit, and it lists sugar and invert sugar syrup. I also couldn't read the sodium value.",
    lang="en", grounded=True,
    tool_calls=[
        ToolCallTrace(tool="get_profiles", args={}, result_summary="3 profiles: Aarav, Thatha, Lakshmi"),
        ToolCallTrace(tool="get_verdict", args={"profile_id": "p_thatha"},
                      result_summary="overall=conflict; sugar=conflict; sodium=unknown"),
        ToolCallTrace(tool="find_evidence", args={"query": "total sugars"}, result_summary="1 verified match"),
    ],
    evidence=[row_ev["total_sugars_g"]] + sug.evidence + inv.evidence,
    verdict_refs=[VerdictRef(profile_id="p_thatha", restriction_id="r_thatha_sugar"),
                  VerdictRef(profile_id="p_thatha", restriction_id="r_thatha_sodium")],
)

parse = ProfileParseResponse(
    profiles=[
        Profile(profile_id="p_new_1", name="Aarav", restrictions=[
            restr("r_new_1", "peanut").model_copy(update={"source_text": "allergic to peanuts"}),
            restr("r_new_2", "tree_nut").model_copy(update={"source_text": "and cashews"}),
        ]),
        Profile(profile_id="p_new_2", name="Father", restrictions=[
            restr("r_new_3", "diabetes_sugar").model_copy(update={"source_text": "my father is diabetic"}),
        ]),
        Profile(profile_id="p_new_3", name="Me", restrictions=[
            restr("r_new_4", "jain").model_copy(update={"source_text": "I am Jain"}),
        ]),
    ],
    unparsed=[], warnings=["Cashew was mapped to 'Tree nut allergy'. Please confirm."],
)

explain = ExplainResponse(
    term="INS 322", canonical_id="ins_322", display_name="Lecithin (INS 322)",
    description="An emulsifier that keeps fats and water mixed. Usually made from soy or sunflower.",
    origin="varies", categories=["soy"], source="kb",
    caution="If the source is soy, it matters for soy allergies. This label says [Soy].",
)

health = HealthResponse(status="ok", providers={"gemini": True, "ollama": True}, engine_mode="stub")


def dump(name: str, obj) -> None:
    data = obj.model_dump(mode="json") if hasattr(obj, "model_dump") else [o.model_dump(mode="json") for o in obj]
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


dump("scan_result.json", scan)
dump("profiles.json", profiles)
dump("catalog.json", catalog)
dump("ask_response.json", ask)
dump("profile_parse.json", parse)
dump("explain.json", explain)
dump("health.json", health)
print(f"OK: {len(tokens)} OCR tokens, {len(ingredients)} ingredients, {len(catalog)} catalog items")
