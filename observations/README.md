# Comparison records

These files contain the model's choices between pairs of essays. They support
the manuscript's reversed-order comparison summary and checks that the
statistical inputs refer to the same essays and scoring groups.

They contain no essay text, individual human ratings or fitted essay scores.
They nevertheless contain information that can be linked to the public
ELLIPSE corpus. Permission to share them must be reviewed separately.

| File | Contents |
| --- | --- |
| `data/judgments/cell_NNN.csv` | One file for each prompt and scoring trait. Each essay pair appears once, with its presentation order and the model's choice. |
| `data/judgments/reversals.csv` | Choices made when selected pairs were shown in the opposite order. These are used only for the reversed-order summary. |
| `data/essays/item_index.csv` | Essay codes, prompt codes and hashed keys that can be matched to public corpus records. |
| `data/design/cells.csv` | The prompt and trait for each comparison file, with expected counts. |
| `data/design/metadata.json` | File format, counts and interpretation of the recorded choices. |
| `data/SHA256SUMS` | File fingerprints used to detect missing or changed inputs. |

There are 676,326 original comparisons and 33,858 reversed-order comparisons
across 96 prompt and trait groups, 16 prompts, 1,714 essays and six traits.
Of the original comparisons, 608,652 were available for pair selection and
67,674 were reserved for evaluation. The `partition` column distinguishes
these two uses. Evaluation comparisons must not be used to select pairs or
fit scores from selected comparisons.

`first_id` and `second_id` preserve the displayed order. A `first_wins` value
of `1` means the model preferred the first essay; `0` means it preferred the
second. The reversed-order file links back to the original pair through
`base_pair_id`. Those observations are excluded from score fitting.

Essay codes are consistent across traits. Group numbers include gaps and
must not be renumbered. Hashed public keys are deterministic: a person with
the public corpus can identify matching records. These codes and hashes
must not be treated as a guarantee of anonymity.

Run `python3 run.py` from the package's top directory to check the files.
The full statistical run, `python3 run.py --analysis`, also calculates the
reversed-order summaries when the condition summaries are included.
See the main README for all commands,
expected outputs and the limits of reproduction. This package does not join
these records to individual human ratings.
