# Reproducing the manuscript results

## What does this package reproduce?

This package accompanies the study of pair selection and score estimation
for comparative judgments of student writing. It recreates Figures 1–4
and Tables 2–4. It also checks the supplied data before using them.

Figures 2–4 and Tables 2–3 are drawn from saved numerical summaries.
An additional command recalculates the reported statistical comparisons
from the saved, unrounded performance measures for 16 writing prompts
and six writing traits per prompt. It does not fit the scoring models again.

Some calculations need additional inputs. Check which folders and files
are present in your copy:

| Included input | What it allows |
| --- | --- |
| `data/primary/`, `data/ssr/`, `data/estimator/` | Figures 2–4, Tables 2–3 and the reported early instability of frequentist reliability estimates |
| `data/human_summary.csv`, `data/table_rq3_human.tex` | Table 4 and its saved numerical summary |
| `data/human_prompt_z.csv` | Recalculation of Table 4 correlations, confidence intervals and differences from saved prompt averages |
| `observations/` | Checks of comparison counts, unique essay pairs, held-out comparisons and reversed presentation order; recalculation of reversal findings |
| `conditions/` together with `observations/` | Recalculation of all reported statistical comparisons and stopping summaries |
| `data/position/` | Recalculation of the reported position and lapse summaries from saved posterior draws |

A complete copy contains all these inputs. Missing optional inputs are
limitations of that copy; a successful display-only run does not mean
those additional calculations were reproduced.

The five score estimators retain their manuscript names:
B1 is the simpler Bayesian Bradley–Terry model; B2 adds presentation-position
and lapse effects. A lapse is a random response. F1 is the conventional
frequentist estimator, F2 uses an alpha adjustment, and F3 applies bootstrap
bias correction to F2. A dense reference uses all original comparisons
for that estimator; it is a benchmark, not a true writing-quality score.
The manuscript explains the four pairing methods: random, p50, Pollitt
and hybrid.

Figures and tables use the manuscript's B1/B2 names above. Stored estimator
codes in `data/primary/`, `conditions/` and recalculated analysis CSV files
are reversed: B1 means the full Bayesian model and B2 means the simpler
model. The figure scripts translate these codes for display. In
`data/estimator/`, columns beginning with `manuscript_` give the display
names; comparison IDs retain the stored codes. Human-correlation files
already use manuscript names. Preserve these codes when checking files.

## What software is needed?

Use Python 3.11 or later. Figures require NumPy 1.24 or later and
Matplotlib 3.6 or later; these are listed in `requirements.txt`.
The table-only command uses Python's standard library.

R is also needed for either of the following:

- If `data/position/` is present, **every main run**, including table-only
  runs, recalculates position and lapse summaries. Use R 4.6.1 with
  `digest` and `jsonlite` (tested versions: 0.6.39 and 2.0.0).
- The `--analysis` option requires R 4.6.1, `clubSandwich` 0.7.0 and
  `digest`. The exact R and `clubSandwich` versions are checked so the
  statistical comparisons can be matched precisely.

Have these programs and packages installed before starting. `Rscript`
must be available on your command path, and its R library must contain
the required packages. The analysis commands need no `pairwiseLLM`, Stan,
LaTeX installation, model provider account or API key. They do not install
software or contact an online service.

These commands check the required software for a complete copy:

```bash
python3 --version
python3 -c 'import numpy, matplotlib; print("NumPy", numpy.__version__, "Matplotlib", matplotlib.__version__)'
Rscript --vanilla -e 'stopifnot(as.character(getRversion()) == "4.6.1", as.character(packageVersion("clubSandwich")) == "0.7.0"); print(sapply(c("digest", "jsonlite", "clubSandwich"), function(p) as.character(packageVersion(p))))'
```

## How do I run it?

Extract the package into a new folder. Open a terminal in that folder,
which contains `README.md`, `run.py`, `data/` and `src/`.
Start with:

```bash
python3 run.py
```

This checks input file hashes, recreates all four figures and three result
tables, and recalculates the human-correlation and position summaries
when their inputs are present. A hash is a file fingerprint used to detect
missing or changed data. When comparison records or condition measures
are included, their structure and completeness are also checked.
The top-level `SHA256SUMS` covers all shipped files, including hidden files.
`source-provenance.json` records original code fingerprints and the changes
made to its explanatory text; those changes preserve the calculations.

For the additional statistical recalculation, use a **second fresh
extraction** and run:

```bash
python3 run.py --analysis
```

This performs the same display run and independently recalculates the
reported comparisons for research questions 1–3, stopping summaries and
reversal findings. It requires `conditions/` and `observations/`.
It compares the new statistics with the saved results, including estimates,
standard errors, degrees of freedom, intervals and p values. The checks
use the stated numerical tolerances in `src/recalculate_inference.R`.

If you only need tables and numerical outputs, use a fresh extraction
for either command below. Neither command imports the plotting libraries:

```bash
python3 run.py --tables-only
```

```bash
python3 run.py --analysis --tables-only
```

Use a new extraction for another main run. Position-summary and analysis
outputs must be new, so earlier results are preserved. Do not edit input
files or their `SHA256SUMS` fingerprints to make a failed check pass.

## Where are the results?

All generated files are under `output/`:

| Output | Manuscript result |
| --- | --- |
| `figures/figure_hybrid_pairing_flowchart.pdf` | Figure 1: explanation of hybrid pairing |
| `figures/figure2_rq1_recovery.pdf` | Figure 2: recovery differences between adaptive and random pairing |
| `figures/figure_rq2_gap_main.pdf` | Figure 3: internal reliability minus dense-reference recovery |
| `figures/figure_rq2_timing_main.pdf` | Figure 4: reliability-based stopping compared with recovery |
| `figures/layout_checks.json` | Checks that the Figure 1 boxes, arrows and labels fit |
| `tables/table_rq2_main.tex` | Table 2: reliability–recovery contrasts |
| `tables/table_rq3_main.tex` | Table 3: estimator performance |
| `tables/table_rq3_human.tex` | Table 4: correlations with human ratings |
| `tables/human_correlations.csv` | Numerical Table 4 results; recalculated when prompt averages are supplied |
| `tables/human_table_verification.txt` | Records whether all 45 Table 4 values matched recalculated prompt summaries or only the saved summary |
| `position_summary.csv` | Lapse, position coefficient and equal-quality first-position preference, with credible intervals |

Each figure also has `.svg` and `.png` versions. The `.tex` files are table
source for LaTeX; generating them does not require LaTeX. Figure file
metadata may vary across environments; compare the rendered figure and
its values, rather than PDF creation dates or file bytes.

The `--analysis` option adds these files under `output/analysis/`:

| Output | What it contains |
| --- | --- |
| `rq1_recalculated.csv` | Three overall adaptive-versus-random recovery contrasts |
| `rq1_estimator_recalculated.csv` | Recovery contrasts for each estimator |
| `rq2_b6_combined_holm6.csv` | Six reliability–recovery contrasts: Bayesian models over budgets 2–16 and exploratory F1 results over budgets 6–16 |
| `rq2_bayes_estimator_recalculated.csv` | Separate Bayesian reliability–recovery contrasts |
| `rq3_recalculated_holm30.csv` | All 30 estimator comparisons across recovery, prediction and score spread |
| `stopping_recalculated.csv` | Stopping results at .90 and .70 thresholds |
| `VALIDATION.txt` | Description of the statistical checks that passed |
| `reversal/reversal_overall.csv` | Overall same-essay and first/second-position reversal summaries |
| `reversal/reversal_cells.csv` | Reversal summaries for each prompt and trait |
| `reversal/reversal_prompts.csv` | Reversal summaries averaged across the six traits in each prompt |
| `reversal/README.txt` | Definitions of the reversal summary columns |

Here, a budget is the mean number of comparisons per essay. Holm adjustment
accounts for multiple tests within a stated family. The statistical analyses
use prompts as the independent units, with standard errors adjusted for
observations within the same prompt (CR2) and Satterthwaite degrees of
freedom. Human-correlation intervals likewise describe variation across
16 prompts. The manuscript provides the statistical methods.

## How can I tell whether reproduction succeeded?

The command must finish without an error and end with:

```text
PASS: Reviewer artifact outputs written to output/
```

Read the earlier messages as well. A message saying a saved human summary
was used means that the prompt-average input was absent; it does not establish
independent recalculation. With `data/human_prompt_z.csv` present, the newly
calculated values are checked against the saved summary and all 45 displayed
Table 4 numbers. Copying the prewritten table alone does not pass this check.

For `--analysis`, also confirm that `output/analysis/VALIDATION.txt` exists
and the console reports that full-precision contrasts and stopping summaries
passed. It checks all 16 prompts and 96 prompt-by-trait combinations.
Figures include checks that plotted values match their input summaries;
inspect the images to confirm that labels are readable.

When position inputs are supplied, the nine displayed values must match:

| Quantity | Median | 95% credible interval |
| --- | ---: | --- |
| Lapse probability | 0.113% | [0.088%, 0.142%] |
| Position coefficient | 1.301 | [1.254, 1.346] |
| Equal-quality first-position preference | 78.5% | [77.7%, 79.3%] |

The reversal results should give 24,704 same-essay choices among 33,858
matched pairs (73.0%), 62.0% first-position preference across the 67,716
matched original/reversed presentations, and 8,642 pairs favoring the first
position in both orders (94.4% of pairs whose preferred essay changed).
In `reversal_overall.csv`, `first_preferred_rate` uses only those matched
presentations. These describe reversed presentations;
they are not a causal estimate of position effects or a test of repeating
an identical presentation.

## What should I do if something fails?

- **Missing Python module:** check the plotting packages listed in
  `requirements.txt`, or use `--tables-only` if you do not need figures.
- **Missing `Rscript`, wrong R version or missing R package:** check the
  software requirements above. R packages must be visible to the same
  `Rscript` used by the terminal.
- **Missing data folder:** check whether that optional input was supplied.
  Statistical recalculation requires both `conditions/` and `observations/`.
- **Hash, schema, count or numerical mismatch:** stop and retain the error.
  Extract an unmodified copy and retry the same command. Do not change
  values, filenames, seeds or tolerances.
- **Output already exists:** keep the previous results and run in a new
  extraction.

When reporting a problem, include the command, software versions and error
message. Do not attach student records, comparison rows, public-corpus keys,
human ratings or private local paths. The final success message is absent
if a required check fails; an incomplete output folder is not a successful run.

## Optional individual checks

These commands run only the named step. Each output must be new.

Check the comparison records without creating figures or tables:

```bash
python3 src/validate_observations.py --data-root observations
```

Recalculate human-correlation summaries and check Table 4:

```bash
python3 src/human_correlations.py --data-dir data --output-dir output/human-check
```

Recalculate position and lapse summaries:

```bash
mkdir -p output
Rscript --vanilla src/recalculate_position.R --data=data/position --output=output/position_check.csv
```

Recalculate reversal summaries:

```bash
mkdir -p output
python3 src/recalculate_reversals.py --data-root observations --output-dir output/reversal-check
```

## Optional: match the public ELLIPSE human ratings locally

The original corpus is maintained separately at the official
[ELLIPSE-Corpus repository](https://github.com/scrosseye/ELLIPSE-Corpus).
Its citation is:

Crossley, S. A., Tian, Y., Baffour, P., Franklin, A., Kim, Y., Morris, W.,
Benner, B., Picou, A., & Boser, U. (2023). Measuring second language
proficiency using the English Language Learner Insight, Proficiency and
Skills Evaluation (ELLIPSE) Corpus. *International Journal of Learner
Corpus Research, 9*(2), 248–269.

This package contains no original corpus files, student writing or human
rating records. To obtain ratings for the study essays:

1. Choose a local data folder **outside this extracted package and outside
   any Git repository**. Download `ELLIPSE_Final_github_train.csv` and
   `ELLIPSE_Final_github_test.zip` from the official repository into that
   folder. Read the corpus maintainers' README and data-use terms there.
2. Extract the test ZIP locally, using the password in that README
   (`ellipse_test`). The extracted file is
   `ELLIPSE_Final_github_test.csv`. If your archive utility cannot decrypt
   it, use a compatible utility such as 7-Zip. Do not download or extract
   the separate raw-rater archive for this join.
3. From the extracted reviewer package, run the command below. Replace
   `/PATH/TO/LOCAL-DATA` with your external local folder. The destination
   file must not already exist; the script creates its parent folder.

```bash
python3 src/merge_human_ratings.py \
  --data-root observations \
  --train /PATH/TO/LOCAL-DATA/ELLIPSE_Final_github_train.csv \
  --test /PATH/TO/LOCAL-DATA/ELLIPSE_Final_github_test.csv \
  --output /PATH/TO/LOCAL-DATA/joined/human_trait_scores.csv
```

The script prints `PASS: 1714 human-scored essays matched`. It requires
1,714 unique essays across 16 prompts, the original `text_id_kaggle`
identifiers and scores for all six traits: cohesion, syntax, vocabulary,
phraseology, grammar and conventions. Missing or duplicate identifiers,
missing or nonnumeric scores for matched essays, incorrect files and
incomplete matches cause an error. It does not export essay text or use
row order to match records.

The exact matching rule is:

```python
public_essay_key = "k" + hashlib.sha256(
    ("ELLIPSE-Corpus/text_id_kaggle/v1:" + str(text_id_kaggle).strip()).encode("utf-8")
).hexdigest()[:24]
```

Read `text_id_kaggle` as its original string; do not convert it to a
number. This key matches `public_essay_key` in
`observations/data/essays/item_index.csv`. The joined file contains only
the substitute item and prompt identifiers and six human trait ratings.
Keep the downloads, extracted CSV and joined output local and outside the
repository. Do not upload them to GitHub, Anonymous GitHub or a replacement
reviewer ZIP.

Linking permits a reviewer to identify the corresponding public corpus
records and inspect their human ratings locally. It also means these
deterministic keys do not guarantee anonymity. Human ratings alone do not
reproduce the essay-level correlations underlying Table 4: that requires
the original fitted essay scores, which are not supplied. The package's
Table 4 recalculation instead starts from 160 original prompt-level
Fisher-z means (five estimators, 16 prompts, B16 and dense references).
It verifies their aggregation, intervals, differences and all 45 displayed
values. The local join is optional and is not an input to that calculation.

## Create model inputs

Download and extract the public ELLIPSE train/test files as described above.
Keep them outside this package and all Git repositories. Python's standard
library is sufficient. First validate the files and complete comparison design:

```bash
python3 src/prepare_luna_inputs.py \
  --train /PATH/TO/LOCAL-DATA/ELLIPSE_Final_github_train.csv \
  --test /PATH/TO/LOCAL-DATA/ELLIPSE_Final_github_test.csv --check
```

Create a two-request example in a **new external directory**:

```bash
python3 src/prepare_luna_inputs.py \
  --train /PATH/TO/LOCAL-DATA/ELLIPSE_Final_github_train.csv \
  --test /PATH/TO/LOCAL-DATA/ELLIPSE_Final_github_test.csv \
  --limit 2 --output /PATH/TO/LOCAL-DATA/luna-example
```

Replace `--limit 2` with `--all` and choose another new directory to write
all 710,184 requests, in chunks grouped by cell and trait. This makes no
provider calls. A corpus-free example is also available:

```bash
python3 src/prepare_luna_inputs.py --synthetic-example \
  --output /PATH/TO/LOCAL-DATA/luna-synthetic
```

Inputs retain the original six-trait instructions and essay presentation
order, including reversed pairs. The writing-task prompt was not included.
Local manifests record hashes and a deterministic map to the packaged pair
IDs; these new request IDs are not the original provider custom IDs.
The author checked rendering against frozen original inputs; reviewers can
check the shipped resource hashes, corpus matching and complete design
without access to those private originals. Keep all generated inputs local;
they contain student writing and must never enter a reviewer ZIP or Git tree.

## Request new model judgments (optional, paid)

This separate workflow requires your own OpenAI access and budget, plus
`pairwiseLLM` 1.6.0 at Git SHA
`2526ab393d994530573af71bf15d89371c5f6228`, `jsonlite` and `digest`.
Install that exact package revision in your own R environment before use.
Inspect the two example requests **offline**, even if a provider key is set:

```bash
Rscript --vanilla src/rejudge_luna_pairs.R \
  --inputs /PATH/TO/LOCAL-DATA/luna-example \
  --chunk cell_001_chunk_0001.jsonl \
  --output /PATH/TO/LOCAL-DATA/luna-offline-check
```

To submit those same two requests, set `OPENAI_API_KEY` privately in your
environment, then explicitly authorize payment with a small cap:

```bash
Rscript --vanilla src/rejudge_luna_pairs.R \
  --inputs /PATH/TO/LOCAL-DATA/luna-example \
  --chunk cell_001_chunk_0001.jsonl \
  --output /PATH/TO/LOCAL-DATA/luna-new-judgments \
  --authorize-paid --max-paid-pairs 2
```

The requested model remains `gpt-5.6-luna`; it may no longer be accessible.
**New responses are not expected to match archived decisions exactly.**
The helper preserves the original Responses Batch parameters and labels
outputs as new judgments. It never substitutes another model. Resume a
submitted batch from its saved registry into another new directory:

```bash
Rscript --vanilla src/rejudge_luna_pairs.R \
  --resume /PATH/TO/LOCAL-DATA/luna-new-judgments \
  --output /PATH/TO/LOCAL-DATA/luna-new-judgments-resumed \
  --authorize-paid --max-paid-pairs 2
```

Process one chunk per submission; do not submit it again to retrieve results.
For larger paid runs, read `--help`; a full-study budget requires the separate
`--acknowledge-full-study-cost` flag. Keep batch registries, requests, errors
and all responses in external local directories, outside every Git repository.
New judgments do not replace the archived observations used by `run.py`.
