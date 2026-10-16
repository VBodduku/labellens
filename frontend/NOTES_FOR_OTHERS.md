# Notes from Part 1 (frontend) for other parts / main

## Requests for `main` (humans decide)
1. **`.env.example`: set `VITE_API_BASE_URL=` (empty) and add `API_PROXY_TARGET=http://localhost:8000`.** The browser calls same-origin `/api`; Vite (dev and preview) proxies it to `API_PROXY_TARGET` — on the integration setup that is the Mac's backend. With `VITE_API_BASE_URL=http://localhost:8000` a phone or cloudflared tunnel calls *its own* localhost and every request fails. Set `VITE_API_BASE_URL` only for the Vercel build (deployed backend URL).
2. **Fixture summary wording (`shared/fixtures/scan_result.json`, Lakshmi):** "Probably fine for Lakshmi's sesame allergy…" reads as reassurance. Part 3 flagged the same. Please keep generated summaries in the four-state wording.

## For Part 2 (backend)
- `Correction.field_path` values look like `ingredients[3].name` and `nutrition.rows[2].values[0].amount` (dot keys, bracket indices). `/api/recheck` receives the extraction with corrections already applied and listed in `user_corrections`.
- `/api/recheck` is also called when the user switches language (to regenerate `summary` in that language) and when saved profiles change; the UI shows a template summary built from message keys until then.
- Scan uploads name files `panel_<i>.jpg|png` in order; `panel_hints` is a JSON array aligned with `images`. Retake replaces panel *i* and rescans, so images must stay named `img_<index>` in upload order.
- Evidence for an unreadable region should keep its `box` even when `text` is empty — the UI shows it as a "Hard-to-read area" chip and offers a retake.
- The frontend maps unknown `error_code` values (e.g. `NOT_FOUND`) to the generic message and shows `X-Request-ID` as "Reference: …" on errors.
- `ocr_only` results show a banner: "Basic reading only — the AI reader was unavailable, so missing items can't be confirmed."
- `/api/ask`: the UI renders `tool_calls` for `get_profiles`, `get_verdict` (`args.profile_id`), `find_evidence` (`args.query`), `explain_ingredient` (`args.term`) and `get_nutrition` (`args.key`) in plain language; any other tool shows "Used <tool>". `refusal: "medical_advice"` and `grounded: false` get their own styling.

- **Deploy (Phase 4):** the Vercel build calls `VITE_API_BASE_URL` directly (cross-origin), so the backend's `CORS_ORIGINS` must include the Vercel production domain and any preview domains being tested. Errors should keep `X-Request-ID` in `Access-Control-Expose-Headers` so the UI can show "Reference: …".
- `RATE_LIMITED` responses: please include `retry_after_s` in the error body (the header alone is not read); the UI counts it down and keeps Retry disabled until zero.

## For Part 3 (engine)
- The About page reads `frontend/public/metrics.json` in the shape of `engine/eval/reports/metrics.json` (`dataset_kind`, `packets`, `real_packets`, rates as 0–1 fractions, `confusion_matrix[expected][given]` over the four states, `average_latency_ms`, `limitations`). It is shown as measured accuracy **only** when `dataset_kind` is `"real"` and `real_packets > 0`. When the real evaluation is done, copy the file over `frontend/public/metrics.json` (or ask a human to).

## For native speakers — please review these 20 strings first
`src/i18n/hi.json` and `src/i18n/te.json` contain full drafts of every key (marked NEEDS HUMAN REVIEW). The strings below are what families read first and must be exactly right. Check meaning, tone (respectful, plain), and that `{placeholders}` still read naturally once filled in (e.g. `{category}` = "मूँगफली" / "వేరుశనగ", `{basis}` = "100 ग्राम" / "100 గ్రా").

| # | Key | English | हिन्दी | తెలుగు |
|---|---|---|---|---|
| 1 | `state.conflict` | Conflict | टकराव | విరుద్ధం |
| 2 | `state.possible` | Check this | इसे जाँचें | ఇది తనిఖీ చేయండి |
| 3 | `state.not_listed` | Not listed | सूची में नहीं | జాబితాలో లేదు |
| 4 | `state.unknown.not_detected` | Not detected | पता नहीं चला | కనబడలేదు |
| 5 | `state.unknown.undeterminable` | Can't determine | तय नहीं हो सकता | నిర్ణయించలేం |
| 6 | `overall.conflict` | Conflicts with this profile | इस प्रोफ़ाइल से टकराव है | ఈ ప్రొఫైల్‌కు విరుద్ధంగా ఉంది |
| 7 | `overall.possible` | Check before eating | खाने से पहले जाँचें | తినే ముందు తనిఖీ చేయండి |
| 8 | `overall.not_listed` | No conflicts on the readable label | पढ़ने योग्य लेबल पर कोई टकराव नहीं | చదవగలిగిన లేబుల్‌లో విరుద్ధమైనవేవీ లేవు |
| 9 | `overall.unknown` | Can't fully check this label | इस लेबल को पूरी तरह नहीं जाँच सकते | ఈ లేబుల్‌ను పూర్తిగా తనిఖీ చేయలేం |
| 10 | `verdict.conflict.ingredient` | Lists {term} — this counts as {category}. | सूची में {term} है — यह {category} में गिना जाता है। | జాబితాలో {term} ఉంది — ఇది {category} కిందకు వస్తుంది. |
| 11 | `verdict.conflict.threshold` | {nutrient} is {value} {unit} per {basis}, above your limit of {limit} {unit}. | {nutrient} प्रति {basis} {value} {unit} है, जो आपकी सीमा {limit} {unit} से ज़्यादा है। | {nutrient} ప్రతి {basis} కి {value} {unit} ఉంది, ఇది మీ పరిమితి {limit} {unit} కంటే ఎక్కువ. |
| 12 | `verdict.possible.may_contain` | The label warns it may contain {item}. | लेबल चेतावनी देता है कि इसमें {item} हो सकता है। | ఇందులో {item} ఉండవచ్చని లేబుల్ హెచ్చరిస్తోంది. |
| 13 | `verdict.possible.ambiguous_source` | {term} can come from {category} sources; the label does not say which. | {term} {category} से बन सकता है; लेबल नहीं बताता कि किससे। | {term} {category} నుంచి రావచ్చు; దేని నుంచో లేబుల్ చెప్పలేదు. |
| 14 | `verdict.not_listed.complete` | Not listed anywhere in the full ingredient list. | पूरी सामग्री-सूची में कहीं नहीं लिखा है। | పూర్తి పదార్థాల జాబితాలో ఎక్కడా లేదు. |
| 15 | `verdict.unknown.nutrient_missing` | {nutrient} is not readable on this label. | इस लेबल पर {nutrient} पढ़ा नहीं जा सकता। | ఈ లేబుల్‌పై {nutrient} చదవలేకపోయాం. |
| 16 | `verdict.unknown.unreadable` | Some ingredients are unreadable. No {category} found in the readable part. | कुछ सामग्री पढ़ी नहीं जा सकीं। पढ़ने योग्य हिस्से में {category} नहीं मिला। | కొన్ని పదార్థాలు చదవలేకపోయాం. చదవగలిగిన భాగంలో {category} కనబడలేదు. |
| 17 | `restrictions.diabetes_sugar` | Diabetic: limit sugar | डायबिटीज़: चीनी सीमित | మధుమేహం: చక్కెర పరిమితి |
| 18 | `restrictions.jain` / `restrictions.no_onion_garlic` | Jain / No onion / garlic | जैन / प्याज़ / लहसुन नहीं | జైన్ / ఉల్లి / వెల్లుల్లి లేకుండా |
| 19 | `ask.refusal.medical` | That needs a doctor or dietitian — LabelLens can only tell you what the label says. | इसके लिए डॉक्टर या आहार विशेषज्ञ चाहिए — LabelLens सिर्फ़ बता सकता है कि लेबल क्या कहता है। | దీనికి డాక్టర్ లేదా డైటీషియన్ కావాలి — లేబుల్ ఏం చెబుతుందో మాత్రమే LabelLens చెప్పగలదు. |
| 20 | `quality.blurry` / `scan.hint.good` | The photo is blurry. Hold steady. / Looks sharp — hold still | फ़ोटो धुंधली है। स्थिर रखें। / साफ़ दिख रहा है — स्थिर रखें | ఫోటో మసకగా ఉంది. కదలకుండా పట్టుకోండి. / స్పష్టంగా ఉంది — కదలకుండా ఉంచండి |

Also worth a look: `categories.*` (used inside sentences), `nutrients.*`, `basis.*`, and the voice prompts `speech.*`. Edit the JSON files directly — the tests fail if a key or `{placeholder}` goes missing.
