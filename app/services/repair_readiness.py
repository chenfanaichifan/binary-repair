"""Phase-8A Repair Readiness registry and read-only evidence probes.

This module is the single source of truth for the 30-item readiness baseline
(G01-G30, titles verbatim from the user's Phase-8 list).  It performs **no
repair, no network access, no provider/AI call, no benchmark/PoC execution**;
the audit script only reads the working tree.

Hard evidence rule (enforced by the audit script and ``validate_document``):

* ``implemented`` - code probe and test probe hit (plus artifact/ground-truth
  probes when the item declares them);
* ``partial``    - only a contract/registry/script/documentation path exists, or
  only one of code/test is present;
* ``missing``    - no evidence path exists in this tree;
* ``not_run``    - explicitly blocked by an unavailable external capability
  (for example a hidden benchmark that is not distributed);
* ``non_goal``   - the item is one of the 12 documented capability non-goals.

Every item carries ``blocker``, ``next_action`` and ``capability_claim=false``:
this audit never claims a new repair capability and never upgrades a verified
state.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = 1
KIND = "repair_readiness_audit"
AUDIT_DATE = "2026-11-16"
STATUSES = ("implemented", "partial", "missing", "not_run", "non_goal")
PHASES = ("8A", "8B", "8C", "8D", "8E")
PRIORITIES = ("P0", "P1", "P2")
GAP_IDS = tuple(f"G{index:02d}" for index in range(1, 31))
CLAIMS_PATH = "docs/status/claims.json"


def _probe(code_paths: list[str], test_paths: list[str],
           ground_truth_paths: list[str], independent_verifier_paths: list[str],
           artifact_paths: list[str], cli: list[str],
           source_scope: list[str], test_markers: list[str],
           ) -> dict[str, Any]:
    return {
        "code_paths": code_paths,
        "test_paths": test_paths,
        "test_markers": test_markers,
        "artifact_paths": artifact_paths,
        "cli": cli,
        "source_scope": source_scope,
        "ground_truth_paths": ground_truth_paths,
        "independent_verifier_paths": independent_verifier_paths,
    }


#: G01-G30 registry.  Titles are the user's Phase-8 titles (not reworded).
READINESS_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "gap_id": "G01",
        "title": "外部知识扫描 Knowledge Source Scanner",
        "title_en": "External Knowledge Source Scanner",
        "user_requirement": (
            "Scan external knowledge sources (NVD/CWE/overflow knowledge) and "
            "turn them into capability-gap candidates."),
        "phase": "8A",
        "priority": "P1",
        "dependencies": [],
        "required_deliverable": (
            "scanner code + test + provisioned knowledge corpus artifact"),
        "probe_spec": _probe(
            ["scripts/fetch_nvd_metadata.py",
             "scripts/train_overflow_knowledge.py",
             "app/services/overflow_features.py"],
            ["tests/test_overflow_knowledge.py"],
            ["knowledge/nvd_sample.json", "knowledge/overflow_kb.json"],
            [], [], ["scripts/fetch_nvd_metadata.py"],
            ["overflow"], ["overflow"]),
        "force_status": "partial",
        "blocker_if_missing": (
            "external NVD corpus is not provisioned; the knowledge_source_scan "
            "discovery mechanism is declared not_run in this tree"),
    },
    {
        "gap_id": "G02",
        "title": "未知维度发现 Dimension Discovery Engine",
        "title_en": "Dimension Discovery Engine",
        "user_requirement": (
            "Discover capability dimensions beyond the legacy 11 technical "
            "dimensions and map them to the measured universe."),
        "phase": "8A",
        "priority": "P1",
        "dependencies": ["G01"],
        "required_deliverable": "20-dimension registry + mapping artifact + tests",
        "probe_spec": _probe(
            ["app/services/capability_dimensions.py",
             "scripts/build_universe_dimension_registry.py"],
            ["tests/test_capability_dimensions.py"],
            ["artifacts/capability-universe-2026-11-16/dimension-registry.json"],
            [], ["artifacts/capability-universe-2026-11-16"],
            ["scripts/build_universe_dimension_registry.py --check"],
            ["capability_dimensions"], ["capability_dimensions"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G03",
        "title": "240 cells 之外的 unknown-space tracking",
        "title_en": "Unknown-space tracking beyond 240 cells",
        "user_requirement": (
            "Track capability space outside the 240 measured cells instead of "
            "pretending it does not exist."),
        "phase": "8A",
        "priority": "P1",
        "dependencies": ["G02"],
        "required_deliverable": (
            "explicit unknown/undiscovered-space accounting with unknown=0 "
            "inside the universe and an honest statement outside it"),
        "probe_spec": _probe(
            ["scripts/check_universe_methodology.py",
             "app/services/capability_dimensions.py"],
            ["tests/test_universe_methodology.py"],
            ["artifacts/capability-universe-2026-11-16/dimension-registry.json",
             "artifacts/capability-universe-2026-11-15/methodology.json"],
            [], ["artifacts/capability-universe-2026-11-15"],
            ["scripts/check_universe_methodology.py --check"],
            [], []),
        "force_status": "partial",
        "blocker_if_missing": (
            "space outside the 240 measured cells is only tracked as "
            "undiscovered_space=not_measurable; no enumerated unknown inventory"),
    },
    {
        "gap_id": "G04",
        "title": "交叉能力组合 Combination Discovery",
        "title_en": "Cross-capability Combination Discovery",
        "user_requirement": (
            "Discover capability gaps that appear only when two dimensions "
            "combine (container x analysis x strategy ...)."),
        "phase": "8A",
        "priority": "P2",
        "dependencies": ["G02", "G03"],
        "required_deliverable": "combination engine + tests + candidate artifact",
        "probe_spec": _probe(
            [], [], [], [], [], [], [], []),
        "force_status": "",
        "blocker_if_missing": (
            "no combination-discovery engine exists; the gap registry only has "
            "single-mechanism adapters"),
    },
    {
        "gap_id": "G05",
        "title": "Mutation-based Discovery",
        "title_en": "Mutation-based Discovery",
        "user_requirement": (
            "Discover gaps by mutating fixtures/inputs and observing analysis "
            "or repair divergences."),
        "phase": "8A",
        "priority": "P2",
        "dependencies": ["G07", "G08"],
        "required_deliverable": "mutation engine + deterministic seeds + tests",
        "probe_spec": _probe([], [], [], [], [], [], [], []),
        "force_status": "",
        "blocker_if_missing": (
            "mutation discovery is declared NOT RUN: no mutation engine/corpus "
            "exists in this tree"),
    },
    {
        "gap_id": "G06",
        "title": "Metamorphic Discovery",
        "title_en": "Metamorphic Discovery",
        "user_requirement": (
            "Discover gaps with metamorphic relations on equivalent binaries."),
        "phase": "8A",
        "priority": "P2",
        "dependencies": ["G07", "G08"],
        "required_deliverable": (
            "metamorphic relation engine + fixtures + tests"),
        "probe_spec": _probe([], [], [], [], [], [], [], []),
        "force_status": "",
        "blocker_if_missing": (
            "metamorphic discovery is declared NOT RUN: no relation engine "
            "exists in this tree"),
    },
    {
        "gap_id": "G07",
        "title": "外部二进制样本库 Binary Corpus",
        "title_en": "External Binary Corpus",
        "user_requirement": (
            "Provide a reproducible binary sample corpus for discovery and "
            "benchmarking."),
        "phase": "8A",
        "priority": "P1",
        "dependencies": [],
        "required_deliverable": (
            "corpus builder/analyzer + committed corpus metadata + tests"),
        "probe_spec": _probe(
            ["scripts/build_local_binary_corpus.py",
             "scripts/analyze_local_binary_corpus.py",
             "app/services/binary_datasets.py"],
            ["tests/test_binary_datasets.py", "tests/test_cgc_dataset.py"],
            ["knowledge/cgc_corpus.json", "knowledge/local_binary_features.json",
             "knowledge/binary_dataset_summary.json"],
            [], [], ["scripts/build_local_binary_corpus.py --check"],
            ["binary_datasets"], ["binary_datasets", "cgc"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G08",
        "title": "新发现与旧 Gap 去重/lineage",
        "title_en": "Deduplication and lineage for findings vs old gaps",
        "user_requirement": (
            "Give every discovered gap a deterministic identity and lineage so "
            "duplicates do not inflate the gap count."),
        "phase": "8A",
        "priority": "P1",
        "dependencies": ["G01", "G07"],
        "required_deliverable": (
            "unified GapRecord + deterministic ids/lineage + tests + artifact"),
        "probe_spec": _probe(
            ["app/services/gap_registry.py",
             "scripts/discover_capability_gaps.py"],
            ["tests/test_gap_registry_discovery.py"],
            ["artifacts/gap-registry-2026-11-16/gaps.json",
             "artifacts/gap-registry-2026-11-16/candidates.json"],
            [], ["artifacts/gap-registry-2026-11-16"],
            ["scripts/discover_capability_gaps.py --check"],
            ["gap_registry"], ["gap_registry"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G09",
        "title": "跨函数 Data-Flow",
        "title_en": "Cross-function Data-Flow",
        "user_requirement": (
            "Track tainted data across function boundaries, not only inside one "
            "analyzed function."),
        "phase": "8B",
        "priority": "P0",
        "dependencies": [],
        "required_deliverable": (
            "inter-procedural data-flow analysis + fixtures + tests"),
        "probe_spec": _probe(
            ["app/services/repair/analyzer.py",
             "app/services/repair/call_targets.py"],
            ["tests/test_repair_analyzer.py"],
            [], [], [], [], ["same-function"], ["Sink analysis"]),
        "force_status": "partial",
        "blocker_if_missing": (
            "analyzer scope is same-function only: cross-function allocations "
            "and argument flows fail closed and are not tracked"),
    },
    {
        "gap_id": "G10",
        "title": "Pointer Alias",
        "title_en": "Pointer Alias",
        "user_requirement": (
            "Resolve pointer aliases (pointer+offset, multiple names) for "
            "destination capacity."),
        "phase": "8B",
        "priority": "P0",
        "dependencies": ["G09"],
        "required_deliverable": "alias-aware capacity analysis + fixtures + tests",
        "probe_spec": _probe(
            ["app/services/repair/analyzer.py"],
            ["tests/test_repair_analyzer.py"],
            [], [], [], [], ["alias"], []),
        "force_status": "",
        "non_goal_ids": ["NG-non-goal-1"],
        "blocker_if_missing": (
            "pointer aliases/offsets are not tracked by the same-function "
            "analyzer; the capability is an explicit claims non-goal"),
    },
    {
        "gap_id": "G11",
        "title": "全局变量/结构体容量推断",
        "title_en": "Global variable / struct capacity inference",
        "user_requirement": (
            "Infer capacities of global buffers and struct members."),
        "phase": "8B",
        "priority": "P0",
        "dependencies": ["G09"],
        "required_deliverable": (
            "global/struct capacity recovery + fixtures + tests"),
        "probe_spec": _probe(
            ["app/services/repair/analyzer.py"],
            ["tests/test_repair_analyzer.py"],
            [], [], [], [], ["global"], []),
        "force_status": "",
        "non_goal_ids": ["NG-non-goal-1"],
        "blocker_if_missing": (
            "global destinations are reserved and struct member layout needs "
            "DWARF; the capability is an explicit claims non-goal"),
    },
    {
        "gap_id": "G12",
        "title": "Integer 漏洞分析（range/overflow/truncation/signedness）",
        "title_en": "Integer vulnerability analysis (range/overflow/truncation/signedness)",
        "user_requirement": (
            "Analyze integer range, overflow, truncation and signedness "
            "defects."),
        "phase": "8B",
        "priority": "P0",
        "dependencies": ["G09"],
        "required_deliverable": (
            "integer analysis + deterministic repair templates + fixtures + tests"),
        "probe_spec": _probe(
            ["app/services/overflow_features.py",
             "app/services/repair/capacity.py"],
            ["tests/test_capacity_repair.py"],
            [], [], [], ["scripts/classify_overflow.py"],
            ["range check"], ["range check"]),
        "force_status": "partial",
        "blocker_if_missing": (
            "only the duplicated-range-check capacity rewrite is deterministic; "
            "general truncation/signedness analysis has no path"),
    },
    {
        "gap_id": "G13",
        "title": "String 漏洞分析",
        "title_en": "String vulnerability analysis",
        "user_requirement": (
            "Analyze and repair string buffer vulnerabilities (strcpy/strcat/"
            "memcpy family)."),
        "phase": "8B",
        "priority": "P0",
        "dependencies": [],
        "required_deliverable": (
            "string-sink analysis + guard repair + fixtures + runtime evidence"),
        "probe_spec": _probe(
            ["app/services/repair/guards.py", "app/services/repair/writer.py"],
            ["tests/test_repair_guards.py", "tests/test_pe_strcpy_guard.py"],
            ["fixtures/elf/vuln-strcpy-x86_64.elf"],
            [], ["artifacts/coverage-closure-2026-11-14"],
            [], ["strcpy"], ["strcpy"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G14",
        "title": "UAF 生命周期",
        "title_en": "UAF lifetime",
        "user_requirement": "Detect and repair use-after-free lifetime bugs.",
        "phase": "8B",
        "priority": "P1",
        "dependencies": ["G09"],
        "required_deliverable": "UAF lifetime analysis + repair + fixtures + tests",
        "probe_spec": _probe([], [], [], [], [], [], [], []),
        "force_status": "",
        "non_goal_ids": ["NG-non-goal-2"],
        "blocker_if_missing": (
            "UAF/lifetime deterministic repair is an explicit claims non-goal "
            "(AI research only)"),
    },
    {
        "gap_id": "G15",
        "title": "间接调用分析",
        "title_en": "Indirect call analysis",
        "user_requirement": (
            "Analyze indirect calls (function pointers, vtables) for repair "
            "targets."),
        "phase": "8B",
        "priority": "P0",
        "dependencies": [],
        "required_deliverable": (
            "indirect-call target analysis + allow-list + tests"),
        "probe_spec": _probe(
            ["app/services/repair/call_targets.py"],
            ["tests/test_ai_assembly_calls.py"],
            [], [], [], [], ["indirect calls"], ["AllowedCall"]),
        "force_status": "partial",
        "blocker_if_missing": (
            "only direct calls already made by the target are resolvable; "
            "indirect calls are explicitly forbidden, not analyzed"),
    },
    {
        "gap_id": "G16",
        "title": "路径敏感分析",
        "title_en": "Path-sensitive analysis",
        "user_requirement": (
            "Analyze path-sensitive guard/repair conditions (path predicates)."),
        "phase": "8B",
        "priority": "P1",
        "dependencies": ["G09"],
        "required_deliverable": "path-sensitive analysis + fixtures + tests",
        "probe_spec": _probe([], [], [], [], [], [], [], []),
        "force_status": "",
        "blocker_if_missing": (
            "no path-sensitive analysis module exists; the analyzer is linear "
            "basic-block based"),
    },
    {
        "gap_id": "G17",
        "title": "并发漏洞分析",
        "title_en": "Concurrency vulnerability analysis",
        "user_requirement": "Analyze concurrency/race vulnerabilities.",
        "phase": "8B",
        "priority": "P1",
        "dependencies": ["G16"],
        "required_deliverable": "concurrency analysis + fixtures + tests",
        "probe_spec": _probe([], [], [], [], [], [], [], []),
        "force_status": "",
        "blocker_if_missing": (
            "no concurrency/race analysis module exists in this tree"),
    },
    {
        "gap_id": "G18",
        "title": "更多二进制格式/架构覆盖",
        "title_en": "More binary format/architecture coverage",
        "user_requirement": (
            "Extend binary format/architecture coverage beyond the current "
            "matrix."),
        "phase": "8B",
        "priority": "P2",
        "dependencies": ["G13"],
        "required_deliverable": (
            "additional format/arch writers + fixtures + gate cells"),
        "probe_spec": _probe(
            ["app/services/repair_matrix.py"],
            ["tests/test_repair_matrix.py"],
            ["artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"],
            [], [], [], [], []),
        "force_status": "",
        "non_goal_ids": ["NG-non-goal-3", "NG-non-goal-4", "NG-non-goal-5"],
        "blocker_if_missing": (
            "arm32/riscv/mips/powerpc/big-endian, 32-bit/fat Mach-O and foreign "
            "native execution are explicit claims non-goals"),
    },
    {
        "gap_id": "G19",
        "title": "Repair Strategy Registry",
        "title_en": "Repair Strategy Registry",
        "user_requirement": (
            "Register repair strategies/profiles with declared evidence model."),
        "phase": "8C",
        "priority": "P0",
        "dependencies": [],
        "required_deliverable": (
            "strategy/evidence-profile registry + matrix + tests"),
        "probe_spec": _probe(
            ["app/services/repair_matrix.py"],
            ["tests/test_repair_matrix.py", "tests/test_gate_profiles.py"],
            ["artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"],
            [], [], [], ["STRATEGY_PROFILES"], ["STRATEGY_PROFILES"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G20",
        "title": "Repair Planner",
        "title_en": "Repair Planner",
        "user_requirement": (
            "Plan a structured repair (RepairSpec) before generating bytes."),
        "phase": "8C",
        "priority": "P0",
        "dependencies": ["G19", "G09", "G12", "G13"],
        "required_deliverable": "planner + plan verification + tests + artifact",
        "probe_spec": _probe(
            ["app/services/repair_spec.py", "app/services/obligations.py",
             "app/services/repair/abi.py"],
            ["tests/test_repair_spec.py", "tests/test_repair_planning.py"],
            ["artifacts/ai-repair-planning-2026-11-15/README.md"],
            [], ["artifacts/ai-repair-planning-2026-11-15"],
            ["scripts/repair_binary.py --plan-only"], ["RepairSpec"],
            ["RepairSpec"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G21",
        "title": "Candidate Manager",
        "title_en": "Candidate Manager",
        "user_requirement": (
            "Stage provider/repair candidates without treating them as results."),
        "phase": "8C",
        "priority": "P1",
        "dependencies": ["G20"],
        "required_deliverable": (
            "candidate staging boundary + API + tests"),
        "probe_spec": _probe(
            ["app/services/candidate_staging.py"],
            ["tests/integration/test_candidate_staging.py"],
            [], [], [], [], [], ["candidate_staging"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G22",
        "title": "Patch Application Engine",
        "title_en": "Patch Application Engine",
        "user_requirement": (
            "Apply a reviewed repair action to binary bytes deterministically."),
        "phase": "8C",
        "priority": "P0",
        "dependencies": ["G19", "G21"],
        "required_deliverable": (
            "writer/application engine + re-derivation + fixtures + tests"),
        "probe_spec": _probe(
            ["app/services/repair/writer.py", "app/services/repair/guards.py"],
            ["tests/test_repair_guards.py", "tests/test_repair_i386_writer.py"],
            ["fixtures/elf/vuln-strcpy-x86_64.elf"],
            [], ["artifacts/coverage-closure-2026-11-14"],
            [], ["guard"], ["guard"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G23",
        "title": "Binary Integrity Verifier",
        "title_en": "Binary Integrity Verifier",
        "user_requirement": (
            "Verify the patched binary is structurally intact and is the "
            "claimed candidate (identity, reparse, bounds)."),
        "phase": "8D",
        "priority": "P0",
        "dependencies": ["G22"],
        "required_deliverable": (
            "integrity/identity verifier + gate checks + tests"),
        "probe_spec": _probe(
            ["app/services/binary_verification.py",
             "app/services/containers.py",
             "app/services/unified_verification.py",
             "app/services/independent_verifier.py",
             "scripts/verify_repair.py"],
            ["tests/test_binary_verification.py",
             "tests/test_container_robustness.py",
             "tests/test_independent_verifier.py"],
            ["artifacts/coverage-closure-2026-11-14/acceptance.json"],
            [], ["artifacts/coverage-closure-2026-11-14"],
            [], ["candidate.identity.patched"], ["candidate.identity.patched"]),
        "force_status": "",
        "blocker_if_missing": (
            "independent verifier is selftest-only and the committed "
            "coverage-closure acceptance checksum is stale; no real integrity "
            "run is claimed"),
    },
    {
        "gap_id": "G24",
        "title": "Semantic Verifier",
        "title_en": "Semantic Verifier",
        "user_requirement": (
            "Verify the repaired binary semantically (runtime/emulated evidence, "
            "gate profiles)."),
        "phase": "8D",
        "priority": "P0",
        "dependencies": ["G23", "G22"],
        "required_deliverable": (
            "unified semantic gate + runtime evidence + tests + acceptance"),
        "probe_spec": _probe(
            ["app/services/unified_verification.py",
             "app/services/runtime/emulated.py",
             "app/services/runtime/capabilities.py",
             "app/services/independent_verifier.py"],
            ["tests/test_binary_verification.py", "tests/test_poc_gate.py",
             "tests/test_runtime_capabilities.py"],
            ["artifacts/coverage-closure-2026-11-14/acceptance.json"],
            [], ["artifacts/coverage-closure-2026-11-14"],
            [], ["unified"], ["build_verification"]),
        "force_status": "",
        "blocker_if_missing": (
            "semantic/runtime evidence exists but the committed coverage-closure "
            "acceptance checksum is stale; no new semantic verification is "
            "claimed"),
    },
    {
        "gap_id": "G25",
        "title": "Regression Engine",
        "title_en": "Regression Engine",
        "user_requirement": (
            "Run PoC + regression differentials and record the verdict."),
        "phase": "8D",
        "priority": "P0",
        "dependencies": ["G24"],
        "required_deliverable": (
            "PoC/regression runner + gate integration + tests + acceptance"),
        "probe_spec": _probe(
            ["app/services/poc_runner.py", "app/services/binary_verification.py"],
            ["tests/test_poc_runner.py", "tests/test_poc_gate.py",
             "tests/test_legacy_manifest_gate.py"],
            ["artifacts/coverage-closure-2026-11-14/acceptance.json"],
            [], ["artifacts/coverage-closure-2026-11-14"],
            [], ["run_poc"], ["run_poc"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G26",
        "title": "Autonomous Experiment Engine",
        "title_en": "Autonomous Experiment Engine",
        "user_requirement": (
            "Run bounded autonomous repair experiments with recorded evidence."),
        "phase": "8D",
        "priority": "P1",
        "dependencies": ["G08", "G20", "G25"],
        "required_deliverable": (
            "reflection/experiment engine + audit + artifact + tests"),
        "probe_spec": _probe(
            ["app/services/reflection_engine.py",
             "scripts/run_autonomous_reflection.py",
             "scripts/autonomous_repair_audit.py"],
            ["tests/test_reflection_engine.py",
             "tests/test_autonomous_repair_audit.py"],
            ["artifacts/autonomous-reflection-2026-11-16/README.md",
             "artifacts/autonomous-repair-audit-2026-11-16/README.md"],
            [], ["artifacts/autonomous-reflection-2026-11-16",
                  "artifacts/autonomous-repair-audit-2026-11-16"],
            ["scripts/run_autonomous_reflection.py --check"],
            ["reflection"], ["reflection"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G27",
        "title": "Acceptance Oracle Self-Audit",
        "title_en": "Acceptance Oracle Self-Audit",
        "user_requirement": (
            "Self-audit the acceptance oracle: mismatch model, matrix, meta "
            "recall/precision."),
        "phase": "8D",
        "priority": "P1",
        "dependencies": ["G23", "G24", "G25"],
        "required_deliverable": (
            "acceptance model + mismatch matrix + meta-audit + tests + artifact"),
        "probe_spec": _probe(
            ["app/services/acceptance_models.py",
             "scripts/audit_acceptance_models.py", "scripts/meta_audit.py"],
            ["tests/test_acceptance_models.py", "tests/test_meta_audit.py"],
            ["artifacts/acceptance-model-audit-2026-11-16/report.json"],
            [], ["artifacts/acceptance-model-audit-2026-11-16"],
            ["scripts/audit_acceptance_models.py --check"],
            ["AcceptanceModelMatcher"], ["AcceptanceModelMatcher"]),
        "force_status": "",
        "blocker_if_missing": "",
    },
    {
        "gap_id": "G28",
        "title": "Multi-model Evaluation",
        "title_en": "Multi-model Evaluation",
        "user_requirement": (
            "Evaluate multiple providers/models on a fixed benchmark and record "
            "honest provider identity."),
        "phase": "8E",
        "priority": "P1",
        "dependencies": ["G27"],
        "required_deliverable": (
            "provider matrix runner + targets + artifact + tests"),
        "probe_spec": _probe(
            ["scripts/run_multi_model_matrix.py",
             "scripts/run_provider_matrix.py",
             "scripts/build_ground_truth_benchmark.py",
             "app/services/provider.py"],
            ["tests/test_provider_matrix.py",
             "tests/test_provider_coverage_artifact.py"],
            ["artifacts/provider-matrix-2026-11-14/summary.json",
             "artifacts/multi-model-matrix-2026-11-14/README.md",
             "benchmark/phase8-v1/manifest.json"],
            [], ["artifacts/provider-matrix-2026-11-14",
                  "benchmark/phase8-v1"],
            ["scripts/run_provider_matrix.py --check"], ["provider"],
            ["provider"]),
        "force_status": "partial",
        "blocker_if_missing": (
            "only 2 of 4 target providers have real recorded evidence; the "
            "other slots are not measured"),
    },
    {
        "gap_id": "G29",
        "title": "Hidden Benchmark",
        "title_en": "Hidden Benchmark",
        "user_requirement": (
            "Validate against a hidden held-out benchmark to prevent benchmark "
            "overfitting."),
        "phase": "8E",
        "priority": "P2",
        "dependencies": ["G07", "G28"],
        "required_deliverable": (
            "hidden benchmark contract + availability flag + runner"),
        "probe_spec": _probe(
            ["contracts/benchmark-sample.schema.json",
             "scripts/build_ground_truth_benchmark.py"],
            ["benchmark/phase8-v1/manifest.json"],
            [], ["artifacts/hidden-benchmark-2026-11-16",
                  "benchmark/phase8-v1"], [], [], [], []),
        "force_status": "not_run",
        "not_run_reason": (
            "hidden_available=false: the hidden benchmark is not distributed "
            "with this tree; no hidden run is claimed"),
        "blocker_if_missing": (
            "hidden benchmark unavailable (hidden_available=false); the registry "
            "must never fabricate a hidden run"),
    },
    {
        "gap_id": "G30",
        "title": "Capability Promotion Governance",
        "title_en": "Capability Promotion Governance",
        "user_requirement": (
            "Govern how a capability is promoted to verified/release-eligible "
            "with evidence, review and independence gates."),
        "phase": "8E",
        "priority": "P1",
        "dependencies": ["G27", "G28"],
        "required_deliverable": (
            "canonical repair states + contracts + promotion tests + fixture "
            "artifact"),
        "probe_spec": _probe(
            ["app/services/repair_states.py", "contracts/repair.schema.json",
             "contracts/acceptance.schema.json",
             "contracts/verification.schema.json",
             "contracts/benchmark-sample.schema.json"],
            ["tests/test_repair_states.py", "tests/test_contracts.py",
             "tests/test_contract_schemas.py"],
            ["artifacts/contract-fixtures-2026-11-16/SHA256SUMS"],
            [], ["artifacts/contract-fixtures-2026-11-16"],
            ["scripts/check_contract_schemas.py --check"], ["repair_states"],
            ["repair_states"]),
        "force_status": "partial",
        "blocker_if_missing": (
            "only the state machine and JSON contracts exist; an end-to-end "
            "promotion workflow with independent review is not audited"),
    },
)

_ITEM_BY_ID = {item["gap_id"]: item for item in READINESS_ITEMS}


def item_by_id(gap_id: str) -> dict[str, Any] | None:
    return _ITEM_BY_ID.get(gap_id)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _file_probe(root: Path, relative_paths: list[str]) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []
    for relative in relative_paths:
        target = root / relative
        if target.is_file():
            present.append(relative)
        else:
            missing.append(relative)
    return {"ok": not missing and bool(relative_paths), "present": present,
            "missing": missing}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_probe(root: Path, relative_paths: list[str]) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []
    problems: list[str] = []
    for relative in relative_paths:
        target = root / relative
        if target.is_dir():
            sums = target / "SHA256SUMS"
            if sums.is_file():
                try:
                    for line in sums.read_text(encoding="utf-8").splitlines():
                        parts = line.split()
                        if len(parts) != 2:
                            problems.append(
                                f"{relative}: malformed SHA256SUMS line")
                            continue
                        digest, name = parts[0], parts[1]
                        file_path = target / name
                        if not file_path.is_file():
                            problems.append(
                                f"{relative}: listed file {name} missing")
                        elif _sha256_file(file_path) != digest:
                            problems.append(
                                f"{relative}: sha256 mismatch for {name}")
                except (OSError, UnicodeError) as exc:
                    problems.append(f"{relative}: SHA256SUMS unreadable: {exc}")
            if target.is_dir():
                present.append(relative)
        elif target.is_file():
            present.append(relative)
        else:
            missing.append(relative)
    return {"ok": not missing and not problems and bool(relative_paths),
            "present": present, "missing": missing, "problems": problems}


def _test_probe(root: Path, test_paths: list[str],
                markers: list[str]) -> dict[str, Any]:
    probe = _file_probe(root, test_paths)
    found_markers: list[str] = []
    missing_markers: list[str] = []
    combined = "\n".join(_read_text(root / relative)
                         for relative in test_paths)
    for marker in markers:
        if marker and marker in combined:
            found_markers.append(marker)
        elif marker:
            missing_markers.append(marker)
    return {
        "ok": probe["ok"] and not missing_markers,
        "present": probe["present"],
        "missing": probe["missing"],
        "found_markers": found_markers,
        "missing_markers": missing_markers,
    }


def _cli_probe(root: Path, cli_entries: list[str]) -> dict[str, Any]:
    present: list[str] = []
    missing: list[str] = []
    for entry in cli_entries:
        script = entry.split()[0] if entry else ""
        if script and (root / script).is_file():
            present.append(entry)
        elif entry:
            missing.append(entry)
    return {"ok": not missing and bool(cli_entries),
            "present": present, "missing": missing}


def _import_probe(root: Path,
                  code_paths: list[str]) -> dict[str, Any]:
    """Static importability evidence for app modules (find_spec, no execution)."""
    import importlib.util

    modules: list[str] = []
    missing: list[str] = []
    for relative in code_paths:
        if not relative.startswith("app/") or not relative.endswith(".py"):
            continue
        module_name = relative[:-3].replace("/", ".")
        if module_name.endswith(".__init__"):
            module_name = module_name[: -len(".__init__")]
        try:
            spec = importlib.util.find_spec(module_name)
        except Exception:  # noqa: BLE001 - importability is best-effort evidence
            spec = None
        if spec is not None:
            modules.append(module_name)
        else:
            missing.append(module_name)
    return {"ok": not missing and bool(modules), "modules": modules,
            "missing": missing}


def _ground_truth_probe(root: Path,
                        relative_paths: list[str]) -> dict[str, Any]:
    if not relative_paths:
        return {"status": "not_applicable", "present": [], "missing": []}
    probe = _file_probe(root, relative_paths)
    return {
        "status": "present" if probe["ok"] else "absent",
        "present": probe["present"],
        "missing": probe["missing"],
    }


def _independent_verifier_probe(root: Path,
                                relative_paths: list[str]) -> dict[str, str]:
    if not relative_paths:
        return {"status": "absent", "refs": []}
    present = [relative for relative in relative_paths
               if (root / relative).is_file()]
    return {
        "status": "present" if present else "absent",
        "refs": present,
    }


def _resolve_status(item: dict[str, Any], evidence: dict[str, Any],
                    claims_non_goal_ids: set[str]) -> str:
    non_goal_ids = [str(value) for value in item.get("non_goal_ids", [])]
    if non_goal_ids:
        return "non_goal"
    force_status = str(item.get("force_status", "") or "")
    if force_status == "not_run" or item.get("not_run_reason"):
        return "not_run"
    if force_status == "partial":
        return "partial"
    code_ok = evidence["code"]["ok"] or evidence["imports"]["ok"]
    test_ok = evidence["tests"]["ok"]
    artifact_ok = evidence["artifacts"]["ok"]
    ground_truth = evidence["ground_truth"]["status"]
    artifact_required = bool(item["probe_spec"]["artifact_paths"])
    ground_truth_required = bool(item["probe_spec"]["ground_truth_paths"])
    if (code_ok and test_ok
            and (artifact_ok or not artifact_required)
            and (ground_truth == "present" or not ground_truth_required)):
        return "implemented"
    any_evidence = bool(
        code_ok or test_ok or artifact_ok
        or evidence["cli"]["present"]
        or evidence["ground_truth"]["present"]
        or evidence["tests"]["present"])
    return "partial" if any_evidence else "missing"


def _next_action(item: dict[str, Any], status: str) -> str:
    gap_id = item["gap_id"]
    if status == "implemented":
        return (
            f"keep {gap_id} code+test evidence green; no new capability claim "
            "is made by this audit")
    if status == "non_goal":
        return (
            f"keep {gap_id} mapped to its claims non-goal ids; re-review at the "
            "quarterly claims review, never promote without new measured evidence")
    if status == "not_run":
        return (
            f"record {gap_id} as unavailable/not_run; provision the external "
            "capability before any run is claimed")
    if status == "partial":
        return (
            f"complete the missing deliverable for {gap_id} and re-run this "
            "audit; only code+test(+artifact) evidence can move it to implemented")
    return (
        f"build the {gap_id} deliverable ({item['required_deliverable']}) with "
        "tests before it appears in any readiness claim")


def load_claims_non_goal_ids(root: Path = Path(".")) -> set[str]:
    payload = _read_text(Path(root) / CLAIMS_PATH)
    try:
        claims = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        return set()
    return {
        str(entry.get("id", "")) for entry in claims.get("non_goals", [])
        if isinstance(entry, dict) and entry.get("id")
    }


def evaluate_item(item: dict[str, Any], root: Path,
                  claims_non_goal_ids: set[str]) -> dict[str, Any]:
    probe = item["probe_spec"]
    evidence = {
        "code": _file_probe(root, probe["code_paths"]),
        "imports": _import_probe(root, probe["code_paths"]),
        "tests": _test_probe(root, probe["test_paths"],
                              probe["test_markers"]),
        "artifacts": _artifact_probe(root, probe["artifact_paths"]),
        "cli": _cli_probe(root, probe["cli"]),
        "ground_truth": _ground_truth_probe(
            root, probe["ground_truth_paths"]),
        "independent_verifier": _independent_verifier_probe(
            root, probe["independent_verifier_paths"]),
    }
    status = _resolve_status(item, evidence, claims_non_goal_ids)
    evidence_refs = sorted({
        *evidence["code"]["present"],
        *evidence["imports"]["modules"],
        *evidence["tests"]["present"],
        *evidence["artifacts"]["present"],
        *[entry.split()[0] for entry in evidence["cli"]["present"]],
    })
    test_refs = sorted(set(evidence["tests"]["present"]))
    non_goal_ids = [str(value) for value in item.get("non_goal_ids", [])]
    unresolved_non_goal_ids = [
        non_goal_id for non_goal_id in non_goal_ids
        if non_goal_id not in claims_non_goal_ids
    ]
    blocker = ""
    if status in {"partial", "missing", "not_run"}:
        blocker = str(item.get("blocker_if_missing", "") or "").strip()
        if not blocker:
            blocker = "required evidence is absent from this tree"
    if status == "non_goal":
        blocker = "explicit claims non-goal; no repair capability is claimed"
    if unresolved_non_goal_ids:
        blocker = (
            f"{blocker} (WARNING: non-goal ids not in claims: "
            f"{unresolved_non_goal_ids})")
    return {
        "gap_id": item["gap_id"],
        "title": item["title"],
        "title_en": item.get("title_en", ""),
        "phase": item["phase"],
        "priority": item["priority"],
        "dependencies": list(item["dependencies"]),
        "required_deliverable": item["required_deliverable"],
        "measured_status": status,
        "evidence_refs": evidence_refs,
        "test_refs": test_refs,
        "code_probe": evidence["code"]["ok"],
        "import_probe": evidence["imports"]["ok"],
        "test_probe": evidence["tests"]["ok"],
        "artifact_probe": evidence["artifacts"]["ok"],
        "cli_probe": evidence["cli"]["ok"],
        "ground_truth": {
            "status": evidence["ground_truth"]["status"],
            "refs": evidence["ground_truth"]["present"],
        },
        "independent_verifier": evidence["independent_verifier"],
        "ground_truth_status": evidence["ground_truth"]["status"],
        "non_goal_ids": non_goal_ids,
        "unresolved_non_goal_ids": unresolved_non_goal_ids,
        "blocker": blocker,
        "next_action": _next_action(item, status),
        "capability_claim": False,
    }


def read_git_sha(root: Path) -> str:
    """Read HEAD SHA read-only (no git state change)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(root),
            capture_output=True, text=True, timeout=20, check=False,
        )
        sha = result.stdout.strip()
        if result.returncode == 0 and sha:
            return sha
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def build_readiness(root: Path | str = ".",
                    generated_from_sha: str | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    claims_non_goal_ids = load_claims_non_goal_ids(root_path)
    items = [evaluate_item(item, root_path, claims_non_goal_ids)
             for item in READINESS_ITEMS]
    summary = {status: 0 for status in STATUSES}
    for item in items:
        summary[item["measured_status"]] += 1
    not_run = [
        {"gap_id": item["gap_id"], "reason": item["blocker"]}
        for item in items if item["measured_status"] == "not_run"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "audit_date": AUDIT_DATE,
        "generated_by": "scripts/audit_repair_readiness.py",
        "generated_from_sha": (generated_from_sha
                               if generated_from_sha is not None
                               else read_git_sha(root_path)),
        "repo_root": ".",
        "probe_mode": "read-only (no repair, no network, no provider/AI, no benchmark/PoC execution)",
        "items": items,
        "summary": {"total": len(items), **summary},
        "capability_claims": [],
        "limitations": [
            "probes are static file/string/import-spec checks; they do not run "
            "the repair pipeline, providers, benchmarks or PoCs",
            "an item is implemented only by code+test(+artifact/ground-truth) "
            "evidence; documentation/contracts/registry paths cap it at partial",
            "generated_from_sha is read from git rev-parse HEAD and makes the "
            "artifact tree-specific",
            "capability space outside the measured universe is not enumerable "
            "here and stays an explicit limitation",
        ],
        "not_run": not_run,
        "capability_claims_note": (
            "no new repair capability is claimed and no verified state is "
            "upgraded by this audit"),
    }


def render_readme(document: dict[str, Any]) -> str:
    summary = document["summary"]
    lines = [
        "# Phase-8A repair readiness baseline (2026-11-16)",
        "",
        "Read-only evidence audit of the 30 Phase-8 user requirements "
        "(G01-G30). It does not run repair, providers, benchmarks or PoCs, and "
        "it claims no new repair capability and upgrades no verified state.",
        "",
        f"- generated_from_sha: `{document['generated_from_sha']}`",
        f"- total items: **{summary['total']}**",
        "- status counts: " + ", ".join(
            f"{status}={summary[status]}" for status in STATUSES),
        "",
        "| id | title | phase | priority | status | code | test | artifact | "
        "ground truth | blocker |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in document["items"]:
        lines.append(
            "| {gap_id} | {title} | {phase} | {priority} | {status} | "
            "{code} | {test} | {artifact} | {gt} | {blocker} |".format(
                gap_id=item["gap_id"],
                title=item.get("title_en") or item["title"],
                phase=item["phase"], priority=item["priority"],
                status=item["measured_status"],
                code="yes" if item["code_probe"] else "no",
                test="yes" if item["test_probe"] else "no",
                artifact="yes" if item["artifact_probe"] else "no",
                gt=item["ground_truth_status"],
                blocker=item["blocker"] or "-",
            ))
    lines.extend([
        "",
        "Hard evidence rule: implemented requires code probe + test probe "
        "(+ artifact/ground truth when declared); contract/registry/documentation "
        "only caps an item at partial; absent evidence is missing; an unavailable "
        "external capability is not_run; the 12 claims non-goals are non_goal.",
        "",
        "Regenerate with `python scripts/audit_repair_readiness.py --write`; "
        "verify with `--check` (deterministic recomputation + SHA256SUMS).",
        "",
    ])
    return "\n".join(lines)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def artifact_payload(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "readiness.json": _canonical_json(document),
        "README.md": render_readme(document),
    }


def write_artifacts(document: dict[str, Any],
                    artifact_dir: Path) -> dict[str, Any]:
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)
    payload = artifact_payload(document)
    hashes: dict[str, str] = {}
    for name, content in payload.items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    sums_lines = [f"{hashes[name]}  {name}" for name in sorted(hashes)]
    sums_path = target / "SHA256SUMS"
    sums_path.write_text("\n".join(sums_lines) + "\n", encoding="utf-8")
    return {"artifact_dir": str(target), "sha256": hashes,
            "sums_sha256": hashlib.sha256(sums_path.read_bytes()).hexdigest()}


def validate_document(document: Any,
                      root: Path | str = ".") -> list[str]:
    """Fail-closed validation of a readiness document (used by --check/tests)."""
    violations: list[str] = []
    if not isinstance(document, dict):
        return ["readiness document is not an object"]
    if document.get("schema_version") != SCHEMA_VERSION:
        violations.append("schema_version mismatch")
    if document.get("kind") != KIND:
        violations.append(f"kind must be {KIND!r}")
    if document.get("capability_claims") != []:
        violations.append("capability_claims must be [] (no new capability claim)")
    if "本轮不新增修复能力" not in str(document.get("capability_claims_note", "")) \
            and "no new repair capability" not in str(
                document.get("capability_claims_note", "")):
        violations.append("capability_claims_note must state no new capability")
    items = document.get("items")
    if not isinstance(items, list) or len(items) != 30:
        return violations + ["items must contain exactly 30 entries"]
    ids = [str(item.get("gap_id", "")) for item in items]
    if ids != list(GAP_IDS):
        violations.append("items must be G01..G30 in order without duplicates")
    summary = document.get("summary") if isinstance(
        document.get("summary"), dict) else {}
    if summary.get("total") != 30:
        violations.append("summary.total must be 30")
    counts = {status: 0 for status in STATUSES}
    claims_non_goal_ids = load_claims_non_goal_ids(Path(root))
    for item in items:
        gap_id = str(item.get("gap_id", "?"))
        status = str(item.get("measured_status", ""))
        if status not in STATUSES:
            violations.append(f"{gap_id}: invalid status {status!r}")
            continue
        counts[status] += 1
        for field in ("title", "phase", "priority", "dependencies",
                      "required_deliverable", "evidence_refs", "test_refs",
                      "ground_truth", "independent_verifier", "blocker",
                      "next_action"):
            if field not in item:
                violations.append(f"{gap_id}: missing field {field}")
        if item.get("capability_claim") is not False:
            violations.append(f"{gap_id}: capability_claim must be false")
        if item.get("phase") not in PHASES:
            violations.append(f"{gap_id}: invalid phase")
        if item.get("priority") not in PRIORITIES:
            violations.append(f"{gap_id}: invalid priority")
        if status in {"partial", "missing", "not_run"} and not str(
                item.get("blocker", "") or "").strip():
            violations.append(f"{gap_id}: {status} item needs a blocker")
        if not str(item.get("next_action", "") or "").strip():
            violations.append(f"{gap_id}: next_action is required")
        if status == "implemented":
            if item.get("code_probe") is not True:
                violations.append(
                    f"{gap_id}: fabricated implemented (code_probe false)")
            if item.get("test_probe") is not True:
                violations.append(
                    f"{gap_id}: fabricated implemented (test_probe false)")
            spec = (_ITEM_BY_ID.get(gap_id) or {}).get("probe_spec", {})
            artifact_required = bool(spec.get("artifact_paths"))
            gt_required = bool(spec.get("ground_truth_paths"))
            if artifact_required and item.get("artifact_probe") is not True:
                violations.append(
                    f"{gap_id}: implemented requires artifact evidence")
            if gt_required and item.get("ground_truth_status") != "present":
                violations.append(
                    f"{gap_id}: implemented requires ground truth evidence")
        if status == "non_goal":
            non_goal_ids = [str(value) for value in item.get("non_goal_ids", [])]
            if not non_goal_ids:
                violations.append(f"{gap_id}: non_goal item must map claims ids")
            unresolved = [value for value in non_goal_ids
                          if value not in claims_non_goal_ids]
            if unresolved:
                violations.append(
                    f"{gap_id}: non_goal ids not in claims: {unresolved}")
        if status == "not_run":
            reason = str(item.get("blocker", "") or "")
            if not reason:
                violations.append(f"{gap_id}: not_run item needs an explicit reason")
    for status in STATUSES:
        if summary.get(status) != counts[status]:
            violations.append(
                f"summary.{status}={summary.get(status)} != recomputed "
                f"{counts[status]}")
    if any(item.get("gap_id") == "G29" for item in items):
        g29 = next(item for item in items if item.get("gap_id") == "G29")
        if g29.get("measured_status") != "not_run":
            violations.append("G29 hidden benchmark must be not_run")
        if "hidden_available=false" not in str(g29.get("blocker", "")):
            violations.append(
                "G29 must record hidden_available=false evidence")
    return violations
