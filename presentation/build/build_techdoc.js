// Riptide Attest — Technical Documentation (DOCX), in the register and
// structure of the RIA Technical Documentation: plain, declarative, every
// claim names the file that proves it.
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, AlignmentType, BorderStyle, ShadingType, ImageRun, PageBreak, LevelFormat,
} = require("docx");
const fs = require("fs");

const NAVY = "0A1628", INK = "1A1A2E", BODY = "334155", TEAL = "007A6A", TEALB = "00C9B1";
const AMBER = "B45309", SLATE = "5B6B7C", BORDER = "D9E1E7", CODEBG = "F1F5F9", RED = "B23A3A";
const ASSETS = "assets/";
const OUT = "out/";
const F = "Inter", FC = "Consolas";

const p = (text, o = {}) => new Paragraph({
  children: Array.isArray(text) ? text : [new TextRun({ text, font: F, size: o.size || 21, color: o.color || BODY, bold: o.bold, italics: o.italics })],
  spacing: { after: o.after == null ? 160 : o.after, line: 276 },
  alignment: o.align, numbering: o.numbering,
});
const r = (text, o = {}) => new TextRun({ text, font: o.font || F, size: o.size || 21, color: o.color || BODY, bold: o.bold, italics: o.italics });
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 420, after: 200 },
  children: [new TextRun({ text, font: F, size: 32, bold: true, color: NAVY })] });
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 160 },
  children: [new TextRun({ text, font: F, size: 25, bold: true, color: INK })] });
const code = (lines) => lines.map((l, i) => new Paragraph({
  children: [new TextRun({ text: l === "" ? " " : l, font: FC, size: 18, color: INK })],
  shading: { type: ShadingType.CLEAR, fill: CODEBG },
  spacing: { after: i === lines.length - 1 ? 200 : 0, line: 240 },
  indent: { left: 240, right: 240 },
}));
const bullets = (items) => items.map(t => new Paragraph({
  children: (Array.isArray(t) ? t : [r(t)]),
  numbering: { reference: "bul", level: 0 }, spacing: { after: 80, line: 276 },
}));

function tbl(rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const bord = { style: BorderStyle.SINGLE, size: 4, color: BORDER };
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((cells, ri) => new TableRow({
      children: cells.map((c, ci) => new TableCell({
        width: { size: widths[ci], type: WidthType.DXA },
        shading: ri === 0 ? { type: ShadingType.CLEAR, fill: NAVY } : (ri % 2 === 0 ? { type: ShadingType.CLEAR, fill: "F8FAFC" } : undefined),
        borders: { top: bord, bottom: bord, left: bord, right: bord },
        margins: { top: 90, bottom: 90, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: String(c), font: F, size: 19, color: ri === 0 ? "FFFFFF" : BODY, bold: ri === 0 })], spacing: { after: 0, line: 252 } })],
      })),
    })),
  });
}
const img = (path, w, h) => new Paragraph({
  children: [new ImageRun({ type: "png", data: fs.readFileSync(path), transformation: { width: w, height: h } })],
  spacing: { before: 120, after: 120 }, alignment: AlignmentType.CENTER,
});
const caption = (t) => p(t, { size: 18, color: SLATE, italics: true, after: 240, align: AlignmentType.CENTER });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

const children = [];

// ================= COVER =================
children.push(
  new Paragraph({ spacing: { before: 2400, after: 100 }, children: [
    new TextRun({ text: "RIPTIDE ", font: F, size: 30, bold: true, color: NAVY }),
    new TextRun({ text: "ATTEST", font: F, size: 30, bold: true, color: TEAL }) ] }),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "Technical Documentation", font: F, size: 64, bold: true, color: NAVY })] }),
  p("Architecture, launch guide, engine walkthrough, guardrails and security model, and the reasoning behind every load-bearing decision. Written for engineering, security, and architecture reviewers; every claim names the file that proves it.", { size: 23, after: 300 }),
  p([r("Repository: ", { size: 21 }), r("github.com/riptide-consulting/riptide-attest", { font: FC, size: 20, color: TEAL })], { after: 80 }),
  p([r("Companion system: ", { size: 21 }), r("Riptide RIA -- RIA writes the opinion; Attest carries the proof.", { size: 21, italics: true })], { after: 300 }),
  p("Riptide Consulting  ·  Carlsbad, CA  ·  July 2026", { size: 21, color: SLATE }),
  pageBreak(),
);

// ================= CONTENTS =================
children.push(h1("Contents"));
[
  "1. System overview", "2. Launch guide", "3. Logical architecture",
  "4. The engine, module by module", "5. The gates, in code",
  "6. The model layer", "7. Guardrails and security model",
  "8. Why the decisions were made", "9. Data flows and security summary",
  "10. Appendix: dependencies and repository map",
].forEach(t => children.push(p(t, { size: 22, after: 90 })));
children.push(pageBreak());

// ================= 1. SYSTEM OVERVIEW =================
children.push(h1("1. System overview"));
children.push(p("Riptide Attest is a deterministic compliance-verification engine, and the deliberate inversion of its sibling, Riptide RIA. RIA is a governed probabilistic pipeline: models write opinions on every run, code applies the rules, and a human holds the key. Attest confines judgment to authoring time: a model compiles each control into a formal specification exactly once, a named human reviews and approves that specification by pinning its SHA-256 hash, and from then on a pure engine verifies it forever. Same evidence, same verdict, byte for byte, on any machine."));
children.push(p("Attest consumes RIA's output. A RIA briefing ends in a remediation plan -- actions, owners, due dates. Attest's triage verb reads that plan, routes the machine-checkable actions into compilation, and returns the rest to the human tracker. From there, each approved control is re-verified on every scheduled run at zero marginal model cost: judgment is bought once, at authoring; verification is pure code."));
children.push(p("The design thesis, in one sentence: the model compiles intent once; a deterministic engine verifies forever. Where RIA's hard problem was trusting judgment enough to let it recommend, Attest's hard problem is reproducing execution exactly -- and the entire architecture is organized around making that reproducibility a tested, enforced property rather than an aspiration."));
children.push(p([
  r("Everything consequential is asserted by code the reader can run: 234 offline tests complete in under two seconds ("),
  r("tests/unit/", { font: FC, size: 19 }),
  r("), and the demo ("),
  r("run_demo.py", { font: FC, size: 19 }),
  r(") asserts nine claims -- the approval gate, byte-identical re-runs, tamper refusal, drift detection, replay -- and exits nonzero if any fails. The demo is offline and spends no model dollars; needing a network or an API key to pass a test is itself classified as a bug."),
]));

// ================= 2. LAUNCH GUIDE =================
children.push(h1("2. Launch guide"));
children.push(h2("2.1 Prerequisites"));
children.push(p("Python 3.11 or newer and git. Nothing else is required for the runtime verbs or the demo: the engine is standard-library-only by tested contract. An Anthropic API key is needed only for the three authoring verbs (triage, compile, explain), which run once per control."));
children.push(h2("2.2 Setup (one time per machine)"));
children.push(...code([
  "git clone https://github.com/riptide-consulting/riptide-attest",
  "cd riptide-attest",
  "python -m venv .venv",
  ".venv\\Scripts\\pip install pytest        (Windows; runtime needs nothing else)",
  ".venv/bin/pip install pytest              (macOS / Linux)",
  "",
  "# authoring verbs only:",
  "copy .env.example .env                    then add ANTHROPIC_API_KEY",
]));
children.push(p([
  r("The "), r(".env", { font: FC, size: 19 }),
  r(" file also carries the model routing policy (MODEL_TRIAGE, MODEL_COMPILER, MODEL_EXPLAINER). All ids are pinned snapshots; changing them is an operator decision per the root "),
  r("CLAUDE.md", { font: FC, size: 19 }), r(", never a hardcoded fallback."),
]));
children.push(h2("2.3 Running it"));
children.push(...code([
  "python run_demo.py            the one-command demo: offline, self-verifying,",
  "                              exit code 0 only if all nine assertions hold",
  "run_demo.bat                  the Windows double-click form of the same",
  "",
  "python -m pytest tests/ -q    the full offline suite: 234 tests, under 2 s",
]));
children.push(p("The operational verbs follow the control lifecycle rather than a pipeline; each supports --json for machine-readable stdout with diagnostics on stderr:"));
children.push(...code([
  "python main.py triage <plan.json>                  model: attestable or not",
  "python main.py compile <action.json> --out <spec>  model: draft CheckSpec",
  "python main.py explain <spec.json>                 model: plain-language packet",
  "python main.py approve <spec.json> --by <name>     human: pin the hash",
  "python main.py snapshot --specs ... --target <dir> code: freeze evidence",
  "python main.py evaluate --specs ... --snapshot <id> code: attestation",
  "python main.py replay <attestation.json>           code: re-derive, assert bytes",
  "python main.py diff <att-a> <att-b>                code: drift report",
  "python main.py publish <attestation.json>          code: gated external write",
]));
children.push(h2("2.4 Exit codes and what they mean"));
children.push(p("The exit-code contract is pinned by tests (tests/unit/test_cli.py), because operators wire alerting to it:"));
children.push(tbl([
  ["Code", "Meaning", "Alerting interpretation"],
  ["0", "Success; for evaluate, the rollup is pass", "Quiet"],
  ["2", "Evaluate completed; rollup is fail or unknown", "A finding, not an error: a control is not enforced. The output names the failing check, its predicate, and the observed value."],
  ["1", "Replay mismatch", "The world or the inputs changed since the original run -- investigate drift"],
  ["3", "Refused", "Approval missing, spec invalid, or an integrity self-check failed (tampered evidence, snapshot, or attestation). One-line refusal, never a traceback. Distinct from 1 so tampering is never mistaken for drift."],
], [900, 2900, 5560]));
children.push(p("", { after: 60 }));
children.push(h2("2.5 Troubleshooting"));
children.push(p("Format: symptom, cause, resolution. Several of these are the system working as designed -- refusals are features with error messages."));
children.push(tbl([
  ["Symptom", "Cause and resolution"],
  ["ApprovalError: spec ... is not in the approval registry", "The spec was edited after approval (the pin is the hash of content), or never approved. This is the design. Re-review and re-approve: python main.py approve <spec> --by <name>."],
  ["TamperError: object store integrity failure", "A stored evidence object no longer hashes to its address: it was modified after collection. The engine refuses it at the moment of use. Recollect the snapshot; investigate who touched the store."],
  ["refused: attestation ... fails its self-check (exit 3)", "The attestation file was edited after writing. Recover from backup or re-evaluate -- determinism means the regenerated file is byte-identical to what the original was."],
  ["refused: ATTEST_PUBLISH_APPROVED is not set (exit 3)", "The human key for the one external effect. If a human has decided to publish, set ATTEST_PUBLISH_APPROVED=1 for that shell and re-run. Deliberately never stored in a config file."],
  ["evaluate exits 2", "Not an error: a control is failing. The output names each failing check and its detail string. Fix the control in the target system, re-snapshot, re-evaluate."],
  ["replay exits 1 with 'inputs, engine version, or approvals have changed'", "The re-derivation does not byte-match: stored artifacts moved, the engine version changed, or an approval was revoked (withdrawn authority does not re-verify, loudly and on purpose)."],
], [3560, 5800]));

// ================= 3. LOGICAL ARCHITECTURE =================
children.push(pageBreak());
children.push(h1("3. Logical architecture"));
children.push(p("Sections 4 through 7 describe one implementation. This section describes the system that implementation instantiates: capabilities named for what they do, the contracts between them, the invariants any implementation must hold, and the ports through which every external dependency attaches. Nothing here names a vendor, a product, or a model, by construction -- the constraint that makes the design reviewable independently of its stack, and portable to another one."));
children.push(img(ASSETS + "Riptide-Attest-logical-architecture.png", 620, 364));
children.push(caption("Figure 1. The logical architecture. Judgment above the line, determinism below, a human between them. The Reasoning Port attaches only to authoring; no path exists from it to the runtime row."));
children.push(img(ASSETS + "Riptide-Attest-control-lifecycle.png", 620, 210));
children.push(caption("Figure 2. A control's lifecycle. Authoring spends model dollars once; the approval pin arms the spec; the runtime verbs are pure code, free forever."));
children.push(h2("3.1 The invariants"));
children.push(p("Nine properties, each the acceptance criterion a review board can test, each named with its enforcing code and its proving test:"));
children.push(tbl([
  ["#", "Invariant", "Enforced by", "Proven by"],
  ["1", "The compiler cannot execute", "require_approved() inside evaluate_specs()", "test_evaluator.py"],
  ["2", "Only hash-approved specs run; an edit voids approval", "The pin is the canonical SHA-256 of content (registry.py)", "test_snapshot_and_registry.py"],
  ["3", "Evaluation is pure: no clock, randomness, network, environment, or model SDK", "Package discipline + the purity wall", "test_purity.py (AST scan, alias-aware)"],
  ["4", "Same snapshot + same specs = the same bytes", "canonical.py encoding rules; no wall clock in any body", "test_determinism.py + golden files + CI"],
  ["5", "Every verdict replays", "One content-addressed store for evidence, specs, manifests", "test_determinism.py (replay)"],
  ["6", "Evidence is content-addressed; tamper is visible at use", "ObjectStore.get() re-hashes every read", "tamper tests + the demo"],
  ["7", "External effects require the human key at the write", "_require_approval() inside publish_attestation()", "test_cli.py"],
  ["8", "Model spend exists only at authoring", "Lazy imports; engine import wall", "test_purity.py"],
  ["9", "Missing evidence fails closed", "unknown -> fail rollup unless a human pinned report-only", "test_evaluator.py"],
], [420, 2680, 3360, 2900]));
children.push(h2("3.2 Ports"));
children.push(p("Two structural absences do the security work: the compiler cannot fetch (authoring holds no evidence tools), and the engine cannot reason (the Reasoning Port does not attach to the runtime row). Everything else is an adapter behind a fixed contract: the demo's filesystem evidence adapter stands where cloud-configuration APIs, IAM exports, or SIEM queries stand in an enterprise deployment; the Notion tracker stands where ServiceNow or Jira stands; swapping any of them changes no governance code, because none of the governance lives in the integration layer."));

// ================= 4. ENGINE =================
children.push(pageBreak());
children.push(h1("4. The engine, module by module"));
children.push(p([
  r("Everything in "), r("attest/engine/", { font: FC, size: 19 }),
  r(" is a deterministic function of its arguments and the bytes in the state directory. The package imports nothing beyond the standard library, and within it: no clock, no randomness, no network, no environment, no model SDK. The engine may parse timestamps; it may never ask what time it is. It may read files; it may never read the environment."),
]));
children.push(h2("4.1 canonical.py -- one byte encoding, one hash"));
children.push(p("Every artifact passes through canonical serialization before it is hashed or written: UTF-8, NFC-normalized strings (keys and values), keys sorted by code point, minimal separators, NaN and Infinity rejected, duplicate keys after normalization rejected, non-JSON types rejected rather than coerced. Coercion is a hiding place for nondeterminism; rejection is a named error at the boundary."));
children.push(h2("4.2 predicates.py -- the verdict algebra"));
children.push(p("Sixteen leaf predicates and four combinators are the entire vocabulary a spec can use. The algebra is stated once: fail dominates unknown dominates pass. 'not' swaps pass and fail but preserves unknown -- ignorance does not invert. Existence checks are the only predicates with an opinion about missing evidence; every other predicate returns unknown for MISSING, and unknown becomes fail at the rollup unless a human explicitly approved report-only. Time enters exactly once: max_age_days measures evidence timestamps against the snapshot's own collected_at, so re-evaluating a five-year-old snapshot yields the verdict it yielded on day one."));
children.push(h2("4.3 snapshot.py -- content-addressed evidence"));
children.push(p("One object store holds evidence bodies, approved specs, and manifests, all by canonical SHA-256. Reads re-hash: content that does not match its address raises TamperError at the moment of use. Evidence that parses but cannot be canonicalized (Infinity smuggled as 1e999, NFC-colliding keys) becomes an error record -- and an error record becomes an unknown verdict, which fails closed. Bad evidence is a finding, never a crash and never a silent pass."));
children.push(h2("4.4 registry.py -- the approval gate"));
children.push(...code([
  "def require_approved(spec: dict, registry: dict) -> str:",
  '    """The gate. Returns the spec hash or raises."""',
  "    digest = hash_obj(spec)",
  "    if digest not in registry.get(\"approved\", {}):",
  "        raise ApprovalError(",
  "            f\"spec {digest[:16]} ... is not in the approval registry --",
  "            refusing to evaluate. Any edit to a spec voids its approval;",
  "            a human must re-approve with: main.py approve <spec> --by <name>\"",
  "        )",
  "    return digest",
]));
children.push(p("Three properties. The pin is the hash of the whole content, so approval of 'whatever the compiler produces next' is inexpressible. The check runs inside the evaluation path, at the point of use, so no refactor of calling code can forget it -- the identical placement argument as RIA's _require_approval(). And revocation is deletion: remove the hash and the spec stops executing on the next run, while its past attestations stop replaying, loudly, because a verdict whose authority was withdrawn should not re-verify."));
children.push(h2("4.5 evaluator.py, report.py, replay.py, diffing.py"));
children.push(p("The evaluator maps (approved specs, manifest, store) to per-check verdicts, citing every evidence item by hash. The attestation body carries no wall-clock timestamp -- the snapshot's collected_at is its notion of time -- and its id is the canonical hash of its body, so the artifact carries its own proof. Replay walks the chain of custody: attestation self-check, manifest by cited hash, each spec by cited hash, approval re-check, full re-evaluation, byte comparison. Drift is a deterministic diff of two attestations: verdict transitions, evidence changes by hash, controls added or removed. 'What changed between Monday and Friday' has exactly one answer."));

// ================= 5. GATES =================
children.push(h1("5. The gates, in code"));
children.push(p("Attest has exactly two authorization moments, and both are human by construction."));
children.push(p([r("The execution gate", { bold: true, color: NAVY }), r(" is section 4.4's registry pin: nothing evaluates without a named human's hash. It moved from RIA's per-run environment key to a durable, content-bound, version-controlled record because Attest approves an artifact that will execute forever, not a run that ends.")]));
children.push(p([r("The effect gate", { bold: true, color: NAVY }), r(" guards the one external write. Verbatim from "), r("attest/publish.py", { font: FC, size: 19 }), r(":")]));
children.push(...code([
  "def _require_approval() -> None:",
  "    if os.environ.get(\"ATTEST_PUBLISH_APPROVED\", \"\").strip().lower() \\",
  "            not in (\"1\", \"true\"):",
  "        raise PermissionError(",
  "            \"ATTEST_PUBLISH_APPROVED is not set -- refusing to publish",
  "            the attestation externally. Set ATTEST_PUBLISH_APPROVED=1 to",
  "            explicitly approve this external side effect.\")",
]));
children.push(p("The check lives inside the function that performs the write, at the moment of the write, after the attestation's own self-check -- so no refactor can forget it and no tampered artifact can ride an approved publish. The key is read from the environment per run and deliberately never stored in configuration. Producing attestations locally is reversible and therefore ungated; leaving the environment is not, and therefore is."));

// ================= 6. MODEL LAYER =================
children.push(h1("6. The model layer"));
children.push(p("Three agents, all at authoring time, each with a scoped specification (agents/<name>/CLAUDE.md), forced tool use (the API must return a schema-conforming tool call; free text is never parsed), untrusted-content framing around any externally-sourced text, and a deterministic post-processing backstop."));
children.push(tbl([
  ["Agent", "Model", "Mission", "Backstop"],
  ["Triage", "Haiku 4.5", "Classify each remediation action: machine-attestable or human-tracked", "confidence < 0.7 forces attestable = false -- uncertainty routes to humans, never to automation"],
  ["Compiler", "Opus 4.8", "One action -> one draft CheckSpec. The trust boundary: a wrong spec produces wrong attestations forever", "Grammar validation rejects rather than repairs; on_unknown forced to fail; the draft is inert until a human pins it"],
  ["Explainer", "Haiku 4.5", "Spec -> plain language for the approval packet", "Labeled advisory; holds no authority; never quoted into a verdict"],
], [1100, 1100, 3480, 3680]));
children.push(p("", { after: 60 }));
children.push(p("The compiler is evaluated the way it deserves: deterministically. Each eval case pairs a control text with evidence known to satisfy the control and evidence known to violate it; the compiled spec is executed against both, and the grade is whether the verdicts match ground truth. A spec that passes the violating evidence means the compiler weakened the control -- automatic failure. The injection suite (evaluations/injection/) applies the same grading to hostile control texts; the deterministic engine, not a model judge, decides whether the attack worked."));

// ================= 7. GUARDRAILS & SECURITY =================
children.push(pageBreak());
children.push(h1("7. Guardrails and security model"));
children.push(h2("7.1 Threat model"));
children.push(tbl([
  ["Threat", "Vector", "Containment"],
  ["Prompt injection", "Hostile instructions embedded in regulatory or remediation text reaching the compiler", "Untrusted-content framing; forced schema; grammar that cannot express fail-open; injection evals graded by execution; and the bound that matters -- a fooled compiler yields only an inert draft a human must pin"],
  ["Evidence tampering", "Stored evidence modified after collection to flip a verdict", "Content addressing: every read re-hashes; mismatch is refused at the moment of use (TamperError), and replay exposes historical tampering"],
  ["Spec tampering", "An approved spec edited to weaken a control", "The approval is the hash of content; any edit voids it and evaluation refuses"],
  ["Report forgery", "An attestation file edited after the fact", "The attestation id is the hash of the body; load_attestation() self-checks and refuses (exit 3, distinct from drift's exit 1)"],
  ["Engine contamination", "Nondeterminism or network reach introduced into the core", "The purity wall: alias-aware AST scan on every push; dynamic import machinery banned outright; a fail-open development hook as tripwire; CI as re-proof"],
  ["Authority forgery", "An agent or model writing approvals or publishing externally", "The registry is written by one human verb and only read by the engine; the publish key is checked inside the write; agent tooling is hook-audited"],
  ["Silent absence", "A control whose evidence quietly stops being collected", "Fail-closed: unreadable, missing, or wrong-typed evidence is unknown, and unknown escalates to fail unless a human pinned report-only"],
], [1700, 3080, 4580]));
children.push(h2("7.2 The purity wall, three layers deep"));
children.push(p("Layer 1, the wall: tests/unit/test_purity.py parses the syntax tree of every engine module on every push -- forbidden modules under any alias, from-imports of dangerous names (from os import getenv), clock calls through aliased chains (from datetime import datetime as dt; dt.now()), and dynamic import machinery (importlib, __import__, exec, eval, string-literal getattr) banned outright. The scanner is itself tested against each of these bypass shapes, because a wall is only a wall once someone has tried to walk through it."));
children.push(p("Layer 2, the tripwire: a development-time hook blocks an agent's edit that would introduce a forbidden pattern into the engine before it lands -- and fails open on its own internal errors, deliberately. A guard that crashes on odd input teaches operators to disable guards; the layer that cannot be removed is the wall behind it."));
children.push(p("Layer 3, the re-proof: CI runs the wall as its own named step, then runs the demo twice and byte-compares attestations -- on Linux, against goldens frozen on Windows. Cross-platform byte-stability is a checked claim on every push."));
children.push(h2("7.3 The adversarial review, on the record"));
children.push(p("Before first commit, the build was attacked by a 59-agent review: five skeptic lenses (platform determinism, fail-open hunting, gate bypass, model layer, coverage and documentation accuracy), every finding judged by three independent refuters, surviving only on majority. Eighteen raw findings; eleven confirmed; eleven fixed, each with a regression test. Among them: the purity wall's six bypass shapes, a fail-open length predicate satisfied by a two-character string where 'two approvers' was meant, RFC 6901 violations on non-ASCII digits, and hostile-but-parseable evidence that could crash a snapshot instead of failing closed. The full record, including what was claimed and refuted, ships in the repository (scratchpad/ADVERSARIAL-REVIEW.md) -- the process is part of the product."));
children.push(h2("7.4 Honest residual risk"));
children.push(p("The compiler can mis-formalize intent: a spec can be well-formed, approved, and still check the wrong thing. This is the residual risk of compile-once, and it is why the human approves with a dry-run and a plain-language explanation in hand, and why the eval suite grades compilation by execution against ground truth. Reach equals adapters: 'enforced' means enforced in systems an evidence adapter reads, and unwired systems are invisible -- fail-closed makes those gaps loud rather than silent. Snapshots are instants: between runs the world can move; run frequency is the operator's dial. None of these are assumed away; each is watched by a mechanism named above."));

// ================= 8. DECISIONS =================
children.push(h1("8. Why the decisions were made"));
const qa = [
  ["Why compile-once instead of judge-every-run?", "Because verification must be reproducible to be worth anything in front of an auditor, and probabilistic judgment on every run cannot be. Confining the model to authoring buys determinism, replay, and zero marginal cost -- and costs one honest limitation (mis-formalization), which the approval packet and the eval suite exist to contain."],
  ["Why is approval a hash pin instead of an environment key?", "RIA approves a run; the key dies with the shell. Attest approves an artifact that executes forever, so the authority record must be durable, content-bound, and versioned. The hash pin is all three, and it makes 'approve whatever comes next' inexpressible."],
  ["Why does the engine forbid even datetime.now?", "A verdict that depends on when you ask is not a verdict; it is an opinion with a timestamp. The evaluator's only clock is the snapshot's collected_at, so every attestation is re-derivable years later, byte for byte. The AST wall makes this a property of the codebase, not a discipline of its authors."],
  ["Why fail-closed on missing evidence?", "Because the alternative -- silence reading as compliance -- is how verification systems rot. An adapter that breaks, a path that moves, a file that stops parsing: each becomes unknown, then fail, then a finding somebody owns. A human can relax a specific spec to report-only; the compiler cannot."],
  ["Why can't the compiler emit report-only specs?", "A model under injection pressure must not hold the pen that weakens verdicts. on_unknown: 'report' exists for humans -- deliberate, reviewed, hash-pinned; the compiler layer forces fail on every draft."],
  ["Why no autonomy tiers, when RIA has three?", "RIA's output is judgment that might act, so it computes an authorization. Attest's output is a fact about the world; facts are not permissions. The two authorization moments that exist -- what may run, what may leave -- are human by construction, not computed."],
  ["Why plain Python, no orchestration framework?", "The runtime is a state machine over files; plain code expresses it readably. Every dependency added to the engine would be surface the purity wall has to police -- so the engine has none, and the complexity budget went to governance."],
];
qa.forEach(([q, a]) => {
  children.push(p(q, { bold: true, color: NAVY, size: 22, after: 80 }));
  children.push(p(a, { after: 220 }));
});

// ================= 9. DATA FLOWS =================
children.push(h1("9. Data flows and security summary"));
children.push(p("Inputs: a RIA remediation plan (or any control source behind the port), and evidence read from operator-scoped adapters into a local content-addressed store. No PHI is in scope by design: evidence describes how systems are configured to handle regulated data -- retention values, encryption flags, timeout settings -- never the data itself."));
children.push(p("What leaves the environment: at authoring time only, the control text and scoped policy excerpts go to the model API (Anthropic's API, or Claude via AWS Bedrock or Google Vertex AI inside the client's tenancy). At runtime, nothing -- verification is local computation over local artifacts. The single gated exception is publishing an attestation record to the tracker, which requires the human key at the moment of the write."));
children.push(p("Outputs: attestations and drift reports as canonical JSON (the record), optional DOCX renderings (a convenience carrying no byte-stability claim), and append-only JSONL logs carrying hashes rather than payloads, SIEM-ready under retention schedules already in force."));

// ================= 10. APPENDIX =================
children.push(h1("10. Appendix: dependencies and repository map"));
children.push(tbl([
  ["Package", "Version", "Role", "Reaches the engine?"],
  ["anthropic", "0.116.0", "Authoring verbs only (lazy-imported)", "Never -- purity test fails the build"],
  ["python-dotenv", "1.2.2", "Model-layer settings", "Never"],
  ["mcp", "1.28.1", "Read-only evidence adapter server", "Never"],
  ["notion-client", "3.1.0", "Gated tracker publish", "Never"],
  ["python-docx", "1.2.0", "Optional rendering", "Never"],
  ["pytest / ruff", "9.1.1 / 0.15.21", "The 234 tests; lint -- both gate CI", "Test-side only"],
], [1700, 1300, 3680, 2680]));
children.push(p("", { after: 120 }));
children.push(...code([
  "main.py                 CLI: the lifecycle verbs; exit-code contract",
  "run_demo.py / .bat      self-verifying demo; exit code is the proof",
  "attest/engine/          the pure core: canonical - pointer - predicates -",
  "                        schema - snapshot - registry - evaluator - report -",
  "                        replay - diffing",
  "attest/                 collect (the one clock read) - audit - publish -",
  "                        triage - compiler - explainer - model_client - rendering",
  "agents/*/CLAUDE.md      scoped per-agent specifications",
  "specs/ registry/        compiled specs - the approval registry (hash pins)",
  "fixtures/               simulated target system - RIA plan - recorded triage",
  "tests/unit/ + golden/   234 offline tests - frozen byte-exact goldens",
  "evaluations/            compiler evals graded by execution - injection suite",
  "mcp_servers/            evidence_fs (read-only) - attest_tracker (gated)",
  ".claude/ .github/       purity + audit hooks - CI (tests, purity wall,",
  "                        double-demo byte comparison on Linux)",
  "docs/ scratchpad/       architecture - grammar - determinism - decisions -",
  "                        runbook - CCAF mapping - the adversarial review record",
]));
children.push(p([
  r("Suggested reading order for a technical reviewer: the README's top half for the thesis; "),
  r("run_demo.py", { font: FC, size: 19 }), r(" output for the nine assertions; "),
  r("attest/engine/registry.py", { font: FC, size: 19 }), r(" for the gate; "),
  r("attest/engine/canonical.py", { font: FC, size: 19 }), r(" for the byte-stability rules; "),
  r("evaluations/", { font: FC, size: 19 }), r(" for judgment graded by execution; and "),
  r("docs/DESIGN-DECISIONS.md", { font: FC, size: 19 }), r(" for the reasoning."),
]));

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", style: { paragraph: { indent: { left: 480, hanging: 240 } } } }] }] },
  styles: { default: { document: { run: { font: F, size: 21, color: BODY } } } },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1200, bottom: 1200, left: 1320, right: 1320 } } },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(OUT + "Riptide-Attest-Technical-Documentation.docx", buf);
  console.log("docx written:", buf.length, "bytes");
});
