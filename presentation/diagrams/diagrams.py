"""Riptide Attest architecture diagrams, in the house style of the RIA
logical-architecture PNG: navy judgment boxes, white deterministic boxes,
teal-outlined ports, amber control points and human authority."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

NAVY = "#0F1E35"
DEEP = "#0A1628"
TEAL = "#00C9B1"
TEAL_DARK = "#007A6A"
AMBER = "#F59E0B"
SLATE = "#5B6B7C"
BORDER = "#D9E1E7"
WHITE = "#FFFFFF"
BG = "#FFFFFF"

FONT = {"family": "DejaVu Sans"}  # closest metrics to Inter available headless


def box(ax, x, y, w, h, title, sub="", kind="det"):
    styles = {
        "judg": dict(fc=NAVY, ec=NAVY, tc=WHITE, sc="#B9C4D4"),
        "det": dict(fc=WHITE, ec=BORDER, tc=DEEP, sc=SLATE),
        "port": dict(fc=WHITE, ec=TEAL, tc=DEEP, sc=SLATE),
        "ctrl": dict(fc=WHITE, ec=AMBER, tc=DEEP, sc=SLATE),
        "human": dict(fc=AMBER, ec=AMBER, tc=DEEP, sc=DEEP),
    }
    s = styles[kind]
    lw = 2.0 if kind in ("port", "ctrl") else 1.4
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.006",
                                fc=s["fc"], ec=s["ec"], lw=lw, mutation_aspect=1.4))
    cy = y + h / 2
    if sub:
        ax.text(x + w / 2, cy + 0.016, title, ha="center", va="center", fontsize=11.5,
                color=s["tc"], fontweight="bold", **FONT)
        ax.text(x + w / 2, cy - 0.020, sub, ha="center", va="center", fontsize=8.6,
                color=s["sc"], **FONT)
    else:
        ax.text(x + w / 2, cy, title, ha="center", va="center", fontsize=11.5,
                color=s["tc"], fontweight="bold", **FONT)


def arrow(ax, x1, y1, x2, y2, color=SLATE, dashed=False, lw=1.6):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=lw, linestyle=(0, (4, 3)) if dashed else "solid",
                                 shrinkA=2, shrinkB=2))


def legend(ax, x, y):
    items = [
        (NAVY, NAVY, "judgment capability (authoring time only)"),
        (WHITE, BORDER, "deterministic capability"),
        (WHITE, AMBER, "control point"),
        (AMBER, AMBER, "human authority"),
        (WHITE, TEAL, "port (an interface, not a product)"),
    ]
    cx = x
    for fc, ec, label in items:
        ax.add_patch(FancyBboxPatch((cx, y), 0.018, 0.028, boxstyle="round,pad=0.004",
                                    fc=fc, ec=ec, lw=1.6, mutation_aspect=1.4))
        ax.text(cx + 0.028, y + 0.014, label, ha="left", va="center", fontsize=9,
                color=SLATE, **FONT)
        cx += 0.033 + len(label) * 0.0058


def section(ax, x, y, label):
    ax.text(x, y, label.upper(), ha="left", va="center", fontsize=10.5,
            color=SLATE, fontweight="bold", **FONT)


def logical():
    fig, ax = plt.subplots(figsize=(20, 11.6), dpi=180)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(BG)

    legend(ax, 0.03, 0.955)

    # -- inbound ports ----------------------------------------------------
    section(ax, 0.03, 0.905, "Inbound ports")
    box(ax, 0.03, 0.80, 0.20, 0.085, "Control Source Port", "approved remediation plan", "port")
    box(ax, 0.26, 0.80, 0.20, 0.085, "Reasoning Port", "authoring time only", "port")

    # -- authoring row ----------------------------------------------------
    section(ax, 0.03, 0.745, "Authoring (judgment, once per control)")
    box(ax, 0.03, 0.615, 0.13, 0.09, "Triage", "attestable or not", "judg")
    box(ax, 0.19, 0.615, 0.15, 0.09, "Compilation", "intent to CheckSpec", "judg")
    box(ax, 0.37, 0.615, 0.14, 0.09, "Explanation", "advisory, no authority", "judg")

    # -- authority --------------------------------------------------------
    section(ax, 0.57, 0.745, "Authority")
    box(ax, 0.57, 0.615, 0.155, 0.09, "Approval", "hash pin; edit voids", "ctrl")
    box(ax, 0.60, 0.80, 0.13, 0.085, "Human", "Authority", "human")
    box(ax, 0.76, 0.615, 0.21, 0.09, "Approval Registry Port", "content-addressed pins", "port")

    # -- runtime rows -----------------------------------------------------
    section(ax, 0.03, 0.545, "Runtime (deterministic, forever, zero model cost)")
    box(ax, 0.03, 0.415, 0.14, 0.09, "Collection", "one clock read", "det")
    box(ax, 0.20, 0.415, 0.15, 0.09, "Evaluation", "pure; fail-closed", "det")
    box(ax, 0.38, 0.415, 0.15, 0.09, "Attestation", "byte-stable artifact", "det")
    box(ax, 0.20, 0.27, 0.13, 0.09, "Replay", "re-derive any verdict", "det")
    box(ax, 0.36, 0.27, 0.13, 0.09, "Drift Diff", "deterministic delta", "det")
    box(ax, 0.53, 0.27, 0.15, 0.09, "Gated Publish", "human key at write", "ctrl")

    # -- evidence + outbound ports ---------------------------------------
    box(ax, 0.03, 0.10, 0.20, 0.085, "Evidence Ports", "read-only, per target system", "port")
    box(ax, 0.53, 0.10, 0.19, 0.085, "Attestation Sink Port", "tracker, auditor", "port")
    box(ax, 0.78, 0.10, 0.17, 0.085, "Audit Sink Port", "JSONL, SIEM-ready", "port")

    # -- cross-cutting ----------------------------------------------------
    section(ax, 0.60, 0.545, "Cross-cutting")
    box(ax, 0.60, 0.415, 0.175, 0.09, "Integrity", "content addressing;\ntamper visible at use", "det")
    box(ax, 0.80, 0.415, 0.17, 0.09, "Audit &\nObservability", "every action, hashed inputs", "det")

    # -- flows ------------------------------------------------------------
    arrow(ax, 0.13, 0.80, 0.10, 0.705)                       # control source -> triage
    arrow(ax, 0.16, 0.66, 0.19, 0.66)                        # triage -> compilation
    arrow(ax, 0.34, 0.66, 0.37, 0.66)                        # compilation -> explanation
    arrow(ax, 0.36, 0.80, 0.265, 0.705, TEAL, dashed=True)   # reasoning port -> authoring
    arrow(ax, 0.51, 0.66, 0.57, 0.66)                        # explanation -> approval (packet)
    arrow(ax, 0.660, 0.80, 0.650, 0.705, AMBER)              # human -> approval
    arrow(ax, 0.725, 0.66, 0.76, 0.66, AMBER)                # approval -> registry
    arrow(ax, 0.78, 0.607, 0.285, 0.51, AMBER, dashed=True)  # registry -> evaluation (the gate)
    arrow(ax, 0.10, 0.185, 0.10, 0.415)                      # evidence port -> collection
    arrow(ax, 0.17, 0.46, 0.20, 0.46)                        # collection -> evaluation
    arrow(ax, 0.35, 0.46, 0.38, 0.46)                        # evaluation -> attestation
    arrow(ax, 0.42, 0.415, 0.30, 0.36)                       # attestation -> replay (stored artifacts)
    arrow(ax, 0.455, 0.415, 0.435, 0.36)                     # attestations -> drift diff
    arrow(ax, 0.50, 0.44, 0.575, 0.36)                       # attestation -> gated publish
    arrow(ax, 0.615, 0.27, 0.625, 0.185, AMBER)              # publish -> attestation sink
    arrow(ax, 0.875, 0.415, 0.865, 0.185)                    # audit -> audit sink
    ax.text(0.03, 0.035, "The Reasoning Port attaches only to authoring capabilities. No path exists from it to the runtime row: "
                         "the engine imports no clock, no randomness, no network, and no model interface, and only registry-pinned specs execute.",
            ha="left", va="center", fontsize=9.5, color=SLATE, **FONT)

    fig.savefig(OUT + "Riptide-Attest-logical-architecture.png", bbox_inches="tight",
                facecolor=BG, pad_inches=0.25)
    plt.close(fig)


def lifecycle():
    fig, ax = plt.subplots(figsize=(20, 6.4), dpi=180)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(BG)

    ax.text(0.03, 0.93, "THE CONTROL LIFECYCLE", ha="left", fontsize=12, color=SLATE,
            fontweight="bold", **FONT)
    ax.text(0.03, 0.845, "Authoring spends model dollars once; a human arms the spec; the runtime verbs are pure code and free forever.",
            ha="left", fontsize=10.5, color=SLATE, **FONT)

    steps = [
        ("Triage", "Haiku 4.5", "attestable?", "judg"),
        ("Compile", "Opus 4.8", "draft CheckSpec", "judg"),
        ("Explain", "Haiku 4.5", "review packet", "judg"),
        ("Approve", "human", "hash pin", "human"),
        ("Snapshot", "code", "freeze evidence", "det"),
        ("Evaluate", "code", "pure verdicts", "det"),
        ("Attest", "code", "byte-stable proof", "det"),
        ("Replay / Diff", "code", "re-derive; drift", "det"),
    ]
    styles = {
        "judg": dict(fc=NAVY, ec=NAVY, tc=WHITE, sc="#B9C4D4"),
        "det": dict(fc=WHITE, ec=BORDER, tc=DEEP, sc=SLATE),
        "human": dict(fc=AMBER, ec=AMBER, tc=DEEP, sc=DEEP),
    }
    x, w, h, gap, y0 = 0.03, 0.094, 0.34, 0.024, 0.36
    for i, (title, actor, sub, kind) in enumerate(steps):
        s = styles[kind]
        ax.add_patch(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0.004,rounding_size=0.004",
                                    fc=s["fc"], ec=s["ec"], lw=1.4, mutation_aspect=0.35))
        ax.text(x + w / 2, y0 + h * 0.72, title, ha="center", va="center", fontsize=12.5,
                color=s["tc"], fontweight="bold", **FONT)
        ax.text(x + w / 2, y0 + h * 0.42, actor, ha="center", va="center", fontsize=9.5,
                color=s["sc"], style="italic", **FONT)
        ax.text(x + w / 2, y0 + h * 0.17, sub, ha="center", va="center", fontsize=9.5,
                color=s["sc"], **FONT)
        if i < len(steps) - 1:
            arrow(ax, x + w + 0.003, y0 + h / 2, x + w + gap - 0.003, y0 + h / 2, SLATE)
        x += w + gap

    ax.add_patch(FancyBboxPatch((0.022, 0.28), 0.346, 0.50, boxstyle="round,pad=0.004",
                                fill=False, ec=NAVY, lw=1.2, linestyle=(0, (5, 4)), mutation_aspect=0.35))
    ax.text(0.195, 0.20, "AUTHORING -- model spend, once per control", ha="center", fontsize=10,
            color=NAVY, fontweight="bold", **FONT)
    ax.add_patch(FancyBboxPatch((0.494, 0.28), 0.482, 0.50, boxstyle="round,pad=0.004",
                                fill=False, ec=TEAL_DARK, lw=1.2, linestyle=(0, (5, 4)), mutation_aspect=0.35))
    ax.text(0.735, 0.20, "RUNTIME -- deterministic, zero model cost, runs forever", ha="center",
            fontsize=10, color=TEAL_DARK, fontweight="bold", **FONT)
    ax.text(0.03, 0.09, "The gate between the halves: evaluate() refuses any spec whose SHA-256 a human has not pinned into the registry. "
                        "Editing one character of an approved spec voids its approval.",
            ha="left", fontsize=9.5, color=SLATE, **FONT)

    fig.savefig(OUT + "Riptide-Attest-control-lifecycle.png", bbox_inches="tight",
                facecolor=BG, pad_inches=0.25)
    plt.close(fig)


import os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets") + os.sep
os.makedirs(OUT, exist_ok=True)

logical()
lifecycle()
print("diagrams written")
