# Phase 3 validation results

Seeds: `[101, 102, 103, 104, 105]`; payments per seed: `5000`.
All metrics below are measured outputs from cross-seed held-out evaluation.

## Synthetic artifact found and fixed

Ring-controlled merchants lacked ordinary customer history, making low causal merchant degree an unrealistically strong proxy for fraud.

Reallocated 4% of the existing payment budget to ordinary customers at ring merchants, mostly before attack activation; total transaction count is unchanged.

## Before/after benchmark impact

| Model | Before PR-AUC | After PR-AUC | Before F1 | After F1 |
|---|---:|---:|---:|---:|
| graph_heuristic | 0.316 | 0.321 | 0.311 | 0.307 |
| network_aware_hgb | 0.979 | 0.971 | 0.949 | 0.951 |
| rules | 0.055 | 0.056 | 0.079 | 0.080 |
| transaction_hgb | 0.196 | 0.199 | 0.236 | 0.243 |

## Feature ablations

| Feature set | Precision | Recall | F1 | PR-AUC | FPR | Ring detection | Hard-negative FP |
|---|---:|---:|---:|---:|---:|---:|---:|
| full_minus_infrastructure | 0.978 +/- 0.011 | 0.831 +/- 0.010 | 0.898 +/- 0.004 | 0.924 +/- 0.008 | 0.001 +/- 0.000 | 1.000 +/- 0.000 | 0.000 +/- 0.000 |
| full_minus_structural | 0.868 +/- 0.009 | 0.940 +/- 0.010 | 0.903 +/- 0.007 | 0.936 +/- 0.005 | 0.007 +/- 0.001 | 1.000 +/- 0.000 | 0.000 +/- 0.000 |
| full_minus_temporal | 0.948 +/- 0.015 | 0.912 +/- 0.024 | 0.929 +/- 0.011 | 0.954 +/- 0.011 | 0.002 +/- 0.001 | 0.980 +/- 0.040 | 0.033 +/- 0.067 |
| full_minus_transaction | 0.976 +/- 0.007 | 0.944 +/- 0.007 | 0.960 +/- 0.006 | 0.972 +/- 0.005 | 0.001 +/- 0.000 | 1.000 +/- 0.000 | 0.000 +/- 0.000 |
| full_network_aware | 0.964 +/- 0.007 | 0.939 +/- 0.011 | 0.951 +/- 0.006 | 0.971 +/- 0.005 | 0.002 +/- 0.000 | 1.000 +/- 0.000 | 0.000 +/- 0.000 |
| transaction_only | 0.627 +/- 0.176 | 0.154 +/- 0.009 | 0.243 +/- 0.005 | 0.199 +/- 0.011 | 0.005 +/- 0.004 | 0.300 +/- 0.000 | 0.000 +/- 0.000 |
| transaction_plus_infrastructure | 0.855 +/- 0.019 | 0.817 +/- 0.035 | 0.835 +/- 0.022 | 0.877 +/- 0.016 | 0.007 +/- 0.001 | 0.880 +/- 0.075 | 0.000 +/- 0.000 |
| transaction_plus_structural | 0.937 +/- 0.015 | 0.745 +/- 0.021 | 0.830 +/- 0.010 | 0.879 +/- 0.011 | 0.002 +/- 0.001 | 0.900 +/- 0.063 | 0.100 +/- 0.082 |
| transaction_plus_temporal | 0.915 +/- 0.014 | 0.570 +/- 0.008 | 0.702 +/- 0.005 | 0.629 +/- 0.007 | 0.003 +/- 0.000 | 0.700 +/- 0.000 | 0.067 +/- 0.082 |

## Permutation importance

| Feature | Held-out PR-AUC decrease |
|---|---:|
| merchant_customer_degree | 0.6080 +/- 0.0333 |
| shared_infrastructure_concentration | 0.3864 +/- 0.1271 |
| payout_merchants | 0.1565 +/- 0.0107 |
| shared_device_customers | 0.0254 +/- 0.0379 |
| merchant_refund_ratio_24h | 0.0151 +/- 0.0107 |
| shared_ip_customers | 0.0141 +/- 0.0071 |
| customer_merchant_degree | 0.0140 +/- 0.0063 |
| device_events_15m | 0.0131 +/- 0.0157 |
| customer_merchant_concentration | 0.0069 +/- 0.0031 |
| merchant_events_15m | 0.0042 +/- 0.0018 |

## Strongest-feature distributions

| Feature | Fraud median (p10-p90) | Benign median (p10-p90) | Univariate separation AUC |
|---|---:|---:|---:|
| merchant_customer_degree | 24.000 (9.000-31.000) | 54.000 (10.000-102.000) | 0.793 |
| shared_infrastructure_concentration | 0.500 (0.250-0.727) | 0.250 (0.250-0.250) | 0.828 |
| payout_merchants | 1.000 (1.000-3.000) | 1.000 (1.000-1.000) | 0.605 |
| shared_device_customers | 4.000 (1.000-12.000) | 1.000 (1.000-1.000) | 0.814 |
| merchant_refund_ratio_24h | 0.000 (0.000-0.000) | 0.000 (0.000-0.000) | 0.512 |
| shared_ip_customers | 1.000 (1.000-2.100) | 1.000 (1.000-1.000) | 0.535 |
| customer_merchant_degree | 1.000 (1.000-1.000) | 1.000 (1.000-3.000) | 0.693 |
| device_events_15m | 1.000 (1.000-4.000) | 1.000 (1.000-1.000) | 0.604 |
| customer_merchant_concentration | 1.000 (1.000-1.000) | 1.000 (0.333-1.000) | 0.697 |
| merchant_events_15m | 1.000 (1.000-4.000) | 1.000 (1.000-1.000) | 0.618 |

## Leave-one-archetype-out generalization

| Held-out archetype | PR-AUC | Recall | Ring detection |
|---|---:|---:|---:|
| slow_burn | 0.880 +/- 0.008 | 0.880 +/- 0.000 | 1.000 +/- 0.000 |
| adversarial_camouflage | 0.940 +/- 0.010 | 0.938 +/- 0.000 | 1.000 +/- 0.000 |
| fragmented | 0.921 +/- 0.050 | 1.000 +/- 0.000 | 1.000 +/- 0.000 |
| merchant_collusion | 0.803 +/- 0.143 | 1.000 +/- 0.000 | 1.000 +/- 0.000 |
| device_sharing | 0.971 +/- 0.007 | 0.960 +/- 0.000 | 1.000 +/- 0.000 |

## Exposure estimation

At-risk value counted once per original payment; abusive refund value replaces, rather than adds to, the purchase value.

Detection recall: `1.000`.

| Scope | Rings | MAE minor | Median AE minor | Mean relative error | Estimated / actual minor |
|---|---:|---:|---:|---:|---:|
| Matched rings | 50 | 821487.0 | 454250.0 | 0.081 | 461382462 / 482834643 |
| End-to-end | 50 | 821487.0 | 454250.0 | 0.081 | 461382462 / 482834643 |

Detection recall and exposure error are separate: a detected ring can still have under- or over-estimated exposure.

## Updated benchmark after hardening

| Model | Precision | Recall | F1 | PR-AUC | FPR | Ring detection |
|---|---:|---:|---:|---:|---:|---:|
| graph_heuristic | 0.331 +/- 0.016 | 0.287 +/- 0.000 | 0.307 +/- 0.007 | 0.321 +/- 0.014 | 0.027 +/- 0.002 | 0.280 +/- 0.098 |
| network_aware_hgb | 0.964 +/- 0.007 | 0.939 +/- 0.011 | 0.951 +/- 0.006 | 0.971 +/- 0.005 | 0.002 +/- 0.000 | 1.000 +/- 0.000 |
| rules | 0.126 +/- 0.004 | 0.058 +/- 0.003 | 0.080 +/- 0.004 | 0.056 +/- 0.002 | 0.019 +/- 0.000 | 0.100 +/- 0.000 |
| transaction_hgb | 0.627 +/- 0.176 | 0.154 +/- 0.009 | 0.243 +/- 0.005 | 0.199 +/- 0.011 | 0.005 +/- 0.004 | 0.300 +/- 0.000 |

## Streaming demo contract

Seed `105` replays `5104` events. The first threshold crossing is `2026-01-02 17:32:56+00:00` and the first candidate appears at `2026-01-03 14:14:16+00:00`. There are `312` normal replay steps before the first model alert.

That first threshold crossing is an isolated pre-attack alert and does not form a candidate. In the explicitly ground-truth-only evaluation overlay, `obvious_coordinated` begins at `2026-01-03 14:06:16+00:00` and its matched candidate appears at `2026-01-03 14:14:16+00:00`—`8.0` minutes later.

The evidence service and replay simulator use only event/graph/model outputs. Fraud ground truth is reserved for offline evaluation.

## Interpretation

Generalization claims should be limited to archetypes whose held-out results support them. The benchmark remains synthetic; expected-loss rates are synthetic assumptions and model probabilities are not calibrated.
