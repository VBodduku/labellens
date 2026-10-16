import { Beef, Bug, CircleHelp, FlaskConical, Gem, Leaf, Microscope, Pencil, Shuffle } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Correction, Ingredient, IngredientAnnotation, Origin, ScanResult } from "../../shared/contract";
import { EvidenceChips } from "../evidence/EvidenceChip";
import { IconButton } from "../ui/IconButton";
import type { EditTarget } from "./CorrectionEditor";

const ORIGIN_ICONS: Record<Origin, typeof Leaf> = {
  plant: Leaf,
  animal: Beef,
  insect: Bug,
  synthetic: FlaskConical,
  mineral: Gem,
  microbial: Microscope,
  varies: Shuffle,
  unknown: CircleHelp,
};

interface RowProps {
  ingredient: Ingredient;
  path: string;
  annotations: Map<string, IngredientAnnotation>;
  editedPaths: Set<string>;
  onEdit: (target: EditTarget) => void;
  onExplain: (term: string) => void;
}

function IngredientRow({ ingredient, path, annotations, editedPaths, onEdit, onExplain }: RowProps) {
  const { t } = useTranslation();
  const annotation = annotations.get(ingredient.id);
  const origin = annotation?.origin ?? "unknown";
  const OriginIcon = ORIGIN_ICONS[origin];
  const namePath = `${path}.name`;
  return (
    <li className="py-3">
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-text-dim"
          title={t(`ingredients.origin.${origin}`)}
        >
          <OriginIcon className="size-4" aria-hidden="true" />
          <span className="sr-only">{t(`ingredients.origin.${origin}`)}</span>
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <button
              type="button"
              lang=""
              onClick={() => onExplain(ingredient.name)}
              aria-label={t("explain.open", { name: ingredient.name })}
              className="min-h-8 text-left font-semibold underline touch:min-h-11 decoration-line decoration-dotted underline-offset-4 hover:decoration-text"
            >
              {ingredient.name}
            </button>
            {ingredient.percentage !== null && ingredient.percentage !== undefined && (
              <span className="text-xs text-text-dim">{ingredient.percentage}%</span>
            )}
            {ingredient.readability !== "clear" && (
              <span className="hatch rounded-chip px-2 py-0.5 text-[0.7rem] font-semibold text-unknown shadow-[inset_0_0_0_1px_var(--unknown)]">
                {t(`ingredients.readability.${ingredient.readability}`)}
              </span>
            )}
            {editedPaths.has(namePath) && (
              <span className="rounded-chip bg-beam/15 px-2 py-0.5 text-[0.7rem] font-semibold text-beam">{t("result.edited")}</span>
            )}
          </div>
          {annotation && annotation.categories.length > 0 && (
            <ul className="mt-1.5 flex flex-wrap gap-1">
              {annotation.categories.map((category) => (
                <li key={category} className="rounded-chip bg-surface-2 px-2 py-0.5 text-[0.7rem] text-text-dim">
                  {t(`categories.${category}`)}
                </li>
              ))}
            </ul>
          )}
          <EvidenceChips evidence={ingredient.evidence} state={null} className="mt-2" />
          {ingredient.sub_ingredients.length > 0 && (
            <ul className="mt-2 border-l border-line pl-3">
              {ingredient.sub_ingredients.map((sub, index) => (
                <IngredientRow
                  key={sub.id}
                  ingredient={sub}
                  path={`${path}.sub_ingredients[${index}]`}
                  annotations={annotations}
                  editedPaths={editedPaths}
                  onEdit={onEdit}
                  onExplain={onExplain}
                />
              ))}
            </ul>
          )}
        </div>
        <IconButton
          label={t("ingredients.edit", { name: ingredient.name })}
          onClick={() => onEdit({ kind: "ingredient", fieldPath: namePath, current: ingredient.name, rawText: ingredient.raw_text })}
        >
          <Pencil className="size-4" aria-hidden="true" />
        </IconButton>
      </div>
    </li>
  );
}

/** Every ingredient as read: origin, what our database says it counts as, readability, and its words on the photo. */
interface IngredientsListProps {
  result: ScanResult;
  corrections: Correction[];
  onEdit: (target: EditTarget) => void;
  onExplain: (term: string) => void;
}

export function IngredientsList({ result, corrections, onEdit, onExplain }: IngredientsListProps) {
  const { t } = useTranslation();
  const { ingredients, ingredients_section: section } = result.extraction;
  const annotations = new Map(result.annotations.map((annotation) => [annotation.ingredient_id, annotation]));
  const editedPaths = new Set(corrections.map((correction) => correction.field_path));

  if (section.presence === "not_found" || ingredients.length === 0) {
    return <p className="card p-5 text-sm text-text-dim">{t("ingredients.empty")}</p>;
  }
  return (
    <div className="card px-4 sm:px-5">
      {!section.complete && (
        <p className="hatch -mx-4 border-b border-line px-4 py-3 text-sm text-unknown sm:-mx-5 sm:px-5">{t("ingredients.incomplete")}</p>
      )}
      <ul className="divide-y divide-line">
        {ingredients.map((ingredient, index) => (
          <IngredientRow
            key={ingredient.id}
            ingredient={ingredient}
            path={`ingredients[${index}]`}
            annotations={annotations}
            editedPaths={editedPaths}
            onEdit={onEdit}
            onExplain={onExplain}
          />
        ))}
      </ul>
    </div>
  );
}
