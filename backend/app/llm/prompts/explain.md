Explain the food-label ingredient or additive "{term}" for a shopper, in {language}.

Rules:
1. `display_name`: the common name (in {language}). `description`: at most 2 short, factual sentences:
   what it is and what it is usually made from.
2. `origin`: plant, animal, insect, synthetic, mineral, microbial, varies or unknown. If it can come
   from different sources, use "varies" and say so in the description.
3. `categories`: only from this list, and only those it may involve: {categories}
4. `caution`: one short sentence if the source or composition can vary or you are unsure, else null.
5. No health, safety or medical claims. If you do not know the term, say that you are not sure.
6. JSON only.
