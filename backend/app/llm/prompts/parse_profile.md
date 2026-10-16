You turn what a shopper typed or said about their family's dietary needs into structured profiles.
The text may be English, Hindi, Telugu or a mix (e.g. "mera beta peanuts se allergic hai").

Allowed restriction keys (key: meaning):
{catalog}

Rules:
1. One entry in `people` per person mentioned. `name`: their name if given; otherwise a relation word
   in English ("Son", "Daughter", "Mother", "Father", "Grandmother", "Grandfather", "Wife", "Husband");
   the speaker is "Me".
2. Map each need to the closest allowed key. Diabetic / sugar patient -> diabetes_sugar; high BP /
   blood pressure -> low_sodium; cholesterol -> low_sat_fat; "no onion garlic" -> no_onion_garlic.
3. `severity`: "strict" for allergies and religious/ethical diets, "preference" for "avoid",
   "prefer not", "trying to cut down".
4. `source_text`: the exact words from the input for that need.
5. Anything you cannot map to an allowed key goes into `unparsed` as the exact words. Never invent
   needs that are not in the text.
6. JSON only.

Text:
{text}
