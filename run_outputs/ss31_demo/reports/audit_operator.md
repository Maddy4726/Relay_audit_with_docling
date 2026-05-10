# Relay Audit Summary

**Overall status:** REVIEW

_Renderer v1 (deterministic)._

## Operator remarks

The document audit completed with overall status **REVIEW**. Sections: 15 PASS, 0 WARN, 0 FAIL, 10 REVIEW (by section-level rollup). Extraction or typed-output quality requires human verification on flagged sections.

## Summary

- **PASS sections:** 15
- **WARN sections:** 0
- **FAIL sections:** 0
- **REVIEW sections:** 10

## Confidence

- **Document confidence:** 0.638 (0–1 scale; mean of section confidences).
- **Low extraction confidence (sections):**
  - `circuit-breaker` — CIRCUIT BREAKER (conf=0.000, generic_tables, section_confidence_below_threshold)
  - `name-plate-details` — NAME PLATE DETAILS (conf=0.000, generic_tables, section_confidence_below_threshold)
  - `insulation-resistance-test-measured-values-in-g` — INSULATION RESISTANCE TEST : (MEASURED VALUES IN GΩ) (conf=0.000, generic_tables, section_confidence_below_threshold)
  - `coil-resistance-test` — COIL RESISTANCE TEST (conf=0.000, generic_tables, section_confidence_below_threshold)
  - `current-transformer` — CURRENT TRANSFORMER (conf=0.000, generic_tables, section_confidence_below_threshold)
  - `ratio-test-by-primary-injection` — RATIO TEST: (BY PRIMARY INJECTION) (conf=0.000, ct_ratio, section_confidence_below_threshold)
  - `shailja-enterprises` — SHAILJA ENTERPRISES (conf=0.000, generic_tables, section_confidence_below_threshold)
  - `test-report-for-motor-feeder` — TEST REPORT FOR MOTOR FEEDER (conf=0.000, generic_tables, section_confidence_below_threshold)
  - `bhilai-steel-plant-bhilai-chhattisgarh` — BHILAI STEEL PLANT ,BHILAI (CHHATTISGARH) (conf=0.000, generic_tables, section_confidence_below_threshold)

## Section status

| # | Section | Status | Conf | Extractor |
|---|---------|--------|------|-------------|
| 0 | PREAMBLE | **PASS** | 1.000 | `preamble` |
| 1 | GENERAL | **PASS** | 1.000 | `generic_tables` |
| 2 | CIRCUIT BREAKER | **REVIEW** | 0.000 | `generic_tables` |
| 3 | NAME PLATE DETAILS | **REVIEW** | 0.000 | `generic_tables` |
| 4 | INSULATION RESISTANCE TEST : (MEASURED VALUES IN GΩ) | **REVIEW** | 0.000 | `generic_tables` |
| 5 | COIL RESISTANCE TEST | **REVIEW** | 0.000 | `generic_tables` |
| 6 | CONTACT RESISTANCE TEST | **PASS** | 1.000 | `contact_resistance` |
| 7 | TIME INTERVAL TEST | **PASS** | 1.000 | `generic_tables` |
| 8 | CURRENT TRANSFORMER | **REVIEW** | 0.000 | `generic_tables` |
| 9 | RATIO TEST: (BY PRIMARY INJECTION) | **REVIEW** | 0.000 | `ct_ratio` |
| 10 | 3.1 CT (CTR: 150 / 5 A) | **PASS** | 0.960 | `ct_ratio` |
| 11 | CBCT (RATIO: 50 / 1 A) | **REVIEW** | 1.000 | `ct_ratio` |
| 12 | RELAY TESTING | **PASS** | 1.000 | `generic_tables` |
| 13 | PROTECTION TESTING ( BY SECONDARY INJECTION) 4.1 MEASUREMENTS | **PASS** | 1.000 | `generic_tables` |
| 14 | SHORT CIRCUIT: (DTOC) | **PASS** | 1.000 | `generic_tables` |
| 15 | THERMAL O/L | **PASS** | 1.000 | `generic_tables` |
| 16 | NEGATIVE SEQUENCE:(DTOC) | **PASS** | 1.000 | `generic_tables` |
| 17 | PROLONGED START/ STARTUP SUPERVISION: MP | **PASS** | 1.000 | `generic_tables` |
| 18 | STALL DURING RUNNING: (DTOC) | **PASS** | 1.000 | `generic_tables` |
| 19 | SHAILJA ENTERPRISES | **REVIEW** | 0.000 | `generic_tables` |
| 20 | TEST REPORT FOR MOTOR FEEDER | **REVIEW** | 0.000 | `generic_tables` |
| 21 | BHILAI STEEL PLANT ,BHILAI (CHHATTISGARH) | **REVIEW** | 0.000 | `generic_tables` |
| 22 | 4.7 EARTH FAULT PROTECTION (E/F): OPERATED THROUGH CBCT | **PASS** | 1.000 | `generic_tables` |
| 23 | 5.0 FINAL CHECKS | **PASS** | 1.000 | `generic_tables` |
| 24 | 6.0 REMARKS: 1) | **PASS** | 1.000 | `generic_tables` |

## Key findings

(Ordered **FAIL → WARN → REVIEW**, then document order.)

### 1. RATIO TEST: (BY PRIMARY INJECTION)

*Section slug:* `ratio-test-by-primary-injection`

- **REVIEW** (typed_payload_review): Typed extractor quality flags require human review.
  - Evidence: flags: ct_ratio_empty_measurements, ct_ratio_low_typed_confidence
  - Source line: 58

### 2. CBCT (RATIO: 50 / 1 A)

*Section slug:* `cbct-ratio-50-1-a`

- **REVIEW** (typed_payload_review): Typed extractor quality flags require human review.
  - Evidence: flags: ct_ratio_empty_measurements, ct_ratio_low_typed_confidence
  - Source line: 78

### 3. CIRCUIT BREAKER

*Section slug:* `circuit-breaker`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 12

### 4. NAME PLATE DETAILS

*Section slug:* `name-plate-details`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 14

### 5. INSULATION RESISTANCE TEST : (MEASURED VALUES IN GΩ)

*Section slug:* `insulation-resistance-test-measured-values-in-g`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 15

### 6. COIL RESISTANCE TEST

*Section slug:* `coil-resistance-test`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 16

### 7. CURRENT TRANSFORMER

*Section slug:* `current-transformer`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 56

### 8. SHAILJA ENTERPRISES

*Section slug:* `shailja-enterprises`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 151

### 9. TEST REPORT FOR MOTOR FEEDER

*Section slug:* `test-report-for-motor-feeder`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 153

### 10. BHILAI STEEL PLANT ,BHILAI (CHHATTISGARH)

*Section slug:* `bhilai-steel-plant-bhilai-chhattisgarh`

- **REVIEW** (low_section_confidence): Section confidence 0.000 is below threshold 0.72.
  - Evidence: confidence=0.0 threshold=0.72
  - Source line: 155

## Review recommendations

- Manually verify 10 section(s) marked REVIEW (low extraction confidence and/or typed extractor flags).
