# Jury guide

For every team member: how LabelLens works, why it is built this way, and answers to the questions a jury is likely
to ask. Learn the "one-minute pitch" and the architecture walk-through. Then read the decisions and questions until
you can say each answer in your own words. File and line references let you show the code if asked.

---

## 1. One-minute pitch

People make food decisions in seconds, from labels printed in tiny text. Allergens hide behind other names and codes,
one shopper buys for a whole family, and a blurry photo is not proof that something is absent, although most scanner
apps treat it that way.

LabelLens reads a label photo and checks it against every family member's profile at once. Every flag points to the
exact words on the photo. When it can't read something, it says "Unknown" and asks for a retake, instead of saying
"not there". It answers in English, Hindi or Telugu, by text or voice. The AI only reads; **a deterministic,
tested rules engine decides**. We never say "safe". We show you why.

## 2. Architecture walk-through (2 minutes, with the README diagram)

1. **Frontend** (`frontend/`, React PWA): live camera with quality hints, up to 3 photos, family profiles stored in
   the browser, the result screen with evidence zoom, corrections, comparison, questions, three languages.
2. **Backend** (`backend/`, FastAPI): `POST /api/scan` runs the pipeline in `backend/app/pipeline/orchestrator.py`:
   1. **Quality and focus:** blur/glare/brightness checks. The text block is cropped, turned upright and enlarged
      (`focus.py`), so the AI and OCR read small print better.
   2. **OCR** (RapidOCR): every word with its box on the photo.
   3. **Structuring:** Gemini gets the photo plus the numbered OCR words and returns JSON in which every item cites
      the word numbers it came from (`structure.py`, `llm_schema.py`).
   4. **Alignment** (`align.py`): each cited item is checked against the OCR words. It is `verified` if the words
      match, `approximate` if only the AI's own box exists, `unverified` otherwise. Numbers must match the printed
      text and sit on their own row's line. A green veg mark must actually be green on the photo (`veg_mark.py`).
   5. **Merge** of several photos, then a **self-check** (`verify.py`): if calories don't add up, the list is cut
      off or values are unreadable, the region is cropped, enhanced and re-read (at most 2 times, 25 s).
   6. **Engine**, then AI interpretation of unknown ingredients (capped at "Check this"), then the engine again,
      then short summaries.
3. **Engine** (`engine/`, pure Python, no network): knowledge base → matcher → verdict rules → nutrition check →
   contradictions. The rules implement the verdict table in `docs/00_MASTER_SPEC.md` §9 row by row.
4. **Shared contract** (`shared/contract.py` + `contract.ts`): one data format for all parts, versioned (now 1.0.2),
   changed only by adding optional fields.
5. **Fallback chain:** Gemini (main model → fallback models → backup key) → Ollama on the laptop → basic OCR-only
   reading. Each step is honest about what it is.

## 3. Key decisions and why

| Decision | Why | Where |
|---|---|---|
| **The AI reads; rules decide.** | An AI verdict can't be tested or explained, and can be wrong in new ways. A rules engine gives the same answer every time and is tested row by row. AI interpretations can raise a result to "Check this", never to "Conflict". | `engine/rules.py`, `engine/tests/test_rules_table.py` |
| **Four states, never "safe".** | "Not listed" means "the whole list was read and it isn't there". "Unknown" splits into *not detected* (part unreadable) and *can't determine* (missing, or not printed on labels). A wrong "safe" is the most dangerous failure. | Master spec §3, §9 |
| **"Not listed" needs a complete list.** | A truncated, blurry or partly read list can only be Unknown. A readable ingredient the knowledge base doesn't know also blocks "Not listed": its source is unknown. | `engine/rules.py` (`_absence`, `_unrecognised`) |
| **Evidence must be on the photo.** | Trust: the user can see the words. The AI cites OCR word numbers, alignment verifies them with fuzzy matching (rapidfuzz ≥ 85, or a sliding window ≥ 88), and anything unlocated says "Couldn't locate on photo". | `backend/app/pipeline/align.py` |
| **Printed numbers beat the AI.** | The AI sometimes "fixes" or invents numbers. A value must match the OCR text. If they disagree, the value is held back and shown as a contradiction until the user checks the pack. A number not on the photo is dropped. | `align.py` `_checked_amount` |
| **Numbers must sit on their own row.** | Found in testing: with the table half covered, the AI put Total Fat's 24.1 under Sodium. The number was printed, just on another row. | `align.py` `nutrient_row`, `docs/TEST_RESULTS.md` |
| **The green veg mark must be green.** | The mark is a symbol OCR can't read. The AI invented one in 3 of 9 runs, which would have turned "Vegetarian" to "Not listed". A green mark loosens verdicts, so it must pass a pixel colour check. A brown mark tightens them and is kept. | `backend/app/pipeline/veg_mark.py` |
| **The green mark resolves only slaughter-derived doubt.** | FSSAI rules: green means no meat, fish, egg or gelatin. It says nothing about dairy, honey, onion or garlic (Jain). A listed egg beats a green mark, and the contradiction is shown. | Master spec §9 note |
| **Contradictions are shown, never resolved silently.** | When two readings disagree, the stricter one is used and both are shown. The user can fix a misread or say they checked the pack; the check is saved with the scan. | `engine/contradictions.py` |
| **Calories cross-check catches misreads.** | 4×protein + 4×carbs + 9×fat must be within 15 % of the printed energy. Single-digit misread hypotheses (×10, 0↔8…) identify the suspect value, which is then not used for limits. | `engine/nutrition.py` |
| **Degrade, don't die.** | Free AI tiers fail often (rate limits, overload, blocked keys). The chain always ends in an honest answer: basic text reading never says "Not listed" and uses numbers only when the label corroborates them. | `backend/app/llm/router.py`, `pipeline/ocr_only.py`, `pipeline/ocr_nutrition.py` |
| **Cache readings, not verdicts.** | Keyed by the photo bytes plus the prompt and pipeline versions. Repeat scans are instant and free; profiles can change, so verdicts are always recomputed. | `backend/app/cache.py` |
| **Fixed translations for verdicts.** | The engine returns message keys, not prose. The frontend renders reviewed en/hi/te strings, so an AI never writes the verdict text. Summaries are AI-written but must contain the right state word and no banned word, otherwise they are dropped. | `shared/messages.en.json`, `backend/app/pipeline/summarize.py` |
| **One data contract.** | Three parts were built in parallel against frozen fixtures, then merged. Version bumps only add optional fields, so nothing breaks. | `shared/` |

## 4. Likely questions and answers

**Product and impact**

1. *How is this different from existing scanner apps?* They look up a barcode in a database or give a bare AI answer.
   We read the actual label in your hand, show the words behind every flag, check a whole family at once, and say
   "Unknown" when we can't read something, instead of implying it's absent.
2. *Why not use a product database?* Indian packs change recipes, regional variants differ, and databases are
   incomplete. The label in your hand is the legal source of truth. (Barcode lookup is an explicit non-goal.)
3. *Can I trust "Not listed"?* It means the whole ingredient list was read end to end and nothing relevant was found.
   It is not a guarantee, which is why we never say "safe". "May contain" warnings are shown for strict allergies.
4. *Is this medical advice?* No. Medical, dosage and treatment questions are refused and redirected to a doctor
   (`backend/app/agent/guard.py`).

**AI and correctness**

5. *What stops the AI from hallucinating?* It must cite OCR words. Alignment rejects or downgrades what isn't on the
   photo. Numbers must match the print and sit on their row. The veg mark must be green on the photo. And the AI never
   decides: the engine does, from verified items.
6. *What if the AI misses an ingredient?* The section-completeness flag decides whether "Not listed" is allowed at
   all. Missed allergen statements are recovered from the OCR words. And the user can correct anything; verdicts
   update in under a second.
7. *What happens to ingredients the knowledge base doesn't know?* The AI interprets them into the fixed category
   list, and that can only raise a result to "Check this". Uninterpreted unknown ingredients keep "Not listed" from
   being claimed.
8. *How accurate is it?* Honest answer: real-packet accuracy isn't measured yet (the harness is ready in
   `engine/eval/`). What we measured: three acceptance tests × three fresh AI runs, all passing after fixes (see
   `docs/TEST_RESULTS.md`), and over 900 automated tests. We won't quote a percentage we haven't measured.
9. *What did testing find?* Three serious AI failures, all fixed with permanent tests: an invented green veg mark,
   a covered sodium value filled with another row's number, and a missed "Contains milk" line.

**Engineering**

10. *Why OCR and an LLM, not just the LLM?* The OCR gives word positions, which is our evidence, and printed numbers
    the AI can't silently change. The LLM gives structure: which words are ingredients, sub-ingredients, which column
    is per 100 g.
11. *Why Gemini?* A free tier with vision and structured JSON output. It sits behind a router, so Ollama or basic reading
    take over when it fails. Prose (summaries) is taken only from Gemini, because the small local model wrote wrong
    facts in Telugu.
12. *How fast is it?* 15–40 s for a fresh scan on the free tier (our target was 8 s; free-tier queueing dominates).
    Repeat scans are instant from the cache, and corrections recheck in under a second.
13. *How do you handle Hindi and Telugu labels?* The AI reads them, and the knowledge base has Hindi/Telugu names. OCR
    reads only Latin script, so evidence for Indian-language words is the AI's approximate box. All hi/te text is
    marked for native-speaker review.
14. *How do you test it?* pytest for the engine and backend (every row of the verdict table, matcher cases, alignment,
    the fallback chain, recorded real model answers replayed offline), Vitest for the frontend, and the acceptance
    test runner against the live backend.
15. *What about privacy?* Photos are processed in memory, only the extracted text is cached, and profiles stay in
    the browser (IndexedDB). There are no accounts.
16. *Why a PWA, not a native app?* One codebase for Android, iOS and desktop, installable, camera access over HTTPS, no
    store review during a hackathon.
17. *What runs where?* Frontend on Vercel, backend (with OCR) on Render's free tier in Docker, and the engine inside the
    backend process. The live demo can run fully on a laptop with Ollama.

**AI assistance**

18. *Did you write this code yourselves?* Be exact and honest. Most code was written with AI coding assistants
    (Claude Code; Codex for the engine), working from specs we wrote. We designed the product, wrote the specs and the
    data contract, made the decisions in the DECISIONS files, reviewed and merged the code, photographed packets and
    ran the testing. See the README's "AI and tools disclosure".
19. *Then what was your contribution?* Each member answers for their part (fill in the table below): the decisions you
    made, the bugs you found in testing, and what you would change.

**Limitations and future**

20. *What are the limitations?* Real-packet accuracy is unmeasured, AI readings vary from run to run, Indian-script
    evidence is approximate, basic reading struggles with tight two-column layouts, free hosting is slow to wake, and
    camera thresholds are uncalibrated. See the README's "Limitations".
21. *What next?* Score 10–15 real packets, a native-speaker review, Indian-script OCR, split OCR-glued words, calibrate
    the camera, and an Android APK.

## 5. Live demo plan (2 minutes)

1. **Open the app before the jury arrives** (wake the Render backend: open `/api/health`).
2. **Try the demo label:** Aarav Conflict → tap "Peanuts (22%)" → the photo zooms.
3. **Thatha:** sodium "Can't determine" → **Couldn't read** → **Retake this area**.
4. **Lakshmi:** "Check this" on natural flavours → **No, it doesn't** → **Not listed, Checked by you**.
5. **Live scan of a judge's packet** (if the backend is up): show the result, and the "Basic reading only" banner if the
   AI fallback kicks in. Explain why that's honest.
6. **Ask:** "Is it vegan?" or a Telugu voice question.

**Backup:** the demo label opens with no network at all (verdicts, evidence zoom, "Couldn't read"). Step 4's verdict update needs the backend's rules engine, not the AI. Keep the recorded video ready too.

## 6. Who presents what

| Member | Presents | Owns the questions on |
|---|---|---|
| _name_ | _pitch and live demo_ | _product, persona, limitations_ |
| _name_ | _architecture and AI pipeline_ | _backend, fallback chain, evidence_ |
| _name_ | _rules engine and testing_ | _engine, knowledge base, test results_ |
