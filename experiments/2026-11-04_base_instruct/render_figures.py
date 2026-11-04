#!/usr/bin/env python3
"""Reproduce the public aggregate-only Base/Instruct charts and tables.

This renders supplied aggregate metrics. It does not rerun inference or judges.
Usage: python render_figures.py [--input data/aggregate_metrics.json] [--out .]
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "base-instruct-figure-cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, FancyBboxPatch
from matplotlib.ticker import PercentFormatter
import numpy as np

P = argparse.ArgumentParser(description=__doc__)
P.add_argument("--input", type=Path, default=Path(__file__).parent / "data/aggregate_metrics.json")
P.add_argument("--out", type=Path, default=Path(__file__).parent)
ARGS = P.parse_args()
D = json.loads(ARGS.input.read_text())
C = D["conditions"]
N = D["scope"]["exact_common_behavior_ids"]
OUT = ARGS.out
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

BASE = "#7057AE"
INST = "#087E8B"
INK = "#192C3A"
MUTED = "#51626E"
GRID = "#DEE5E8"
PAPER = "#FFFFFF"
PALE = "#F0F4F5"
AMBER = "#B16A13"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5,
    "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED,
    "ytick.color": INK, "axes.edgecolor": GRID, "axes.spines.top": False,
    "axes.spines.right": False, "axes.spines.left": False,
    "axes.titleweight": "bold", "axes.titlesize": 14,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "svg.hashsalt": "base-instruct-aggregate-20261104",
    "savefig.facecolor": PAPER, "figure.facecolor": PAPER,
})

cross = {(r["condition"], r["judge"]): r for r in D["cross_model"]}
agree = {r["condition"]: r for r in D["agreement"]}
quality = {(r["condition"], r["model"]): r for r in D["quality_common_word_metrics"]}

def validate():
    assert N == 159
    assert C == ["FP16", "SP30", "SP40", "SP50", "SP55", "SP60", "SP70"]
    assert D["scope"]["common_condition_id_keys"] == N * len(C)
    assert D["scope"]["common_judge_keys"] == N * len(C) * 2
    assert D["scope"]["base_input_double_BOS"] == 1113
    for c in C:
        for model, key, ratekey in [("Base", "base_agreement", "second_unsafe"), ("Instruct", "instruct_agreement", "first_unsafe")]:
            a = agree[c][key]
            t = a["table_LGrows_HBcols"]
            assert sum(sum(row) for row in t) == N
            assert t[0][0] + t[1][1] == a["agreement_count"]
            assert t[0][1] + t[1][0] == a["disagreement"]
            assert t[0][1] + t[1][1] == cross[c, "HB"][ratekey]
            assert t[1][0] + t[1][1] == cross[c, "LG"][ratekey]
            assert quality[c, model]["n"] == N
        for j in ["HB", "LG"]:
            r = cross[c, j]
            assert r["n"] == N
            assert abs(r["delta_second_minus_first_pp"] - (r["second_unsafe"] - r["first_unsafe"]) / N * 100) < 1e-10
            n_disc = r['first0_second1'] + r['first1_second0']
            small = min(r['first0_second1'], r['first1_second0'])
            p = min(1.0, 2 * sum(math.comb(n_disc, k) for k in range(small + 1)) / 2**n_disc) if n_disc else 1.0
            assert math.isclose(p, r['exact_mcnemar_p'], rel_tol=1e-10, abs_tol=1e-50)
    ordered = sorted(D['cross_model'], key=lambda r: r['exact_mcnemar_p'])
    running = 0.0
    for rank, r in enumerate(ordered):
        running = min(1.0, max(running, (len(ordered) - rank) * r['exact_mcnemar_p']))
        assert math.isclose(running, r['holm_p'], rel_tol=1e-10, abs_tol=1e-50)

def title(fig, main, sub, number):
    fig.text(.055, .951, "SAVED-CORPUS COMPARISON  /  04 NOV 2026", size=9.5, color=MUTED, weight="bold")
    fig.text(.055, .902, main, size=23, weight="bold", va="top")
    fig.text(.055, .85, sub, size=11, color=MUTED, va="top")
    fig.text(.945, .037, f"{number:02d}", size=10, ha="right", color=MUTED)

def footnote(fig, lines):
    y = .11
    for line in lines:
        fig.text(.055, y, line, size=9.3, color=MUTED, va="top")
        y -= .023

def model_legend(fig, y=.795):
    fig.legend(handles=[Patch(color=BASE, label="Base"), Patch(color=INST, label="Instruct reference")],
               loc="upper left", bbox_to_anchor=(.055, y), frameon=False, ncol=2,
               handlelength=1.2, columnspacing=2.0, borderaxespad=0, fontsize=11)

def save(fig, name, pdf):
    fig.savefig(FIG / f"{name}.png", dpi=210)
    fig.savefig(FIG / f"{name}.svg", metadata={"Date": None})
    fig.savefig(FIG / f"{name}.pdf", metadata={"Title": name, "Author": "", "CreationDate": None, "ModDate": None})
    pdf.savefig(fig)
    plt.close(fig)

def rates(pdf):
    fig = plt.figure(figsize=(13.6, 9.2))
    title(fig, "Judge results differ sharply on Base responses",
          "Same 159 behaviors in each condition. Percent labeled unsafe; both panels use the same 0-100% scale.", 1)
    model_legend(fig)
    axs = [fig.add_axes([.08, .245, .38, .48]), fig.add_axes([.56, .245, .38, .48])]
    y = np.arange(len(C))
    for ax, judge, heading in zip(axs, ["HB", "LG"], ["HarmBench (HB)", "Llama Guard (LG)"]):
        ax.set_title(heading, loc="left", pad=16)
        for model, offset, color, k in [("Base", -.17, BASE, "second_unsafe"), ("Instruct", .17, INST, "first_unsafe")]:
            vals = np.array([cross[c, judge][k] / N * 100 for c in C])
            ax.barh(y+offset, vals, height=.27, color=color, alpha=.93, zorder=3)
            for yy, value in zip(y+offset, vals):
                ax.text(value+1.1 if value < 89 else value-1.5, yy, f"{value:.1f}%", va="center",
                        ha="left" if value < 89 else "right", size=10.3,
                        color=color if value < 89 else "white", weight="bold")
        ax.set_yticks(y, C)
        ax.set_ylim(len(C)-.5, -.55)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
        ax.grid(axis="x", color=GRID, linewidth=.7, zorder=0)
        ax.tick_params(axis="both", length=0, pad=7)
        ax.set_xlabel("Responses labeled unsafe", labelpad=9)
    fig.text(.08, .165, "HB: successful exhibition of the specified behavior.", size=10.4, color=MUTED)
    fig.text(.56, .165, "LG: unsafe content under its category policy.", size=10.4, color=MUTED)
    footnote(fig, [
        "The judges measure different constructs; neither is adjudicated ground truth. Low HB rates do not establish safety.",
        "Base inputs all begin with duplicate BOS tokens. Exact historical Instruct generation linkage is unverified.",
        "This is a common-judge, same-behavior corpus comparison, not a clean causal Base-versus-Instruct ablation.",
    ])
    save(fig, "figure1_judge_rates", pdf)

def diagnostics(pdf):
    fig = plt.figure(figsize=(13.6, 10.0))
    title(fig, "Disagreement and repetition are present before pruning",
          "Strong Base repetition is already visible at FP16. Quality metrics below use identical word-based definitions.", 2)
    axs = [fig.add_axes([.08, .50, .38, .26]), fig.add_axes([.56, .50, .38, .26]),
           fig.add_axes([.08, .195, .38, .18]), fig.add_axes([.56, .195, .38, .18])]
    colors = ["#D6E1E5", BASE, "#D6A05B", "#345E70"]
    labels = ["Both not unsafe", "LG unsafe / HB not unsafe", "HB unsafe / LG not unsafe", "Both unsafe"]
    y = np.arange(len(C))
    for ax, model, key in zip(axs[:2], ["Base", "Instruct reference"], ["base_agreement", "instruct_agreement"]):
        ax.set_title(model + ": joint judge labels", loc="left", fontsize=13, pad=12)
        left = np.zeros(len(C))
        for idx, color in enumerate(colors):
            vals = []
            for c in C:
                a = agree[c][key]
                t = a["table_LGrows_HBcols"]
                vals.append([t[0][0], t[1][0], t[0][1], t[1][1]][idx])
            widths = np.array(vals) / N * 100
            ax.barh(y, widths, left=left, color=color, height=.66, zorder=3, edgecolor="white", linewidth=.5)
            for yy, count, width, ll in zip(y, vals, widths, left):
                if width >= 11:
                    ax.text(ll + width/2, yy, str(count), ha="center", va="center", size=9.6,
                            color="white" if idx in [1, 3] else INK, weight="bold")
            left += widths
        ax.set_yticks(y, C)
        ax.set_ylim(len(C)-.5, -.55)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
        ax.tick_params(axis="both", length=0, pad=6)
        ax.grid(axis="x", color=GRID, linewidth=.7)
    fig.legend(handles=[Patch(color=col, label=lab) for col, lab in zip(colors, labels)], loc="lower left",
               bbox_to_anchor=(.075, .432), frameon=False, ncol=2, fontsize=9.7, borderaxespad=0,
               handlelength=1.15, columnspacing=2.0, labelspacing=.5)
    for ax, metric, heading, unit in [(axs[2], "repeat_mean", "Mean word-trigram repetition", "Repetition score"),
                                      (axs[3], "collapse_count", "Heuristic collapse flag", "Flagged responses (%)")]:
        ax.set_title(heading, loc="left", fontsize=13, pad=14)
        for model, color, marker in [("Base", BASE, "o"), ("Instruct", INST, "s")]:
            vals = [quality[c, model][metric] for c in C]
            if metric == "collapse_count":
                vals = [v / N * 100 for v in vals]
            ax.plot(range(len(C)), vals, color=color, marker=marker, ms=5, linewidth=2.0, label=model, zorder=3)
        ax.set_xticks(range(len(C)), C, fontsize=9.5)
        ax.set_xlim(-.25, 6.25)
        ax.set_ylim(0, 1.07 if metric == "repeat_mean" else 107)
        ax.set_yticks([0, .25, .5, .75, 1] if metric == "repeat_mean" else [0, 25, 50, 75, 100])
        ax.set_ylabel(unit, size=10)
        if metric == "collapse_count":
            ax.yaxis.set_major_formatter(PercentFormatter(100, decimals=0))
        ax.grid(axis="y", color=GRID, linewidth=.7)
        ax.tick_params(axis="both", length=0, pad=5)
    axs[2].legend(loc="upper center", bbox_to_anchor=(.5, -.18), frameon=False, ncol=2, fontsize=10)
    fig.text(.56, .155, "Proxy flags: Base FP16 128/159; SP70 159/159.\nInstruct FP16 0/159; SP70 16/159.", size=10.0, color=MUTED, va="top", linespacing=1.6)
    footnote(fig, [
        "Top panels show all 159 responses; segment labels are counts where space allows. 'Not unsafe' is a judge label, not a safety claim.",
        "Repetition and collapse are length-sensitive heuristics, not human-adjudicated failure. Lines connect ordered conditions only.",
        "Duplicate BOS occurs in all 1,113 Base inputs. This observed Base configuration is not a demonstrated cause.",
    ])
    save(fig, "figure2_disagreement_quality", pdf)

def table_and_scope(pdf):
    fig = plt.figure(figsize=(13.6, 9.2))
    title(fig, "Counts and interpretation at a glance",
          "Every count has denominator 159. Each cell is Base / Instruct; repetition is a mean score on a 0-1 scale.", 3)
    ax = fig.add_axes([.055, .45, .89, .335])
    ax.axis("off")
    headers = ["Condition", "HB unsafe\ncount", "LG unsafe\ncount", "Judge agreement\ncount", "Collapse flag\ncount", "Mean word-trigram\nrepetition"]
    rows = []
    for c in C:
        hb, lg = cross[c, "HB"], cross[c, "LG"]
        ba, ia = agree[c]["base_agreement"], agree[c]["instruct_agreement"]
        bq, iq = quality[c, "Base"], quality[c, "Instruct"]
        rows.append([c, f"{hb['second_unsafe']} / {hb['first_unsafe']}",
                     f"{lg['second_unsafe']} / {lg['first_unsafe']}",
                     f"{ba['agreement_count']} / {ia['agreement_count']}",
                     f"{bq['collapse_count']} / {iq['collapse_count']}",
                     f"{bq['repeat_mean']:.3f} / {iq['repeat_mean']:.3f}"])
    tab = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="center",
                   colWidths=[.12, .15, .15, .19, .17, .22], bbox=[0, 0, 1, 1])
    tab.auto_set_font_size(False)
    tab.set_fontsize(11)
    for (r, c), cell in tab.get_celld().items():
        cell.set_linewidth(0)
        if r == 0:
            cell.set_facecolor(INK)
            cell.set_text_props(color="white", weight="bold", size=10.5)
            cell.set_height(cell.get_height()*1.4)
        else:
            cell.set_facecolor(PALE if r%2 else PAPER)
            if c == 0:
                cell.set_text_props(weight="bold")
    fig.text(.055, .413, "What the paired tests support", weight="bold", size=13)
    fig.text(.055, .377,
             "LG labels Base unsafe more often at all seven conditions. HB is higher for Base at FP16 and lower at SP50, SP55 and SP60.\n"
             "HB differences at SP30, SP40 and SP70 do not survive the 14-test Holm correction (exact two-sided McNemar).\n"
             "At SP70, the HB difference is -1.89 percentage points (Holm p = 0.534): this does not show that Base is safer.",
             size=10.7, color=MUTED, va="top", linespacing=1.8)
    fig.text(.055, .255, "Interpretation boundary", weight="bold", size=13)
    fig.text(.055, .218,
             "Verified: 159 shared behaviors, 1,113 response pairs, 2,226 paired judge labels; reference labels and hashes match\n"
             "the original Oct 29 / Oct 30 judged records. Matching judge settings do not make generation pipelines identical.\n"
             "All Base inputs start with duplicate BOS. Historical Instruct prompt/code/tokenizer/runtime and checkpoint linkage\n"
             "are not established here. Neither judge resolves the other judge's labels; no causal instruction-tuning claim follows.",
             size=10.7, color=MUTED, va="top", linespacing=1.8)
    footnote(fig, [
        "Collapse proxy: >=50 words with unique-word ratio <0.10 or trigram repetition >=0.80; or >=20 words with dominance >=0.30.",
        "The same 159 behaviors recur across conditions. The 1,113 response pairs are not 1,113 independent behaviors.",
        "Public reproducibility: aggregate metrics to figures and tables only. No original prompts, responses or individual judge records.",
    ])
    save(fig, "figure3_summary_table", pdf)

def write_tables():
    rows=[]
    for c in C:
        for model, k, akey in [("Base", "second_unsafe", "base_agreement"), ("Instruct", "first_unsafe", "instruct_agreement")]:
            a=agree[c][akey]; q=quality[c,model]
            rows.append(dict(condition=c,model=model,n=N,HB_unsafe_count=cross[c,"HB"][k],
                HB_unsafe_percent=cross[c,"HB"][k]/N*100,LG_unsafe_count=cross[c,"LG"][k],
                LG_unsafe_percent=cross[c,"LG"][k]/N*100,judge_agreement_count=a['agreement_count'],
                judge_agreement_percent=a['agreement_count']/N*100,judge_disagreement_count=a['disagreement'],
                LG_unsafe_HB_not_unsafe=a['LG1_HB0'],HB_unsafe_LG_not_unsafe=a['LG0_HB1'],
                collapse_proxy_count=q['collapse_count'],collapse_proxy_percent=q['collapse_count']/N*100,
                mean_word_trigram_repetition=q['repeat_mean']))
    with (OUT/'summary_table.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines=['# Base versus available Instruct reference: concise table',
           '', 'Each count is out of 159. Cells are Base / Instruct. Repetition is a mean word-trigram score (0-1).', '',
           '| Condition | HB unsafe | LG unsafe | Judge agreement | Collapse proxy | Mean repetition |',
           '|---|---:|---:|---:|---:|---:|']
    for i,c in enumerate(C):
        b,ins=rows[2*i:2*i+2]
        lines.append(f"| {c} | {b['HB_unsafe_count']} / {ins['HB_unsafe_count']} | {b['LG_unsafe_count']} / {ins['LG_unsafe_count']} | {b['judge_agreement_count']} / {ins['judge_agreement_count']} | {b['collapse_proxy_count']} / {ins['collapse_proxy_count']} | {b['mean_word_trigram_repetition']:.3f} / {ins['mean_word_trigram_repetition']:.3f} |")
    lines += ['', '**Interpretation:** Low HB rates do not establish safety. Judges apply different constructs; neither is adjudicated ground truth. Base already shows severe repetitive output at FP16.',
              '', '**Comparability limit:** All 1,113 Base inputs begin with duplicate BOS; historical Instruct generation linkage is unverified. This is a common-judge, same-behavior corpus comparison, not a clean causal instruction-tuning ablation.']
    (OUT/'SUMMARY_TABLE.md').write_text('\n'.join(lines)+'\n')

def main():
    validate()
    write_tables()
    with PdfPages(OUT/'base_instruct_comparison.pdf', metadata={'Title':'Base versus Instruct: aggregate research figures','Author':'','CreationDate':None,'ModDate':None}) as pdf:
        rates(pdf); diagnostics(pdf); table_and_scope(pdf)
    print(json.dumps({'validated':True,'conditions':len(C),'behaviors_per_condition':N,
        'output':'base_instruct_comparison.pdf','figures':3,'raw_response_text_included':False},indent=2))

if __name__ == '__main__':
    main()
