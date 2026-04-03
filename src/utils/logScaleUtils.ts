/**
 * Minimum value threshold for log scale plotting.
 * Values below this will be clipped to avoid extreme negative log values.
 */
export const LOG_SCALE_MIN_VALUE = 1e-10;

/**
 * Clips a value to a minimum threshold for safe log scale plotting.
 * Prevents values like 0 or near-zero from causing extreme drops on log scale.
 */
export function clipForLogScale(value: number, minValue: number = LOG_SCALE_MIN_VALUE): number {
  if (value <= 0 || !isFinite(value)) {
    return minValue;
  }
  return Math.max(value, minValue);
}

/**
 * Clips an array of values for log scale plotting.
 * Optionally filters out zero/negative values instead of clipping.
 */
export function clipArrayForLogScale(
  values: number[],
  minValue: number = LOG_SCALE_MIN_VALUE,
  filterInsteadOfClip: boolean = false
): number[] {
  if (filterInsteadOfClip) {
    return values.filter(v => v > 0 && isFinite(v)).map(v => Math.max(v, minValue));
  }
  return values.map(v => clipForLogScale(v, minValue));
}

/**
 * Processes data points with x,y coordinates for log scale Y-axis.
 * Returns points with Y values clipped to minimum threshold.
 */
export function clipDataPointsForLogScale<T extends { x: number; y: number }>(
  points: T[],
  minValue: number = LOG_SCALE_MIN_VALUE,
  filterZeros: boolean = false
): T[] {
  if (filterZeros) {
    return points.filter(p => p.y > 0 && isFinite(p.y));
  }
  return points.map(p => ({
    ...p,
    y: clipForLogScale(p.y, minValue)
  }));
}
