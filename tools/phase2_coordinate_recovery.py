from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"expected source fragment not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_block(path: Path, start: str, end: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    start_index = text.find(start)
    if start_index < 0:
        if replacement in text:
            return
        raise RuntimeError(f"block start not found in {path}: {start}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"block end not found in {path}: {end}")
    path.write_text(text[:start_index] + replacement + text[end_index:], encoding="utf-8")


def recover_config_model() -> None:
    path = ROOT / "src/trajcert/config.py"
    replace_once(
        path,
        "from contextvars import ContextVar\nfrom itertools import pairwise\n",
        "from contextvars import ContextVar\nfrom enum import StrEnum\nfrom itertools import pairwise\n",
    )
    replace_once(
        path,
        'active_config: ContextVar[TrajCertConfig] = ContextVar("active_config")\n',
        '_UTILITY_AND_COHERENCE_LAW_COUNT = 6\n'
        '_SHARPNESS_ORACLE_LAW_COUNT = 10\n'
        '_SAFETY_AND_IMPOSSIBILITY_LAW_COUNT = 8\n'
        '_STRICT_TIMING_CASE_COUNT = 6\n'
        '_COVERAGE_STRESS_CASE_COUNT = 12\n'
        '_FAILURE_BOUNDARY_LEVEL_COUNT = 7\n\n'
        'active_config: ContextVar[TrajCertConfig] = ContextVar("active_config")\n',
    )
    replace_once(
        path,
        "class LawConfig(ConfigModel):\n"
        "    theta: UnitFloat\n"
        "    q1: UnitFloat\n"
        "    q0: UnitFloat\n"
        "    lambda1: StrictFloat\n"
        "    lambda0: StrictFloat\n\n\n",
        "class LawConfig(ConfigModel):\n"
        "    theta: UnitFloat\n"
        "    q1: UnitFloat\n"
        "    q0: UnitFloat\n"
        "    lambda1: StrictFloat\n"
        "    lambda0: StrictFloat\n\n\n"
        "class TimingInformationExpectation(StrEnum):\n"
        '    ZERO = "ZERO"\n'
        '    POSITIVE = "POSITIVE"\n\n\n'
        "class StrictTimingCaseConfig(ConfigModel):\n"
        "    law: LawKey\n"
        "    fine_bands: PositiveInt\n"
        "    coarse_bands: PositiveInt\n"
        "    expectation: TimingInformationExpectation\n\n"
        "    @model_validator(mode=\"after\")\n"
        "    def validate_refinement(self) -> StrictTimingCaseConfig:\n"
        "        if self.fine_bands <= self.coarse_bands:\n"
        '            raise ValueError("strict timing fine partition must refine the coarse partition")\n'
        "        if self.fine_bands % self.coarse_bands != 0:\n"
        '            raise ValueError("strict timing partitions must be deterministic nested coarsenings")\n'
        "        return self\n\n\n"
        "class LegacyPartitionIncoherenceConfig(ConfigModel):\n"
        "    gamma: tuple[Annotated[StrictFloat, Field(ge=1.0)], ...]\n"
        "    q: tuple[Annotated[StrictFloat, Field(gt=0.0, lt=1.0)], ...]\n"
        "    latent_outcome_probabilities: tuple[UnitFloat, UnitFloat]\n\n"
        "    @model_validator(mode=\"after\")\n"
        "    def validate_grid(self) -> LegacyPartitionIncoherenceConfig:\n"
        '        _require_unique(self.gamma, "study_design.legacy_partition_incoherence.gamma")\n'
        '        _require_unique(self.q, "study_design.legacy_partition_incoherence.q")\n'
        '        _require_strictly_increasing(self.gamma, "study_design.legacy_partition_incoherence.gamma")\n'
        '        _require_strictly_increasing(self.q, "study_design.legacy_partition_incoherence.q")\n'
        "        if sum(self.latent_outcome_probabilities) != 1.0:\n"
        '            raise ValueError("legacy latent outcome probabilities must sum exactly to one")\n'
        "        if any(value <= 0.0 for value in self.latent_outcome_probabilities):\n"
        '            raise ValueError("legacy latent outcome probabilities must be positive")\n'
        "        return self\n\n\n"
        "class CoverageStressSensitivityReference(StrEnum):\n"
        '    TRUE_INFORMATION = "TRUE_INFORMATION"\n'
        '    COMPATIBILITY_FLOOR = "COMPATIBILITY_FLOOR"\n\n\n'
        "class CoverageStressCaseConfig(ConfigModel):\n"
        "    name: str\n"
        "    law: LawKey\n"
        "    band_count: PositiveInt\n"
        "    rho_offset: NonNegativeFloat\n"
        "    sensitivity_reference: CoverageStressSensitivityReference\n"
        "    beta_offset: NonNegativeFloat | None = None\n"
        "    minimum_information_completion: bool = False\n\n"
        "    @model_validator(mode=\"after\")\n"
        "    def validate_reference(self) -> CoverageStressCaseConfig:\n"
        "        requires_completion = (\n"
        "            self.sensitivity_reference\n"
        "            is CoverageStressSensitivityReference.COMPATIBILITY_FLOOR\n"
        "        )\n"
        "        if requires_completion != self.minimum_information_completion:\n"
        "            raise ValueError(\n"
        '                "compatibility-floor stress must be the declared minimum-information completion"\n'
        "            )\n"
        "        return self\n\n\n"
        "class StudyDesignConfig(ConfigModel):\n"
        "    utility_and_coherence_laws: tuple[LawKey, ...]\n"
        "    sharpness_oracle_laws: tuple[LawKey, ...]\n"
        "    safety_and_impossibility_laws: tuple[LawKey, ...]\n"
        "    strict_timing_cases: tuple[StrictTimingCaseConfig, ...]\n"
        "    legacy_partition_incoherence: LegacyPartitionIncoherenceConfig\n"
        "    coverage_stress_cases: tuple[CoverageStressCaseConfig, ...]\n\n"
        "    @model_validator(mode=\"after\")\n"
        "    def validate_registry_cardinalities(self) -> StudyDesignConfig:\n"
        "        expected_lengths = (\n"
        "            (\n"
        "                len(self.utility_and_coherence_laws),\n"
        "                _UTILITY_AND_COHERENCE_LAW_COUNT,\n"
        '                "utility_and_coherence_laws",\n'
        "            ),\n"
        "            (\n"
        "                len(self.sharpness_oracle_laws),\n"
        "                _SHARPNESS_ORACLE_LAW_COUNT,\n"
        '                "sharpness_oracle_laws",\n'
        "            ),\n"
        "            (\n"
        "                len(self.safety_and_impossibility_laws),\n"
        "                _SAFETY_AND_IMPOSSIBILITY_LAW_COUNT,\n"
        '                "safety_and_impossibility_laws",\n'
        "            ),\n"
        "            (\n"
        "                len(self.strict_timing_cases),\n"
        "                _STRICT_TIMING_CASE_COUNT,\n"
        '                "strict_timing_cases",\n'
        "            ),\n"
        "            (\n"
        "                len(self.coverage_stress_cases),\n"
        "                _COVERAGE_STRESS_CASE_COUNT,\n"
        '                "coverage_stress_cases",\n'
        "            ),\n"
        "        )\n"
        "        for observed, expected, field_name in expected_lengths:\n"
        "            if observed != expected:\n"
        "                raise ValueError(f\"study_design.{field_name} must contain {expected} entries\")\n"
        "        for field_name, values in (\n"
        '            ("utility_and_coherence_laws", self.utility_and_coherence_laws),\n'
        '            ("sharpness_oracle_laws", self.sharpness_oracle_laws),\n'
        '            ("safety_and_impossibility_laws", self.safety_and_impossibility_laws),\n'
        "        ):\n"
        "            _require_unique(values, f\"study_design.{field_name}\")\n"
        "        _require_unique(\n"
        "            tuple(case.name for case in self.coverage_stress_cases),\n"
        '            "study_design.coverage_stress_cases.name",\n'
        "        )\n"
        "        return self\n\n\n",
    )
    replace_once(
        path,
        "class GridsConfig(ConfigModel):\n"
        "    partitions: tuple[PositiveInt, ...]\n"
        "    scaling_bands: tuple[PositiveInt, ...]\n"
        "    rho: tuple[SensitivityBudget, ...]\n"
        "    beta: tuple[UnitFloat, ...]\n",
        "class GridsConfig(ConfigModel):\n"
        "    partitions: tuple[PositiveInt, ...]\n"
        "    scaling_bands: tuple[PositiveInt, ...]\n"
        "    rho: tuple[SensitivityBudget, ...]\n"
        "    same_endpoint_rho: tuple[SensitivityBudget, ...]\n"
        "    beta: tuple[UnitFloat, ...]\n",
    )
    replace_once(
        path,
        '        _require_unique(self.rho, "grids.rho")\n'
        '        _require_unique(self.beta, "grids.beta")\n'
        '        _require_strictly_decreasing(self.partitions, "grids.partitions")\n'
        '        _require_strictly_increasing(self.scaling_bands, "grids.scaling_bands")\n'
        '        _require_strictly_increasing(self.rho, "grids.rho")\n'
        '        _require_strictly_increasing(self.beta, "grids.beta")\n',
        '        _require_unique(self.rho, "grids.rho")\n'
        '        _require_unique(self.same_endpoint_rho, "grids.same_endpoint_rho")\n'
        '        _require_unique(self.beta, "grids.beta")\n'
        '        _require_strictly_decreasing(self.partitions, "grids.partitions")\n'
        '        _require_strictly_increasing(self.scaling_bands, "grids.scaling_bands")\n'
        '        _require_strictly_increasing(self.rho, "grids.rho")\n'
        '        _require_strictly_increasing(self.same_endpoint_rho, "grids.same_endpoint_rho")\n'
        '        _require_strictly_increasing(self.beta, "grids.beta")\n',
    )
    replace_once(
        path,
        "class FailureBoundaryConfig(ConfigModel):\n"
        "    unresolvedness: tuple[UnitFloat, ...]\n"
        "    timing_contrast: tuple[NonNegativeFloat, ...]\n"
        "    prevalence: tuple[UnitFloat, ...]\n"
        "    bands: tuple[PositiveInt, ...]\n"
        "    information_margin: tuple[NonNegativeFloat, ...]\n"
        "    risk_offset: tuple[StrictFloat, ...]\n"
        "    sample_size: tuple[PositiveInt, ...]\n",
        "class FailureBoundaryConfig(ConfigModel):\n"
        "    unresolvedness: tuple[UnitFloat, ...]\n"
        "    timing_contrast: tuple[NonNegativeFloat, ...]\n"
        "    prevalence: tuple[UnitFloat, ...]\n"
        "    bands: tuple[PositiveInt, ...]\n"
        "    information_margin: tuple[NonNegativeFloat, ...]\n"
        "    risk_offset: tuple[StrictFloat, ...]\n"
        "    sample_size: tuple[PositiveInt, ...]\n"
        "    terminal_selection_asymmetry: tuple[tuple[UnitFloat, UnitFloat], ...]\n"
        "    optimizer_nodes: tuple[PositiveInt, ...]\n"
        "    optimizer_sample_size: PositiveInt\n",
    )
    replace_once(
        path,
        '            ("failure_boundary.sample_size", self.sample_size),\n'
        "        ):\n"
        "            _require_unique(values, field_name)\n"
        "            _require_strictly_increasing(values, field_name)\n"
        "        return self\n",
        '            ("failure_boundary.sample_size", self.sample_size),\n'
        '            ("failure_boundary.optimizer_nodes", self.optimizer_nodes),\n'
        "        ):\n"
        "            _require_unique(values, field_name)\n"
        "            _require_strictly_increasing(values, field_name)\n"
        "            if len(values) != _FAILURE_BOUNDARY_LEVEL_COUNT:\n"
        "                raise ValueError(f\"{field_name} must contain seven levels\")\n"
        "        _require_unique(\n"
        "            self.terminal_selection_asymmetry,\n"
        '            "failure_boundary.terminal_selection_asymmetry",\n'
        "        )\n"
        "        if len(self.terminal_selection_asymmetry) != _FAILURE_BOUNDARY_LEVEL_COUNT:\n"
        '            raise ValueError("failure_boundary.terminal_selection_asymmetry must contain seven levels")\n'
        "        return self\n",
    )
    replace_once(
        path,
        "    comparators: ComparatorsConfig\n"
        "    sequential: SequentialConfig\n",
        "    comparators: ComparatorsConfig\n"
        "    study_design: StudyDesignConfig\n"
        "    sequential: SequentialConfig\n",
    )
    replace_once(
        path,
        '        if any(bool(x) for x in (rho not in self.grids.rho for rho in self.sequential.utility.rho)):\n'
        '            raise ValueError("sequential.utility.rho must be a subset of grids.rho")\n'
        "        return self\n",
        '        if any(bool(x) for x in (rho not in self.grids.rho for rho in self.sequential.utility.rho)):\n'
        '            raise ValueError("sequential.utility.rho must be a subset of grids.rho")\n'
        "        if any(rho not in self.grids.rho for rho in self.grids.same_endpoint_rho):\n"
        '            raise ValueError("grids.same_endpoint_rho must be a subset of grids.rho")\n'
        "        selected_laws = (\n"
        "            *self.study_design.utility_and_coherence_laws,\n"
        "            *self.study_design.sharpness_oracle_laws,\n"
        "            *self.study_design.safety_and_impossibility_laws,\n"
        "            *(case.law for case in self.study_design.strict_timing_cases),\n"
        "            *(case.law for case in self.study_design.coverage_stress_cases),\n"
        "        )\n"
        "        if any(law not in self.laws for law in selected_laws):\n"
        '            raise ValueError("study-design law selections must reference configured laws")\n'
        "        configured_partitions = set(self.grids.partitions)\n"
        "        for case in self.study_design.strict_timing_cases:\n"
        "            if case.fine_bands not in configured_partitions or case.coarse_bands not in configured_partitions:\n"
        '                raise ValueError("strict timing cases must use configured analysis partitions")\n'
        "        available_stress_bands = configured_partitions | set(self.grids.scaling_bands)\n"
        "        if any(\n"
        "            case.band_count not in available_stress_bands\n"
        "            for case in self.study_design.coverage_stress_cases\n"
        "        ):\n"
        '            raise ValueError("coverage stress cases must use a predeclared partition resolution")\n'
        "        return self\n",
    )


def recover_yaml() -> None:
    path = ROOT / "configs/trajcert.yaml"
    replace_once(
        path,
        "  rho:\n"
        "    [0, 0.0025, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075,\n"
        "     0.10, 0.15, 0.20, 0.30, 0.40, 0.50]\n\n"
        "  beta: [0.01, 0.025, 0.05, 0.10, 0.20]\n",
        "  rho:\n"
        "    [0, 0.0025, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075,\n"
        "     0.10, 0.15, 0.20, 0.30, 0.40, 0.50]\n\n"
        "  same_endpoint_rho: [0.01, 0.05, 0.10, 0.20, 0.40]\n"
        "  beta: [0.01, 0.025, 0.05, 0.10, 0.20]\n",
    )
    replace_once(
        path,
        "numerics:\n",
        "study_design:\n"
        "  utility_and_coherence_laws:\n"
        "    - no_path_dependence\n"
        "    - timing_harmful_late\n"
        "    - terminal_harmful_unresolved\n"
        "    - timing_terminal_harmful_late\n"
        "    - high_unresolvedness\n"
        "    - low_prevalence\n\n"
        "  sharpness_oracle_laws:\n"
        "    - no_path_dependence\n"
        "    - timing_harmful_late\n"
        "    - terminal_harmful_unresolved\n"
        "    - timing_terminal_harmful_late\n"
        "    - timing_terminal_harmful_early\n"
        "    - high_unresolvedness\n"
        "    - low_prevalence\n"
        "    - high_prevalence\n"
        "    - intrinsic_impossibility\n"
        "    - near_degeneracy\n\n"
        "  safety_and_impossibility_laws:\n"
        "    - no_path_dependence\n"
        "    - timing_harmful_late\n"
        "    - terminal_harmful_unresolved\n"
        "    - timing_terminal_harmful_late\n"
        "    - timing_terminal_harmful_early\n"
        "    - high_unresolvedness\n"
        "    - low_prevalence\n"
        "    - intrinsic_impossibility\n\n"
        "  strict_timing_cases:\n"
        "    - {law: no_path_dependence, fine_bands: 8, coarse_bands: 4, expectation: ZERO}\n"
        "    - {law: terminal_harmful_unresolved, fine_bands: 8, coarse_bands: 4, expectation: ZERO}\n"
        "    - {law: same_endpoint_no_timing, fine_bands: 8, coarse_bands: 2, expectation: ZERO}\n"
        "    - {law: timing_harmful_late, fine_bands: 8, coarse_bands: 4, expectation: POSITIVE}\n"
        "    - {law: timing_terminal_harmful_late, fine_bands: 8, coarse_bands: 4, expectation: POSITIVE}\n"
        "    - {law: same_endpoint_with_timing, fine_bands: 8, coarse_bands: 2, expectation: POSITIVE}\n\n"
        "  legacy_partition_incoherence:\n"
        "    gamma: [1.5, 2, 4]\n"
        "    q: [0.1, 0.3]\n"
        "    latent_outcome_probabilities: [0.5, 0.5]\n\n"
        "  coverage_stress_cases:\n"
        "    - {name: \"Independent resolution control\", law: no_path_dependence, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Timing-only harmful-late stress\", law: timing_harmful_late, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Terminal-selection harmful-unresolved stress\", law: terminal_harmful_unresolved, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Timing-and-terminal harmful-late stress\", law: timing_terminal_harmful_late, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Timing-and-terminal harmful-early stress\", law: timing_terminal_harmful_early, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"High unresolvedness stress\", law: high_unresolvedness, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Low error-prevalence stress\", law: low_prevalence, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Near-degeneracy stress\", law: near_degeneracy, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Sixteen-band resolution stress\", law: timing_terminal_harmful_late, band_count: 16, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Thirty-two-band resolution stress\", law: timing_terminal_harmful_late, band_count: 32, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION}\n"
        "    - {name: \"Minimum-information completion stress\", law: timing_terminal_harmful_late, band_count: 8, rho_offset: 0.002, sensitivity_reference: COMPATIBILITY_FLOOR, minimum_information_completion: true}\n"
        "    - {name: \"Near-certification risk-budget stress\", law: timing_terminal_harmful_late, band_count: 8, rho_offset: 0.01, sensitivity_reference: TRUE_INFORMATION, beta_offset: 0.002}\n\n"
        "numerics:\n",
    )
    replace_once(
        path,
        "  sample_size: [25, 50, 100, 200, 500, 1000, 2000]\n",
        "  sample_size: [25, 50, 100, 200, 500, 1000, 2000]\n"
        "  terminal_selection_asymmetry:\n"
        "    - [0.01, 0.50]\n"
        "    - [0.02, 0.40]\n"
        "    - [0.05, 0.30]\n"
        "    - [0.10, 0.10]\n"
        "    - [0.30, 0.05]\n"
        "    - [0.40, 0.02]\n"
        "    - [0.50, 0.01]\n"
        "  optimizer_nodes: [1000, 5000, 20000, 100000, 500000, 1000000, 2000000]\n"
        "  optimizer_sample_size: 500\n",
    )


def recover_registry() -> None:
    path = ROOT / "src/trajcert/experiments/registry.py"
    text = path.read_text(encoding="utf-8")
    names = (
        "Legacy Partition Incoherence Check",
        "Strict Timing-Gain Identity",
        "Partition Coherence",
        "Same Endpoint, Different Timing",
        "Strict Timing Gain",
        "Sharpness Against Generic Oracle",
        "Safety and Intrinsic Impossibility",
        "Anytime Coverage Stress",
        "Population Sensitivity Utility",
        "Sequential Sensitivity Utility",
        "Failure Boundary Atlas",
    )
    for name in names:
        pattern = re.compile(
            rf'(experiment_name=ExperimentNameValue\("{re.escape(name)}"\),.*?configuration_gap_cells=)(\d+)',
            re.DOTALL,
        )
        match = pattern.search(text)
        if match is None:
            raise RuntimeError(f"registry definition not found: {name}")
        if match.group(2) != "0":
            text = text[: match.start(2)] + "0" + text[match.end(2) :]
    path.write_text(text, encoding="utf-8")


def recover_plan() -> None:
    path = ROOT / "src/trajcert/experiments/plan.py"
    replace_once(
        path,
        "_MISSING_LEGACY_GRID = ReasonCode(\"MISSING_LEGACY_Q_GRID_AND_THREE_GAMMA_SELECTION\")\n"
        "_MISSING_FAILURE_AXIS = ReasonCode(\"MISSING_FAILURE_BOUNDARY_AXIS_CONFIGURATION\")\n",
        "",
    )
    start = "def _coordinates_for_definition(\n"
    end = "def _law_names(config: TrajCertConfig) -> tuple[LawName, ...]:\n"
    replacement = '''def _coordinates_for_definition(\n    definition: ExperimentDefinition, config: TrajCertConfig\n) -> tuple[SemanticCoordinates, ...]:\n    name = str(definition.experiment_name)\n    laws = _law_names(config)\n    partitions = _partition_names(config)\n    adjacent_pairs = tuple(\n        ComparisonPairName(f"{fine} -> {coarse}") for fine, coarse in pairwise(partitions)\n    )\n    utility_laws = tuple(\n        LAW_DISPLAY_NAMES[key] for key in config.study_design.utility_and_coherence_laws\n    )\n    if definition.declared_cells == 0:\n        return ()\n    if name == "Scientific and Data Inventory":\n        return (_variant("protocol-inventory-gate"),)\n    if name == "Legacy Partition Incoherence Check":\n        legacy = config.study_design.legacy_partition_incoherence\n        return tuple(\n            SemanticCoordinates(\n                gamma=gamma,\n                variant_name=VariantName(f"q={q}"),\n            )\n            for gamma, q in product(legacy.gamma, legacy.q)\n        )\n    if name in {\n        "Path Information Decomposition",\n        "Information Profile Convexity",\n        "Minimum Compatibility Identity",\n    }:\n        return tuple(\n            SemanticCoordinates(synthetic_law_name=law, partition_name=partition)\n            for law, partition in product(laws, partitions)\n        )\n    if name == "Sharp-Set Constructive Identity":\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=law,\n                partition_name=partition,\n                sensitivity_coordinate=_offset_coordinate(offset),\n            )\n            for law, partition, offset in product(laws, partitions, _SHARP_SET_OFFSETS)\n        )\n    if name == "Refinement Dominance Identity":\n        return tuple(\n            SemanticCoordinates(synthetic_law_name=law, comparison_pair_name=pair)\n            for law, pair in product(laws, adjacent_pairs)\n        )\n    if name in {"Strict Timing-Gain Identity", "Strict Timing Gain"}:\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=LAW_DISPLAY_NAMES[case.law],\n                comparison_pair_name=ComparisonPairName(\n                    f"{partition_name(case.fine_bands)} -> {partition_name(case.coarse_bands)}"\n                ),\n                sensitivity_coordinate=_offset_coordinate(offset),\n            )\n            for case, offset in product(config.study_design.strict_timing_cases, _TIMING_OFFSETS)\n        )\n    if name == "Safety-Boundary Identity":\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=law,\n                variant_name=VariantName(safety_case),\n            )\n            for law, safety_case in product(laws, _SAFETY_CASES)\n        )\n    if name == "Endpoint Special-Case Identity":\n        endpoint = partitions[-1]\n        return tuple(\n            SemanticCoordinates(synthetic_law_name=law, partition_name=endpoint) for law in laws\n        )\n    if name == "Anytime Projection Proof Check":\n        return (_variant("projection-proof-record"),)\n    if name == "Population Complexity Proof Check":\n        return (_variant("population-operation-count-record"),)\n    if name == "Production Solver vs Independent Oracle":\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=law,\n                partition_name=partition,\n                sensitivity_coordinate=_offset_coordinate(offset),\n            )\n            for law, partition, offset in product(laws, partitions, _ORACLE_OFFSETS)\n        )\n    if name in {\n        "Callback-Model Reduction Falsification",\n        "Generic Information-Optimization Reduction",\n    }:\n        finest = partitions[0]\n        return tuple(\n            SemanticCoordinates(synthetic_law_name=law, partition_name=finest) for law in laws\n        )\n    if name == "Partition Coherence":\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=law,\n                comparison_pair_name=pair,\n                sensitivity_coordinate=_offset_coordinate(offset),\n            )\n            for law, pair, offset in product(utility_laws, adjacent_pairs, _TIMING_OFFSETS)\n        )\n    if name == "Same Endpoint, Different Timing":\n        comparison = ComparisonPairName(\n            "Same endpoint without timing information|Same endpoint with timing information"\n        )\n        return tuple(\n            SemanticCoordinates(\n                comparison_pair_name=comparison,\n                partition_name=partition,\n                rho=rho,\n            )\n            for partition, rho in product(partitions, config.grids.same_endpoint_rho)\n        )\n    if name == "Compatibility Floor Behavior":\n        selected_partitions = (partitions[0], partitions[-1])\n        return tuple(\n            SemanticCoordinates(synthetic_law_name=law, partition_name=partition)\n            for law, partition in product(laws, selected_partitions)\n        )\n    if name == "Sharpness Against Generic Oracle":\n        selected_laws = tuple(\n            LAW_DISPLAY_NAMES[key] for key in config.study_design.sharpness_oracle_laws\n        )\n        return tuple(\n            SemanticCoordinates(synthetic_law_name=law, partition_name=partition)\n            for law, partition in product(selected_laws, partitions)\n        )\n    if name == "Safety and Intrinsic Impossibility":\n        selected_laws = tuple(\n            LAW_DISPLAY_NAMES[key] for key in config.study_design.safety_and_impossibility_laws\n        )\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=law,\n                variant_name=VariantName(safety_case),\n            )\n            for law, safety_case in product(selected_laws, _SAFETY_CASES)\n        )\n    if name == "Anytime Implementation Hand Cases":\n        return tuple(\n            SemanticCoordinates(\n                variant_name=VariantName(f"hand-case-{case_index:02d}"),\n                partition_name=partition,\n            )\n            for case_index, partition in product(range(1, 11), partitions[:3])\n        )\n    if name == "Anytime Coverage Stress":\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=LAW_DISPLAY_NAMES[case.law],\n                partition_name=partition_name(case.band_count),\n                variant_name=VariantName(case.name),\n            )\n            for case in config.study_design.coverage_stress_cases\n        )\n    if name == "Population Sensitivity Utility":\n        rho_values = _population_rho_values(config)\n        return tuple(\n            SemanticCoordinates(\n                synthetic_law_name=law,\n                partition_name=partition,\n                rho=rho,\n            )\n            for law, partition, rho in product(utility_laws, partitions, rho_values)\n        )\n    if name == "Sequential Sensitivity Utility":\n        return tuple(\n            SemanticCoordinates(synthetic_law_name=law, rho=rho)\n            for law, rho in product(utility_laws, config.sequential.utility.rho)\n        )\n    if name == "Failure Boundary Atlas":\n        return _failure_boundary_coordinates(config)\n    if name == "Computational Scaling":\n        return tuple(\n            SemanticCoordinates(scaling_band_count=band_count)\n            for band_count in config.grids.scaling_bands\n        )\n    if name == "Statistical Synthesis":\n        return (_variant("deterministic-synthesis"),)\n    raise ValueError(f"no plan expansion implementation for registry experiment: {name}")\n\n\n'''
    replace_block(path, start, end, replacement)
    start = "def _failure_boundary_coordinates(config: TrajCertConfig) -> tuple[SemanticCoordinates, ...]:\n"
    end = "def _signed_level(axis_name: str, level: float | int) -> str:\n"
    replacement = '''def _failure_boundary_coordinates(config: TrajCertConfig) -> tuple[SemanticCoordinates, ...]:\n    configured_axes: tuple[tuple[str, tuple[float | int, ...]], ...] = (\n        ("terminal-unresolved-severity", tuple(config.failure_boundary.unresolvedness)),\n        ("timing-contrast", tuple(config.failure_boundary.timing_contrast)),\n        ("harmful-prevalence", tuple(config.failure_boundary.prevalence)),\n        ("path-resolution", tuple(config.failure_boundary.bands)),\n        ("information-margin", tuple(config.failure_boundary.information_margin)),\n        ("risk-offset", tuple(config.failure_boundary.risk_offset)),\n        ("matured-sample-size", tuple(config.failure_boundary.sample_size)),\n        ("optimizer-node-budget", tuple(config.failure_boundary.optimizer_nodes)),\n    )\n    coordinates: list[SemanticCoordinates] = []\n    for axis_name, levels in configured_axes:\n        if len(levels) != 7:\n            raise ValueError(f"failure-boundary axis {axis_name} must contain exactly seven levels")\n        for level in levels:\n            coordinates.append(\n                SemanticCoordinates(\n                    failure_boundary_axis_and_level=FailureBoundaryCoordinate(\n                        f"{axis_name}={_signed_level(axis_name, level)}"\n                    )\n                )\n            )\n    for q1, q0 in config.failure_boundary.terminal_selection_asymmetry:\n        coordinates.append(\n            SemanticCoordinates(\n                failure_boundary_axis_and_level=FailureBoundaryCoordinate(\n                    f"terminal-selection-asymmetry=q1:{q1},q0:{q0}"\n                )\n            )\n        )\n    return tuple(coordinates)\n\n\n'''
    replace_block(path, start, end, replacement)
    start = "def _invalid_reason(\n"
    end = "def _required_experiments(\n"
    replacement = '''def _invalid_reason(\n    definition: ExperimentDefinition, ordinal: int, gap_start: int\n) -> ReasonCode | None:\n    if definition.configuration_gap_cells == 0 or ordinal < gap_start:\n        return None\n    return ReasonCode("MISSING_AUTHORITATIVE_CONFIGURATION")\n\n\n'''
    replace_block(path, start, end, replacement)


def main() -> None:
    recover_config_model()
    recover_yaml()
    recover_registry()
    recover_plan()


if __name__ == "__main__":
    main()
