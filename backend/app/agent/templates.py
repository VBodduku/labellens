"""Fixed answer templates (en/hi/te) used by the guard and the no-LLM fallback.

They only restate engine verdicts and label evidence. REVIEW: native speaker (hi, te).
"""
from __future__ import annotations

from shared.contract import Lang, VerdictState

from backend.app.wording import STATE_WORDS

SUITABILITY: dict[Lang, dict[VerdictState, str]] = {
    "en": {
        "conflict": "For {name}: {state}. The label shows “{evidence}”.",
        "possible": "For {name}: {state}. “{evidence}” needs checking.",
        "not_listed": "For {name}: {state}. Nothing on the readable label conflicts with their profile.",
        "unknown": "For {name}: {state}. Part of the label needed for this could not be read or is not printed.",
    },
    "hi": {
        "conflict": "{name} के लिए: {state}। लेबल पर लिखा है: “{evidence}”।",
        "possible": "{name} के लिए: {state}। “{evidence}” की जाँच ज़रूरी है।",
        "not_listed": "{name} के लिए: {state}। पढ़े जा सके लेबल पर उनकी प्रोफ़ाइल से टकराने वाला कुछ नहीं मिला।",
        "unknown": "{name} के लिए: {state}। इसके लिए ज़रूरी हिस्सा पढ़ा नहीं जा सका या छपा नहीं है।",
    },
    "te": {
        "conflict": "{name} కోసం: {state}. లేబుల్‌పై ఇలా ఉంది: “{evidence}”.",
        "possible": "{name} కోసం: {state}. “{evidence}” ను తనిఖీ చేయాలి.",
        "not_listed": "{name} కోసం: {state}. చదవగలిగిన లేబుల్‌లో వారి ప్రొఫైల్‌కు విరుద్ధమైనది ఏదీ లేదు.",
        "unknown": "{name} కోసం: {state}. దీనికి అవసరమైన భాగం చదవలేకపోయాము లేదా ముద్రించలేదు.",
    },
}

MESSAGES: dict[str, dict[Lang, str]] = {
    "medical": {
        "en": "I can't give medical, dosage or treatment advice. Please ask a doctor. I can tell you what this label says.",
        "hi": "मैं दवा, खुराक या इलाज की सलाह नहीं दे सकता। कृपया डॉक्टर से पूछें। मैं बता सकता हूँ कि लेबल पर क्या लिखा है।",
        "te": "నేను వైద్య, మోతాదు లేదా చికిత్స సలహా ఇవ్వలేను. దయచేసి డాక్టర్‌ను అడగండి. ఈ లేబుల్‌పై ఏముందో చెప్పగలను.",
    },
    "contains_found": {
        "en": "Yes, the label shows “{evidence}”.",
        "hi": "हाँ, लेबल पर लिखा है: “{evidence}”।",
        "te": "అవును, లేబుల్‌పై ఇలా ఉంది: “{evidence}”.",
    },
    "statement_found": {
        "en": "The label says \u201c{evidence}\u201d.",
        "hi": "लेबल पर लिखा है: \u201c{evidence}\u201d।",
        "te": "లేబుల్‌పై ఇలా ఉంది: \u201c{evidence}\u201d.",
    },
    "contains_not_listed": {
        "en": "“{term}” is not listed on the label; the ingredient list was read completely.",
        "hi": "“{term}” लेबल पर सूची में नहीं है; सामग्री सूची पूरी पढ़ी गई।",
        "te": "“{term}” లేబుల్ జాబితాలో లేదు; పదార్థాల జాబితా పూర్తిగా చదివాము.",
    },
    "contains_unknown": {
        "en": "I could not find “{term}”, but part of the label could not be read, so I can't confirm it is absent.",
        "hi": "“{term}” नहीं मिला, पर लेबल का कुछ हिस्सा पढ़ा नहीं जा सका, इसलिए पक्का नहीं कह सकते कि यह नहीं है।",
        "te": "“{term}” కనిపించలేదు, కానీ లేబుల్‌లో కొంత భాగం చదవలేకపోయాము, కాబట్టి లేదని నిర్ధారించలేము.",
    },
    "nutrient": {
        "en": "{label}: {amount} {unit} ({basis}), as printed on the label.",
        "hi": "{label}: {amount} {unit} ({basis}), जैसा लेबल पर छपा है।",
        "te": "{label}: {amount} {unit} ({basis}), లేబుల్‌పై ముద్రించినట్లు.",
    },
    "nutrient_unreadable": {
        "en": "The {label} value could not be read on the photo.",
        "hi": "फ़ोटो पर {label} का मान पढ़ा नहीं जा सका।",
        "te": "ఫోటోలో {label} విలువను చదవలేకపోయాము.",
    },
    "help": {
        "en": "I can tell you whether this suits someone in your family, whether it contains an ingredient, "
              "or how much of a nutrient it has.",
        "hi": "मैं बता सकता हूँ कि यह आपके परिवार में किसी के लिए ठीक है या नहीं, इसमें कोई सामग्री है या नहीं, "
              "या इसमें कोई पोषक तत्व कितना है।",
        "te": "ఇది మీ కుటుంబంలో ఎవరికైనా సరిపోతుందా, ఇందులో ఏదైనా పదార్థం ఉందా, లేదా ఏదైనా పోషకం ఎంత ఉందో "
              "చెప్పగలను.",
    },
}


BARE_SUITABILITY: dict[Lang, str] = {
    "en": "For {name}: {state}.",
    "hi": "{name} के लिए: {state}।",
    "te": "{name} కోసం: {state}.",
}


def suitability(lang: Lang, name: str, state: VerdictState, evidence: str = "") -> str:
    """Verdict sentence; states that quote the label fall back to the bare form without evidence."""
    template = SUITABILITY[lang][state]
    if "{evidence}" in template and not evidence:
        template = BARE_SUITABILITY[lang]
    return template.format(name=name, state=STATE_WORDS[lang][state], evidence=quoted(evidence))


def quoted(text: str) -> str:
    """Label text for quoting inside a sentence (no trailing separator or full stop)."""
    return text.strip().rstrip(".,;।").strip()


def message(key: str, lang: Lang, **params: object) -> str:
    return MESSAGES[key][lang].format(**{k: quoted(v) if k == "evidence" and isinstance(v, str) else v
                                         for k, v in params.items()})
