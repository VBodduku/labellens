import type {
  AskRequest,
  AskResponse,
  ExplainRequest,
  ExplainResponse,
  HealthResponse,
  Lang,
  PanelHint,
  Profile,
  ProfileParseRequest,
  ProfileParseResponse,
  RecheckRequest,
  RestrictionCatalogItem,
  ScanResult,
} from "../shared/contract";

export interface ScanInput {
  /** Panel images in upload order; the backend names them img_0..img_2. */
  images: Blob[];
  profiles: Profile[];
  lang: Lang;
  panelHints?: PanelHint[];
}

export interface CallOptions {
  signal?: AbortSignal;
}

/** The single API surface the app talks to; implemented by the real client and the fixture mock. */
export interface LabelLensApi {
  health(options?: CallOptions): Promise<HealthResponse>;
  catalog(options?: CallOptions): Promise<RestrictionCatalogItem[]>;
  scan(input: ScanInput, options?: CallOptions): Promise<ScanResult>;
  recheck(request: RecheckRequest, options?: CallOptions): Promise<ScanResult>;
  ask(request: AskRequest, options?: CallOptions): Promise<AskResponse>;
  parseProfile(request: ProfileParseRequest, options?: CallOptions): Promise<ProfileParseResponse>;
  explain(request: ExplainRequest, options?: CallOptions): Promise<ExplainResponse>;
}
