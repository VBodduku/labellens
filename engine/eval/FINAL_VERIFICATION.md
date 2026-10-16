# Feature-freeze follow-up verification

The original 575 tests passed on re-run. Adversarial review then found two matcher
defects and one capture-integrity defect that those tests did not cover. All three
were reproduced with failing tests before their fixes. The suite now has **590
passing tests**, including the shared fixture scenario; strict Mypy and Ruff pass.
Public API and KB coverage remain five functions, 29 restrictions and 260 entries.
No new verdict rules, categories or KB entries were added.

## Reproduced dangerous misses

These are constructed review cases, not photographed packet observations.
Each case has a complete readable ingredient section, no allergen statement and
no veg-mark signal. The expected conflict follows the explicit ingredient text.

| Input | Profile | Before | After |
| --- | --- | --- | --- |
| `ﬃbre,Peanuts` | peanut | not_listed | conflict |
| `ﬄour,Milk` | milk | not_listed | conflict |
| `İNGREDIENT,MILK` | milk | not_listed | conflict |
| `ﬃbre，Peanuts` | peanut | not_listed | conflict |
| `acetic acid esters of mono and diglyceride egg` | egg | not_listed | conflict |
| `mixed acetic and tartaric acid esters of mono and diglyceride egg` | egg | not_listed | conflict |

Whole-string NFKC/lowercasing can expand characters. The splitter had used normalized
offsets to slice original text, cutting letters off the next ingredient. It now
normalizes delimiter candidates while retaining original offsets and source text.
Fuzzy compound repair had discarded an unrelated exact egg match when replacing
the whole fragment with a long additive alias. Replacement now requires each exact
span to belong to the candidate compound. OCR-spaced cocoa butter/buckwheat retain
their compound protection. Evidence text stays exactly as supplied.

The 14 new matcher/splitter regressions cover the six conflict cases, source-text
offsets, fullwidth punctuation and compound controls. A separate exhaustive review
of all 477 aliases with definite categories after an expanding Unicode prefix
found zero lost definite categories after the fix. This is KB/matcher consistency
verification, not an estimate of real-packet accuracy.

## Interrupted recapture

A controlled KeyboardInterrupt reproduced a stale-manifest bug: old responses could
be scored after an interrupted rerun because the prior manifest still said complete.
Capture now writes all case IDs as pending before replacing any response. A stopped
or failed batch is rejected by the scorer; only a fully completed batch clears
pending. The fifteenth new regression proves that no report is written in this case.

## Rechecks and limits

The two saved synthetic cases were re-evaluated and all three report artifacts
regenerated. Their existing scores remain unchanged (93.75% verdict/nutrient accuracy,
zero dangerous misses in that synthetic set). About metrics remain pending with
zero real packets and null rates. Those scores are not combined with the adversarial
cases to manufacture a real headline metric.

Fixture-only timing over 300 calls with eight profiles: **5.3447 ms median,
5.6530 ms p95, 6.0957 ms maximum**; 10 warmups, Python 3.13.9 on macOS arm64.
Raw results are in performance.json. The largest-real-label target remains unmeasured.

The actual backend is still unreachable outside the sandbox and the real dataset
still contains only its template. Live extraction accuracy, real dangerous misses,
live request latency, largest-real-label timing and integrated About-page verification
remain outstanding. The engine cannot complete those checks without the real input
folders and running backend. See dataset/README.md for commands.

Re-run code checks from the repository root in the project Python environment:

```
python -m pytest engine/tests
python -c "import engine; print(len(engine.restriction_catalog()))"
```
