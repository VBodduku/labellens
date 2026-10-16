import type {
  AskResponse,
  ExplainResponse,
  HealthResponse,
  Profile,
  ProfileParseResponse,
  RestrictionCatalogItem,
  ScanResult,
} from "../shared/contract";
import askJson from "../shared/fixtures/ask_response.json";
import catalogJson from "../shared/fixtures/catalog.json";
import explainJson from "../shared/fixtures/explain.json";
import healthJson from "../shared/fixtures/health.json";
import profileParseJson from "../shared/fixtures/profile_parse.json";
import profilesJson from "../shared/fixtures/profiles.json";
import sampleLabelUrl from "../shared/fixtures/sample_label.svg?url";
import scanResultJson from "../shared/fixtures/scan_result.json";

/*
 * Typed views of shared/fixtures (generated from the Pydantic contract by build_fixtures.py, so the
 * shapes match). JSON imports widen string unions to `string`, hence the casts in this one place.
 */
export const fixtureScanResult = scanResultJson as unknown as ScanResult;
export const fixtureProfiles = profilesJson as unknown as Profile[];
export const fixtureCatalog = catalogJson as unknown as RestrictionCatalogItem[];
export const fixtureAsk = askJson as unknown as AskResponse;
export const fixtureExplain = explainJson as unknown as ExplainResponse;
export const fixtureHealth = healthJson as unknown as HealthResponse;
export const fixtureProfileParse = profileParseJson as unknown as ProfileParseResponse;
export { sampleLabelUrl };
