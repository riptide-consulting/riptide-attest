# The presentation toolchain

The Riptide Attest master deck (35 slides) and technical documentation are
built from code, never hand-edited. This directory is the same pattern as
`riptide-ria/presentation/`: builders, diagram generators, quality gates,
and a one-command demo-readiness check. The built artifacts land in `out/`
(git-ignored: ~1.5 MB of output that regenerates in seconds from ~1 MB of
source).

## Layout

    build/      deck and doc builders (node: pptxgenjs, docx)
    diagrams/   architecture diagram generator (python: matplotlib)
    qa/         quality gates (python: WCAG contrast, layout geometry
                and text fit with real font metrics)
    assets/     generated diagrams (checked in: the doc and deck embed them)
    fonts/      Inter, Inter Italic, Source Serif 4 (OFL licensed)
    out/        built artifacts (git-ignored)

## Build and verify

    npm install         once
    npm run all         diagrams -> deck -> doc -> both gates

Or the full demo-readiness proof (adds the 234-test suite and the
self-verifying demo):

    powershell -File demo-check.ps1

## Design rules

Brand tokens are the Riptide set: Abyss Navy 0A1628, Riptide Teal 00C9B1,
Signal Amber F59E0B, Bone FAF7F2, Slate 5B6B7C, Mist D9E1E7. The contrast
rule from the brand guide is enforced by the gate, not by discipline: pure
brand colours for fills and text on dark; the deep variants (Deep Teal
007A6A, Deep Amber 9C5D00) for small text on light. Typefaces: Inter for
text, Source Serif 4 for editorial accents, Consolas for code.

The gates are the review: a slide change that overflows its box, stretches
an image, or fails WCAG contrast fails the build. `FACTS.md` pins every
number the deck asserts to its source file in this repository; if a number
moves in code, the deck builder and FACTS.md move with it.

Fonts must be installed on the presenting machine (select all three in
`fonts/`, right-click, Install) or PowerPoint silently substitutes.
