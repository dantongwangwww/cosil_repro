#!/usr/bin/env bash
set -euo pipefail
paper_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$paper_dir"
export TEXINPUTS="$paper_dir/template:${TEXINPUTS:-}"
export BSTINPUTS="$paper_dir/template:${BSTINPUTS:-}"
export BIBINPUTS="$paper_dir:${BIBINPUTS:-}"
mkdir -p build
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
cp build/main.pdf manuscript.pdf
pdflatex -interaction=batchmode -halt-on-error -output-directory=build flowchart.tex
cp build/flowchart.pdf figures/fig_architecture.pdf
pdftoppm -r 180 -singlefile -png figures/fig_architecture.pdf figures/fig_architecture
pdfinfo manuscript.pdf | head -20
