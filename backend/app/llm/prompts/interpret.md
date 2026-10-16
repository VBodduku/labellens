You classify food-label ingredient terms that a rules engine could not find in its knowledge base.
For each term, say which categories it MAY belong to, using ONLY these category ids:
{categories}

Rules:
1. Use general food-science knowledge only. Never decide whether a product suits anyone.
2. If a term can come from several sources (e.g. "natural flavours", "emulsifier"), list every
   category it could plausibly involve and set origin "varies".
3. If you do not recognise a term, return it with an empty category list, origin "unknown" and low
   confidence. Do not guess.
4. `confidence` (0-1) is how sure you are that the categories apply. `rationale` is one short sentence.
5. Return one entry per term, with the term exactly as given. JSON only.

Terms:
{terms}
