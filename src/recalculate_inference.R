#!/usr/bin/env Rscript
# Recalculate the manuscript's statistical comparisons from full-precision metrics.
# Use writing prompts as the independent groups for uncertainty estimates.
# The statistical functions are extracted from the verified original source.
options(stringsAsFactors = FALSE, digits = 17)
Sys.umask("0077")
fail <- function(...) stop(paste0(..., collapse = ""), call. = FALSE)
need <- function(ok, ...) if (!isTRUE(ok)) fail(...)
args <- commandArgs(trailingOnly = TRUE)
if (identical(args, "--help")) {
  cat("Recalculate the reported statistical comparisons without refitting models.\n",
      "Run python3 run.py --analysis from the extracted package.\n",
      "For a direct R run, supply absolute paths:\n",
      "Rscript --vanilla src/recalculate_inference.R ",
      "--root=PACKAGE_DIRECTORY --output=PACKAGE_DIRECTORY/output/NEW_DIRECTORY\n", sep = "")
  quit(status = 0L)
}
need(length(args) == 2L && all(grepl("^--(root|output)=", args)),
     "Specify --root=ABS --output=ABS (new directory)")
keys <- sub("^--([^=]+)=.*$", "\\1", args)
need(!anyDuplicated(keys) && setequal(keys, c("root", "output")),
     "Invalid/duplicate CLI keys")
opts <- stats::setNames(sub("^--[^=]+=", "", args), keys)
need(all(startsWith(opts, "/")), "All paths must be absolute")
root <- normalizePath(opts[["root"]], mustWork = TRUE)
output <- opts[["output"]]
need(!file.exists(output), "Output exists; choose a new result directory")
# Keep generated results inside output/, including when this script is run directly.
need(startsWith(output, paste0(root, "/output/")),
     "Analysis output must be inside the reviewer package output/ directory")
parent_dir <- dirname(output)
if (!dir.exists(parent_dir))
  dir.create(parent_dir, recursive = TRUE, showWarnings = FALSE, mode = "0700")
need(dir.exists(parent_dir), "Could not initialize analysis output parent")
parent <- normalizePath(parent_dir, mustWork = TRUE)
output <- file.path(parent, basename(output))
need(!identical(root, output), "Output cannot equal input")
for (package in c("clubSandwich", "digest"))
  need(requireNamespace(package, quietly = TRUE),
       "Missing R package: ", package)
need(as.character(utils::packageVersion("clubSandwich")) == "0.7.0",
     "Requires original clubSandwich 0.7.0 for exact CR2 inference")
need(as.character(getRversion()) == "4.6.1",
     "Requires original R 4.6.1 for exact numerical comparison")

src <- file.path(root, "src", "d153_statistics.R")
need(file.exists(src), "Missing standalone pure D153 statistics source")
source(src, local = TRUE)
expected_columns <- c("cell_index", "prompt_id", "trait", "replicate_index",
                      "strategy", "B", "estimator", "N", "M", "replay_seed",
                      "R2", "reliability", "log_loss", "spread_error")
condition_root <- file.path(root, "conditions")
files <- c("data/condition_metrics.csv", "data/metadata.json")
manifest <- file.path(condition_root, "data/SHA256SUMS")
need(file.exists(manifest), "Missing SHA256 manifest of condition metrics")
lines <- readLines(manifest, warn = FALSE)
need(length(lines) == 2L, "Unexpected condition manifest size")
for (line in lines) {
  parts <- strsplit(trimws(line), "[[:space:]]+")[[1L]]
  need(length(parts) == 2L && parts[2L] %in% files &&
       identical(digest::digest(file = file.path(condition_root, parts[2L]),
                                algo = "sha256"), parts[1L]),
       "Condition manifest SHA mismatch")
}
metrics <- utils::read.csv(
  file.path(condition_root, "data/condition_metrics.csv"),
  check.names = FALSE, stringsAsFactors = FALSE)
need(identical(names(metrics), expected_columns) && nrow(metrics) == 10944L &&
     !any(metrics$strategy == "hybrid" & metrics$estimator %in% c("F2", "F3")),
     "Unrounded 10944-row manuscript condition panel not present")
design <- utils::read.csv(
  file.path(root, "observations/data/design/cells.csv"),
  stringsAsFactors = FALSE)
need(nrow(design) == 96L && setequal(metrics$cell_index, design$cell_id),
     "W011/D153 cell identities differ")
at <- match(metrics$cell_index, design$cell_id)
need(all(metrics$prompt_id == design$prompt_id[at]) &&
     all(metrics$trait == design$trait[at]) &&
     all(metrics$N == design$n_items[at]) &&
     all(metrics$replay_seed == 114000000 + 10 * metrics$cell_index +
                                    metrics$replicate_index),
     "Prompt/trait/N or original D136 replay seed differs")
metrics$prompt_key <- metrics$prompt_id  # group traits from the same writing prompt
cells <- d153_validate_metrics(metrics)
need(nrow(cells) == 96L && length(unique(cells$prompt_key)) == 16L,
     "Original 16-prompt inferential support missing")
metric_fields <- c("R2", "reliability", "log_loss", "spread_error")
need(all(vapply(metrics[metric_fields], is.numeric, TRUE)),
     "Missing numeric model performance measures")

compare <- function(actual, frozen, key, cols, label) {
  need(nrow(actual) == nrow(frozen),
       label, " number of contrasts changed")
  ac <- do.call(paste, c(actual[key], sep = "\x1f"))
  fr <- do.call(paste, c(frozen[key], sep = "\x1f"))
  need(!anyDuplicated(ac) && !anyDuplicated(fr) && setequal(ac, fr),
       label, " contrasts or identities differ")
  matched <- frozen[match(ac, fr), , drop = FALSE]
  for (field in cols) {
    need(field %in% names(actual) && field %in% names(matched),
         label, " missing field ", field)
    a <- actual[[field]]
    b <- matched[[field]]
    if (is.numeric(a) && is.numeric(b)) {
      need(identical(is.finite(a), is.finite(b)),
           label, " nonfinite status differs in ", field)
      good <- is.finite(a)
      if (any(good)) {
        delta <- abs(a[good] - b[good])
        # Model statistics should replicate within a tiny fraction of a
        # displayed 0.001 unit, even across CPU/toolchain roundoff.
        tolerance <- if (field %in% c("p_value", "p_holm", "p_holm30")) {
          pmax(1e-14, 1e-6 * abs(b[good]))
        } else pmax(1e-10, 1e-9 * abs(b[good]))
        need(all(delta <= tolerance),
             label, " original full-precision numerical mismatch: ", field)
      }
    } else need(identical(as.character(a), as.character(b)),
                label, " original categorical mismatch: ", field)
  }
  invisible(TRUE)
}
infer_cols <- c("estimate", "se", "df_satterthwaite", "ci95_low",
                "ci95_high", "p_value", "n_prompts", "n_cells",
                "target_prompts", "target_traits", "status", "reason")

# Compare pairing methods for recovery and for reliability minus recovery.
# Average the budget checkpoints using the manuscript's trapezoidal weights.
integrated_effect <- function(first, second, estimators, metric) {
  vapply(cells$cell_index, function(ci) {
    differences <- vapply(estimators, function(e) {
      integrate <- function(strategy) {
        z <- metrics[metrics$cell_index == ci & metrics$strategy == strategy &
                       metrics$estimator == e, , drop = FALSE]
        value <- if (metric == "aurc") z$R2 else z$reliability - z$R2
        d153_integrate(z$B, value)
      }
      integrate(first) - integrate(second)
    }, 0.0)
    need(all(is.finite(differences)), "Missing matched integrated effect")
    mean(differences)
  }, 0.0)
}
infer_effect <- function(value, analysis, family, id, outcome, direction) {
  cbind(data.frame(analysis = analysis, family = family, contrast_id = id,
                   outcome = outcome, direction = direction),
        d153_infer(cbind(cells, value = value))$summary)
}
rq1_rows <- list(); rq1_estimator_rows <- list()
for (s in c("p50", "pollitt", "hybrid")) {
  rq1_rows[[length(rq1_rows) + 1L]] <- infer_effect(
    integrated_effect(s, "random", c("B1", "B2", "F1"), "aurc"),
    "RQ1", "Holm-3", paste0(s, "-random"), "aurc", "higher_favors_first")
  for (e in c("B1", "B2", "F1"))
    rq1_estimator_rows[[length(rq1_estimator_rows) + 1L]] <- infer_effect(
      integrated_effect(s, "random", e, "aurc"), "RQ1-estimator", "descriptive",
      paste0(e, ":", s, "-random"), "aurc", "higher_favors_first")
}
rq1 <- d153_holm(do.call(rbind, rq1_rows), 3L)
check_rq1 <- utils::read.csv(file.path(root, "data/primary/rq1.csv"))
compare(rq1, check_rq1, "contrast_id",
        c(infer_cols, "p_holm"), "RQ1 AURC Holm-3")
rq1_estimator <- do.call(rbind, rq1_estimator_rows)
compare(rq1_estimator, utils::read.csv(file.path(root, "data/primary/rq1_estimator.csv")),
        "contrast_id", infer_cols, "RQ1 estimator-specific AURC")
stop_summary <- d153_stopping_summaries(d153_thresholds(metrics, cells)$stopping)$stopping_summary
frozen_stops <- utils::read.csv(
  file.path(root, "data/primary/stopping_summary.csv"))
compare(stop_summary, frozen_stops,
        c("estimator", "strategy", "threshold", "endpoint"),
        c("rate", "n_prompts", "n_observed", "n_eligible",
          "n_missing", "n_events", "n_classified_all",
          "n_known_stops", "n_known_readiness", "weighting"),
        "RQ2 stopping .90/.70")

# F1 uses six checkpoints from 6 to 16 comparisons per essay; Bayesian models use 2–16.
integrate_gap <- function(cell, strategy) {
  z <- metrics[metrics$cell_index == cell & metrics$strategy == strategy &
                 metrics$estimator == "F1" & metrics$B %in% seq(6, 16, 2), ]
  budgets <- seq(6, 16, 2)
  need(nrow(z) == 6L && setequal(z$B, budgets),
       "Missing F1 B6–16 checkpoint")
  gaps <- (z$reliability - z$R2)[match(budgets, z$B)]
  need(all(is.finite(gaps)), "Missing F1 B6–16 signed SSR-recovery")
  sum(gaps * c(1, 2, 2, 2, 2, 1) / 10)
}
f1_rows <- list()
for (compare_strategy in c("random", "pollitt", "hybrid")) {
  effect <- vapply(cells$cell_index, function(ci)
    integrate_gap(ci, "p50") - integrate_gap(ci, compare_strategy), 0.0)
  fitted <- d153_infer(cbind(cells, value = effect))$summary
  need(fitted$n_prompts == 16L && fitted$n_cells == 96L &&
       fitted$status == "estimable", "F1 B6–16 prompt coverage differs")
  f1_rows[[length(f1_rows) + 1L]] <- cbind(
    data.frame(analysis = "RQ2", family = "Holm-6",
               contrast_id = paste0("F1:p50-", compare_strategy),
               outcome = "integrated_gap",
               direction = "positive_means_larger_reliability_minus_recovery"),
    fitted, p_holm = NA_real_)
}
bayes_rows <- list(); rq2_estimator_rows <- list()
for (s in c("random", "pollitt", "hybrid")) {
  bayes_rows[[length(bayes_rows) + 1L]] <- cbind(infer_effect(
    integrated_effect("p50", s, c("B1", "B2"), "gap"), "RQ2", "Holm-6",
    paste0("Bayesian:p50-", s), "integrated_gap",
    "positive_means_larger_reliability_minus_recovery"), p_holm = NA_real_)
  for (e in c("B1", "B2"))
    rq2_estimator_rows[[length(rq2_estimator_rows) + 1L]] <- infer_effect(
      integrated_effect("p50", s, e, "gap"), "RQ2-estimator", "descriptive",
      paste0(e, ":p50-", s), "integrated_gap",
      "positive_means_larger_reliability_minus_recovery")
}
bayes <- do.call(rbind, bayes_rows)
rq2_estimator <- do.call(rbind, rq2_estimator_rows)
compare(rq2_estimator, utils::read.csv(file.path(root, "data/primary/rq2_estimator.csv")),
        "contrast_id", infer_cols, "RQ2 separate Bayesian estimators")
need(nrow(bayes) == 3L, "Missing three original Bayesian RQ2 contrasts")
rq2 <- d153_holm(rbind(bayes, do.call(rbind, f1_rows)), n = 6L)
frozen_bayes <- utils::read.csv(file.path(root, "data/primary/rq2.csv"))
frozen_bayes <- frozen_bayes[
  grepl("^Bayesian:", frozen_bayes$contrast_id), , drop = FALSE]
compare(rq2[grepl("^Bayesian:", rq2$contrast_id), ], frozen_bayes,
        "contrast_id", infer_cols, "RQ2 B2–16 Bayesian")
original_f1 <- utils::read.csv(file.path(root, "data/ssr/contrasts.csv"))
original_f1 <- original_f1[original_f1$lower_B == 6, , drop = FALSE]
recalc_f1 <- rq2[grepl("^F1:", rq2$contrast_id), , drop = FALSE]
recalc_f1$contrast_id <- sub("^F1:", "", recalc_f1$contrast_id)
compare(recalc_f1, original_f1, "contrast_id", infer_cols,
        "RQ2 post hoc F1 B6–16")
need(all(is.finite(rq2$p_holm)), "RQ2 exploratory Holm-6 missing")

# Compare the five estimators using matched methods and comparison budgets.
strategies <- c("random", "p50", "pollitt")
budgets <- c(4L, 8L, 16L)
pairs <- c("B1-B2", "B2-F1", "B2-F2", "B2-F3", "B1-F1",
           "B1-F2", "B1-F3", "F2-F1", "F3-F1", "F3-F2")
rq3_rows <- list()
conditions <- metrics[metrics$strategy %in% strategies &
                        metrics$B %in% budgets, , drop = FALSE]
need(nrow(conditions) == 4320L, "Incomplete RQ3 matched five-estimator panel")
for (outcome in c("R2", "log_loss", "spread_error")) for (pair in pairs) {
  ids <- strsplit(pair, "-", fixed = TRUE)[[1L]]
  effect <- vapply(cells$cell_index, function(ci) {
    x <- conditions[conditions$cell_index == ci, , drop = FALSE]
    need(nrow(x) == 45L, "Missing matched RQ3 cell")
    grid <- expand.grid(strategy = strategies, B = budgets)
    get <- function(estimator) {
      z <- x[x$estimator == estimator, , drop = FALSE]
      at <- match(paste(grid$strategy, grid$B, sep = "|"),
                  paste(z$strategy, z$B, sep = "|"))
      need(length(at) == 9L && !anyNA(at), "RQ3 unmatched estimator history")
      z[[outcome]][at]
    }
    a <- get(ids[1L]); b <- get(ids[2L])
    need(all(is.finite(a)) && all(is.finite(b)), "RQ3 missing finite conditions")
    mean(a - b)
  }, 0.0)
  fitted <- d153_infer(cbind(cells, value = effect))$summary
  need(fitted$status == "estimable" &&
       fitted$n_prompts == 16L && fitted$n_cells == 96L,
       "RQ3 missing original 16-prompt inference support")
  rq3_rows[[length(rq3_rows) + 1L]] <- cbind(
    data.frame(contrast_id = pair, outcome = outcome), fitted)
}
rq3 <- d153_holm(do.call(rbind, rq3_rows), 30L)
names(rq3)[names(rq3) == "p_holm"] <- "p_holm30"
expected_rq3 <- utils::read.csv(
  file.path(root, "data/estimator/rq3_holm30.csv"))
compare(rq3, expected_rq3, c("contrast_id", "outcome"),
        c(infer_cols, "p_holm30"), "RQ3 complete post hoc Holm-30")

# Save the recalculated values and a short record of the checks performed.
dir.create(output, showWarnings = FALSE, mode = "0700")
need(dir.exists(output), "Cannot create analysis output directory")
write_output <- function(x, name) {
  utils::write.csv(x, file.path(output, name), row.names = FALSE)
}
write_output(rq1, "rq1_recalculated.csv")
write_output(rq1_estimator, "rq1_estimator_recalculated.csv")
write_output(rq2, "rq2_b6_combined_holm6.csv")
write_output(rq2_estimator, "rq2_bayes_estimator_recalculated.csv")
write_output(rq3, "rq3_recalculated_holm30.csv")
write_output(stop_summary, "stopping_recalculated.csv")
writeLines(c(
  "Independent 16-prompt RQ1/RQ2/RQ3 statistical recalculation from",
  "SHA-verified, full-precision 10944-row manuscript projection of D153 metrics.",
  "CR2 clubSandwich 0.7.0, Satterthwaite; full original 96 cells.",
  "RQ1: normalized trapezoidal B2-B16 AURC, 3 contrasts Holm-3.",
  "RQ2: Bayes B2-B16 + exploratory F1 B6-B16, 6 contrasts Holm-6.",
  "RQ3: 10 estimator pairs x 3 outcomes, original 9 matched",
  "conditions per cell, 16 prompt clusters, joint Holm-30.",
  "STOPPING: independently recomputed 0.90/0.70 summaries.",
  "All original full-precision inferential fields numerically checked.",
  "No model refits, item-score validity, native bootstrap, provider calls.",
  "Original data files and frozen statistical releases unchanged."),
  file.path(output, "VALIDATION.txt"))
cat("PASS: RQ1 Holm-3, RQ2 original Bayesian + B6–16 post hoc Holm-6,",
    "RQ3 post hoc Holm-30, original 16-prompt CR2/Satterthwaite\n")
cat("PASS: stopping .90/.70; all full-precision contrasts checked against verified releases\n")
cat("NO estimator refits, Bayesian sampler runs or F3 bootstrap attempts performed\n")
