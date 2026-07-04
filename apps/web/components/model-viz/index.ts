/**
 * Frontend registry for the staged model animations — mirrors the backend package
 * `laboratree/labs/modeling/viz` (same family names).
 *
 * Plug IN a family: add `<family>.tsx` exporting `Train` and `Test` stage components and list it
 * here. Plug OUT: remove the entry (requests fall back to the trees view). Nothing else changes —
 * StagedModelAnimation is a thin host that looks the family up by name.
 */

import type { ComponentType } from "react";
import type { TestProps, TrainProps } from "./shared";
import * as anomaly from "./anomaly";
import * as clustering from "./clustering";
import * as knn from "./knn";
import * as linear from "./linear";
import * as nn from "./nn";
import * as timeseries from "./timeseries";
import * as trees from "./trees";

export type FamilyStages = {
  Train: ComponentType<TrainProps>;
  Test: ComponentType<TestProps>;
};

const FAMILIES: Record<string, FamilyStages> = {
  trees,
  linear,
  nn,
  knn,
  timeseries,
  clustering,
  anomaly,
};

export function stagesFor(family: string): FamilyStages {
  return FAMILIES[family] ?? FAMILIES.trees;
}

export { DataStage, ResultBadge, RowValues } from "./shared";
