# Translation review (Hindi / Telugu)

Machine-drafted strings that a native speaker must check before the demo.

Also review the `REVIEW`-marked strings in `backend/app/wording.py` and `backend/app/agent/templates.py`.

## The 20 strings families read first
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
