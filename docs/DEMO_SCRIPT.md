# Demo video script (3 minutes)

**Goal:** show the problem, the working app and why its answers can be trusted. Every claim on screen must be
something the app really does: never say "safe" or "healthy", even in the narration.

**Story:** Lakshmi buys for her family. Aarav (8) has a peanut and tree-nut allergy. Thatha (67) is diabetic and
watches sodium. Lakshmi is Jain and has a mild sesame allergy. This is the family in "Try the demo label".

---

## Before recording (checklist)

1. **Backend:** restart it with a working Gemini key. `http://localhost:8000/api/health` must show `"gemini": true`.
2. **Warm the cache** with the packets you'll scan live (`python -m backend.scripts.warm_cache "<photos>"`), so the
   live scan answers instantly.
3. **Phone:** open the app over HTTPS (cloudflared link or the Vercel URL). Allow the camera and microphone. Set the
   theme you want and close other apps.
4. **Family:** on the Family page, add Aarav, Thatha and Lakshmi exactly as above (the demo label brings its own
   copy; a live scan uses the saved family).
5. **Props:** one real packet whose label is readable (the Bingo pack works well), and a second packet for comparison.
6. **Recording:** record the phone screen (Android: screen recorder; iPhone: Control Centre → Screen Recording)
   plus a separate camera shot of the packet in hand. Record the voiceover separately for a clean sound.
7. **Rehearse twice.** Do a dry run of the comparison and the Telugu question on the recording phone; available
   voices differ per device.

## Shot list

| Time | On screen | Voiceover (say in your own words) |
|---|---|---|
| 0:00–0:20 | Close-up of a real packet's small print; zoom on "INS 322", "milk solids", a smudged value. | "This label is complete, but in a shop aisle it is unreadable. Milk hides as whey or milk solids, animal products hide behind codes like INS 441, and a blurry photo doesn't tell you what's missing. One shopper buys for a child with a peanut allergy, a diabetic grandfather and a Jain mother." |
| 0:20–0:30 | Home page → tap **Scan a label**. | "LabelLens checks one photo for the whole family, and shows you the words behind every answer." |
| 0:30–0:55 | Live camera on the packet: the hint pill ("Hold steady" → "Looks sharp"), tap the shutter, add a second photo, tap **Analyse**. Show the analysing screen with its honest stage text. | "The camera coaches you to a sharp photo. You can add the back and the side if the ingredients wrap around. It reads every word with OCR, the AI structures the label citing those words, and a rules engine decides." |
| 0:55–1:20 | Result: family strip with each person's state. Tap **Aarav: Conflict** → tap the evidence chip "Peanuts (22%)": the photo zooms to the words. | "Four states only: Conflict, Check this, Not listed, Unknown. Never 'safe'. Every flag points at the exact words on the packet. Tap it and you see them." |
| 1:20–1:40 | **Thatha:** sugar Conflict ("38 g per 100 g, above your limit of 22.5 g"), sodium **Can't determine** → **Couldn't read** tab → **Retake this area**. | "When the sodium value is smudged, LabelLens doesn't guess. It says it can't determine, and points to the exact area to retake." |
| 1:40–2:00 | **Lakshmi: Check this**, "Natural Flavours can come from onion or garlic sources". Tap **No, it doesn't** → the verdict changes to **Not listed — Checked by you**. | "Ambiguous ingredients are flagged, not decided. Lakshmi checks the pack, answers once, and every verdict is rechecked. The app records that she checked, not that it decided." |
| 2:00–2:20 | Ask bar: tap the mic, ask in Telugu "ఇది నాకు సరిపోతుందా?" (or type it). Show the answer, the "How it checked" tool steps, and play read-aloud. | "Thatha reads Telugu more comfortably than English small print. He asks by voice, and the answer comes only from the engine's verdicts and the label's words." |
| 2:20–2:40 | **Compare with another product** → scan the second packet → the comparison screen: each person's verdicts for A and B, per-100 g nutrition side by side. | "Standing in the aisle, the next question is which packet. Comparison puts both side by side for each person, per 100 grams, without calling either one 'healthier'." |
| 2:40–2:55 | **How it works** page: the pipeline and the four states. Then flash `docs/TEST_RESULTS.md` (3 tests × 3 runs, pass) and the architecture diagram from the README. | "Under the hood: OCR evidence, an AI that must cite what it reads, and a deterministic rules engine with over 900 tests. Our acceptance tests caught and fixed the ways an AI misled us: an invented veg mark, a number moved to the wrong row, and a missed allergen line." |
| 2:55–3:00 | Logo and tagline. | "We never say safe. We show you why." |

## If something fails while recording

- **The AI is slow or down:** use **Try the demo label**. Its confirmation and recheck need only the backend's rules
  engine, not the AI. With no backend at all it still shows every verdict, evidence zoom and "Couldn't read", but a
  confirmation won't change the verdict, and there's no live scan or comparison. If a live scan falls back to basic reading, show the "Basic reading only" banner:
  it demonstrates honest degradation.
- **No Telugu voice on the phone:** type the question; read-aloud then offers English.
- **The camera won't open:** use **Upload a photo** on the scan screen.

## Things not to say

- "Safe", "healthy", "guaranteed", "approved", "certified".
- "It detects all allergens." Say "it shows what the label says, and what it couldn't read."
- Accuracy percentages: real-packet accuracy is not measured yet. Quote the acceptance tests instead.
