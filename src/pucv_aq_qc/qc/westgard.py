"""Westgard-like multirule evaluation (docs/QC_MODEL.md §5).

Rules operate on an ordered LJSeries. Messages are TM-readable Spanish
templates (docs/QC_MODEL.md §7) kept here so Beatriz can edit wording without
touching rule logic. No message contains a patient identifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pucv_aq_qc.qc.levey_jennings import LJPoint, LJSeries
from pucv_aq_qc.schemas.enums import Severity

# --- Spanish message templates (editable by Beatriz) ------------------------

_ANALYTE_ES = {
    "glucose": "Glicemia",
    "chol_total": "Colesterol total",
    "triglycerides": "Triglicéridos",
    "creatinine": "Creatinina",
    "urea": "Urea",
    "alt": "ALT/GPT",
    "ast": "AST/GOT",
    "albumin": "Albúmina",
}

MESSAGE_TEMPLATES: dict[str, str] = {
    "1_2s": (
        "⚠️ Advertencia (1₂ₛ): el control Nivel {level} de {analyte} (lote {lot}) se ubicó "
        "a más de 2 DE del valor objetivo. Punto de alerta: revise la tendencia; aún no "
        "requiere rechazo."
    ),
    "1_3s": (
        "⛔ Rechazo (1₃ₛ): el control Nivel {level} de {analyte} (lote {lot}) superó ±3 DE. "
        "Corrida rechazada: no libere resultados. Verifique calibración y reactivo."
    ),
    "2_2s": (
        "⛔ Rechazo (2₂ₛ): dos controles consecutivos de {analyte} (Nivel {level}) cayeron "
        "sobre ±2 DE del mismo lado. Indica error sistemático (sesgo). Revise "
        "calibración/lote antes de re-medir."
    ),
    "R_4s": (
        "⛔ Rechazo (R₄ₛ): la diferencia entre dos controles consecutivos de {analyte} "
        "(Nivel {level}) superó 4 DE. Sugiere error aleatorio (imprecisión). Repita QC."
    ),
    "4_1s": (
        "⚠️ Advertencia (4₁ₛ): 4 controles seguidos de {analyte} (Nivel {level}) quedaron "
        "sobre ±1 DE del mismo lado. Desplazamiento sistemático incipiente; programe "
        "verificación de calibración."
    ),
    "10x": (
        "⚠️ Advertencia (10ₓ): 10 controles consecutivos de {analyte} (Nivel {level}) "
        "cayeron al mismo lado de la media. Sesgo sostenido; evalúe recalibración."
    ),
}


def render_message(rule_code: str, analyte_code: str, level: str, lot: str | None) -> str:
    analyte = _ANALYTE_ES.get(analyte_code, analyte_code)
    return MESSAGE_TEMPLATES[rule_code].format(
        analyte=analyte, level=level, lot=lot or "s/l"
    )


# --- Config -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WestgardConfig:
    """Rule severities. ``4_1s`` is configurable (default warning), per §5."""

    severity_4_1s: Severity = Severity.warning
    enabled: frozenset[str] = frozenset(
        {"1_2s", "1_3s", "2_2s", "R_4s", "4_1s", "10x"}
    )


DEFAULT_CONFIG = WestgardConfig()


# --- Rule hit ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuleHit:
    rule_code: str
    severity: str
    involved_point_ids: list[str] = field(default_factory=list)
    message: str = ""


# --- Evaluation -------------------------------------------------------------


def _valid_points(series: LJSeries) -> list[LJPoint]:
    return [p for p in series.points if p.valid and p.z is not None]


def _sign(z: float) -> int:
    if z > 0:
        return 1
    if z < 0:
        return -1
    return 0


def evaluate(series: LJSeries, config: WestgardConfig = DEFAULT_CONFIG) -> list[RuleHit]:
    """Evaluate all enabled Westgard rules over one control series."""
    pts = _valid_points(series)
    hits: list[RuleHit] = []

    def msg(rule: str) -> str:
        return render_message(rule, series.analyte_code, series.control_level, series.reagent_lot)

    # 1_3s and 1_2s: per-point tripwires.
    for p in pts:
        az = abs(p.z)
        if "1_3s" in config.enabled and az > 3:
            hits.append(RuleHit("1_3s", Severity.reject, [p.point_id], msg("1_3s")))
        if "1_2s" in config.enabled and az > 2:
            hits.append(RuleHit("1_2s", Severity.warning, [p.point_id], msg("1_2s")))

    # 2_2s: two consecutive points beyond same ±2SD (non-overlapping).
    if "2_2s" in config.enabled:
        i = 0
        while i < len(pts) - 1:
            a, b = pts[i], pts[i + 1]
            if abs(a.z) > 2 and abs(b.z) > 2 and _sign(a.z) == _sign(b.z) != 0:
                hits.append(
                    RuleHit("2_2s", Severity.reject, [a.point_id, b.point_id], msg("2_2s"))
                )
                i += 2
            else:
                i += 1

    # R_4s: range between two consecutive points > 4SD (non-overlapping).
    if "R_4s" in config.enabled:
        i = 0
        while i < len(pts) - 1:
            a, b = pts[i], pts[i + 1]
            if abs(a.z - b.z) > 4:
                hits.append(
                    RuleHit("R_4s", Severity.reject, [a.point_id, b.point_id], msg("R_4s"))
                )
                i += 2
            else:
                i += 1

    # 4_1s: 4 consecutive points beyond same ±1SD (non-overlapping).
    if "4_1s" in config.enabled:
        hits.extend(
            _run_rule(pts, window=4, threshold=1.0, rule="4_1s", severity=config.severity_4_1s, msg=msg("4_1s"))
        )

    # 10x: 10 consecutive points on the same side of the mean (non-overlapping).
    if "10x" in config.enabled:
        hits.extend(
            _run_rule(pts, window=10, threshold=0.0, rule="10x", severity=Severity.warning, msg=msg("10x"))
        )

    return hits


def _run_rule(
    pts: list[LJPoint], *, window: int, threshold: float, rule: str, severity: Severity, msg: str
) -> list[RuleHit]:
    """Emit a hit when ``window`` consecutive points share a side and exceed
    ``threshold`` SD (threshold 0 = simply same side). Non-overlapping."""
    out: list[RuleHit] = []
    i = 0
    while i <= len(pts) - window:
        block = pts[i : i + window]
        sign = _sign(block[0].z)
        if sign != 0 and all(
            _sign(p.z) == sign and abs(p.z) > threshold for p in block
        ):
            out.append(RuleHit(rule, severity, [p.point_id for p in block], msg))
            i += window
        else:
            i += 1
    return out
