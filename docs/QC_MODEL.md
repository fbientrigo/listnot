# QC_MODEL.md

**Project:** `pucv-aq-qc` — quality-control engine model.
**Audience:** Beatriz (clinical/QC authority) and Fabian (implementation). Messages are written for **Tecnología Médica** users, not programmers.

---

## 1. QC concepts

Internal QC monitors analytical performance by measuring **control materials** of known target values in each run, and checking whether the analyzer is producing results consistent with its validated performance.

- **Control material:** a stabilized sample with an assigned **target mean** and **target SD** per analyte, per **lot**, per **control level** (we use two: **L1** low/normal, **L2** high).
- **Run:** a batch of patient samples bracketed by QC measurements.
- **Systematic error (bias/shift/drift):** the whole series moves off target — miscalibration, reagent/lot change, aging.
- **Random error (imprecision):** scatter increases — pipetting, temperature, instability.

The engine consumes `QCMeasurement` rows and emits `QCFlag` rows with a **run status**.

---

## 2. Levey-Jennings (LJ)

An LJ chart plots each QC value over time against horizontal reference lines at the target **mean** and at **±1SD, ±2SD, ±3SD**.

The engine returns LJ-ready series per (`analyte_code`, `control_level`, `reagent_lot`):

```python
# qc/levey_jennings.py
@dataclass
class LJPoint:
    measured_at: datetime
    value: float
    z: float                    # (value - target_mean) / target_sd
    band: str                   # "in_1sd" | "1_2sd" | "2_3sd" | "beyond_3sd"

def lj_series(measurements: list[QCMeasurement]) -> LJSeries: ...
# LJSeries carries target_mean, target_sd, the ±1/2/3 SD limits, and ordered points.
```

Ordering is by `measured_at`; multi-point rules (2_2s, R_4s, 4_1s, 10x) operate on this ordered series.

---

## 3. z-scores

For each QC measurement:

```
z = (value − target_mean) / target_sd
```

`z` is the number of SDs from target. It is the primary input to every Westgard rule and is stored/derived per point. A `target_sd <= 0` is a data error → the measurement is flagged `info`/invalid, never divided by zero.

---

## 4. CV (coefficient of variation)

Per (`analyte_code`, `control_level`, `reagent_lot`) over a window:

```
mean = Σvalue / n
SD   = sample standard deviation of values          (n-1 denominator, n ≥ 2)
CV%  = 100 · SD / mean
```

```python
# qc/metrics.py
@dataclass
class ControlStats:
    n: int
    mean: float
    sd: float | None            # None when n < 2
    cv_percent: float | None    # None when n < 2 or mean == 0
```

CV% is compared against the analyte's **allowable CV** (owned by Beatriz). Observed CV above the allowable limit indicates the method's imprecision has degraded even if individual points pass Westgard.

---

## 5. Westgard-like rules

Evaluated per control level and across levels within a run. `n` = position in the ordered series.

| Rule | Trigger | Meaning | Default severity |
|---|---|---|---|
| `1_2s` | one point beyond ±2SD | warning tripwire | **warning** |
| `1_3s` | one point beyond ±3SD | large random/systematic error | **reject** |
| `2_2s` | 2 consecutive points beyond same ±2SD (same level over time, or both levels in one run) | systematic error | **reject** |
| `R_4s` | range between two points (typically L1 vs L2 in a run) > 4SD | random error | **reject** |
| `4_1s` | 4 consecutive points beyond same ±1SD | systematic shift | **warning→reject** (configurable) |
| `10x` | 10 consecutive points on the same side of the mean | systematic shift/bias | **warning** |

```python
# qc/westgard.py
@dataclass
class RuleHit:
    rule_code: str
    severity: str               # "info" | "warning" | "reject"
    involved_point_ids: list[str]
    message: str                # Spanish, TM-readable

def evaluate(series: LJSeries, config: WestgardConfig) -> list[RuleHit]: ...
```

`1_2s` is used as a **warning/screen**: on its own it is a heads-up, not a rejection (classic Westgard multirule). `4_1s` severity is configurable because institutions differ; default is `warning`, escalate to `reject` via `WestgardConfig`.

---

## 6. Run status logic

A run's status is the **most severe** outcome across all rules evaluated for that run:

```
if any hit.severity == "reject":   run_status = "rejected"
elif any hit.severity == "warning": run_status = "warning"
else:                               run_status = "accepted"
```

| run_status | Action for the TM user |
|---|---|
| `accepted` | Release patient results for the run. |
| `warning` | Inspect; results releasable with caution; watch for a developing trend. |
| `rejected` | **Do not release.** Identify cause, correct, re-run QC before releasing. |

Every `RuleHit` becomes a `QCFlag` row carrying `rule_code`, `severity`, `run_status`, and a `message`.

---

## 7. Example messages for Tecnología Médica users

Messages are Spanish, name the analyte/level/lot, state the rule in plain terms, and give a next step. **They never contain patient identifiers.**

| Situation | Message |
|---|---|
| `1_2s` L1 glicemia | ⚠️ *Advertencia (1₂ₛ): el control Nivel 1 de Glicemia (lote L23A) se ubicó a más de 2 DE del valor objetivo. Punto de alerta: revise la tendencia; aún no requiere rechazo.* |
| `1_3s` L2 colesterol | ⛔ *Rechazo (1₃ₛ): el control Nivel 2 de Colesterol total (lote C11B) superó ±3 DE. Corrida rechazada: no libere resultados. Verifique calibración y reactivo.* |
| `2_2s` creatinina | ⛔ *Rechazo (2₂ₛ): dos controles consecutivos de Creatinina cayeron sobre +2 DE del mismo lado. Indica error sistemático (sesgo). Revise calibración/lote antes de re-medir.* |
| `R_4s` AST | ⛔ *Rechazo (R₄ₛ): la diferencia entre Nivel 1 y Nivel 2 de AST superó 4 DE en la misma corrida. Sugiere error aleatorio (imprecisión). Repita QC.* |
| `4_1s` albúmina | ⚠️ *Advertencia (4₁ₛ): 4 controles seguidos de Albúmina quedaron sobre +1 DE. Desplazamiento sistemático incipiente; programe verificación de calibración.* |
| `10x` urea | ⚠️ *Advertencia (10ₓ): 10 controles consecutivos de Urea cayeron al mismo lado de la media. Sesgo sostenido; evalúe recalibración.* |
| CV alto | ⚠️ *La imprecisión (CV%) de {analito} Nivel {L} superó el límite permitido ({cv_obs}% > {cv_max}%). Revise condiciones pre-analíticas y del equipo.* |
| Corrida aceptada | ✅ *Corrida aceptada: todos los controles de {analito} dentro de límites. Puede liberar resultados.* |

Message strings live in `qc/summary.py` / `qc/westgard.py` as templates so Beatriz can review and edit wording without touching rule logic.
