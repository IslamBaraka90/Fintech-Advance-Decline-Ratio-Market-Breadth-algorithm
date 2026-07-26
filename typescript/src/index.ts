/**
 * Fintech Advance/Decline Ratio — point-in-time market-breadth ratio.
 *
 * Companion article (canonical): https://thefintechbuilder.com/market-breadth-and-internals/advance-decline-breadth/advance-decline-ratio/
 * Catalog topic id: D04-F01-A02 (Domain D04 — Market Breadth and Internals / Family D04-F01 — Advance-Decline Breadth)
 */

export {
  BreadthValidationError,
  calculateAdvanceDeclineRatio,
  evaluateAdvanceDeclineRatioAsOf,
  type BreadthResult,
  type BreadthSnapshot,
  type BreadthQuery,
} from "./advanceDeclineRatio.ts";
export {
  logAdRatio,
  percentAdvancing,
  strengthKey,
  compareStrength,
  type Strength,
} from "./analysis.ts";
