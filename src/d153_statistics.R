# Calculate only the manuscript's contrasts and stopping summaries.
D153_BUDGETS <- seq(2, 16, 2)
D153_AURC_WEIGHTS <- c(1, 2, 2, 2, 2, 2, 2, 1) / 14
D153_STRATEGIES <- c("random", "p50", "pollitt", "hybrid")

.d153s_fail <- function(...) stop(..., call. = FALSE)
.d153s_bind <- function(x) if (length(x)) do.call(rbind, x) else data.frame()
.d153s_key <- function(x, cols) do.call(paste, c(x[cols], sep = "\034"))
.d153s_required <- function(x, cols) {
  if (!is.data.frame(x) || !all(cols %in% names(x)))
    .d153s_fail("D153 metrics missing required columns: ", paste(setdiff(cols, names(x)), collapse = ", "))
}

d153_validate_metrics <- function(x) {
  keys <- c("prompt_key", "trait", "cell_index", "replicate_index", "strategy", "B", "estimator")
  .d153s_required(x, c(keys, "R2", "reliability", "log_loss", "spread_error"))
  if (!nrow(x) || anyNA(x[keys]) || any(vapply(x[keys], function(v) any(!nzchar(as.character(v))), logical(1))))
    .d153s_fail("D153 requires nonmissing metric identities")
  if (anyDuplicated(.d153s_key(x, keys))) .d153s_fail("D153 duplicate metric identity")
  if (!all(x$strategy %in% D153_STRATEGIES) || !all(x$estimator %in% c("B1", "B2", "F1", "F2", "F3")) ||
      !all(x$B %in% D153_BUDGETS)) .d153s_fail("D153 unknown strategy, estimator or budget")
  cells <- unique(x[c("prompt_key", "trait", "cell_index", "replicate_index")])
  if (anyDuplicated(cells$cell_index) || anyDuplicated(.d153s_key(cells, c("prompt_key", "trait"))))
    .d153s_fail("D153 cell/replay identity is not one-to-one")
  if (length(unique(cells$prompt_key)) != 16L || length(unique(cells$trait)) != 6L || nrow(cells) != 96L ||
      any(table(cells$prompt_key) != 6L)) .d153s_fail("D153 requires the original 16 prompts x six trait cell identities")
  for (nm in c("R2", "reliability", "log_loss", "spread_error"))
    if (!is.numeric(x[[nm]])) .d153s_fail("D153 metric must be numeric: ", nm)
  cells[order(cells$cell_index), , drop = FALSE]
}

d153_integrate <- function(B, value) {
  if (length(B) != 8L || anyDuplicated(B) || !setequal(B, D153_BUDGETS) ||
      length(value) != 8L || any(!is.finite(value))) return(NA_real_)
  sum(value[match(D153_BUDGETS, B)] * D153_AURC_WEIGHTS)
}

d153_infer <- function(x, expected_traits = sort(unique(x$trait))) {
  .d153s_required(x, c("prompt_key", "trait", "cell_index", "value"))
  if (anyDuplicated(.d153s_key(x, c("prompt_key", "trait")))) .d153s_fail("D153 duplicate inference cell")
  complete <- vapply(split(x, x$prompt_key), function(z) nrow(z) == 6L &&
    setequal(z$trait, expected_traits) && all(is.finite(z$value)), logical(1))
  retain <- names(complete)[complete]
  support <- x[c("prompt_key", "trait", "cell_index")]
  support$included <- support$prompt_key %in% retain
  support$reason <- ifelse(!is.finite(x$value), "invalid_matched_cell", ifelse(support$included,
    "complete_six_trait_prompt", "another_trait_missing_in_prompt"))
  z <- x[x$prompt_key %in% retain, , drop = FALSE]
  result <- data.frame(estimate = NA_real_, se = NA_real_, df_satterthwaite = NA_real_,
    ci95_low = NA_real_, ci95_high = NA_real_, p_value = NA_real_, n_prompts = length(retain),
    n_cells = nrow(z), target_prompts = 16L, target_traits = 6L, status = "nonestimable",
    reason = "fewer_than_two_complete_prompts", stringsAsFactors = FALSE)
  if (nrow(z)) result$estimate <- mean(z$value)
  if (length(retain) < 2L) return(list(summary = result, support = support))
  if (!requireNamespace("clubSandwich", quietly = TRUE) ||
      as.character(utils::packageVersion("clubSandwich")) != "0.7.0")
    .d153s_fail("D153 requires the existing pinned clubSandwich 0.7.0; do not install dependencies")
  z$trait <- factor(z$trait, levels = expected_traits)
  fit <- stats::lm(value ~ 0 + trait, data = z)
  if (all(abs(stats::residuals(fit)) <= 100 * .Machine$double.eps * max(abs(z$value), .Machine$double.xmin))) {
    result$reason <- "CR2_zero_residual_variance_after_trait_adjustment"
    return(list(summary = result, support = support))
  }
  C <- matrix(rep(1 / 6, 6), nrow = 1L, dimnames = list("equal_trait_mean", names(stats::coef(fit))))
  inference <- tryCatch(as.data.frame(clubSandwich::linear_contrast(fit, vcov = "CR2",
    cluster = z$prompt_key, contrasts = C, test = "Satterthwaite", p_values = TRUE,
    adjustment_method = "none")), error = identity)
  if (inherits(inference, "error")) {
    result$reason <- paste0("CR2_not_estimable: ", conditionMessage(inference))
  } else {
    if (!identical(names(inference), c("Coef", "Est", "SE", "df", "CI_L", "CI_U", "p_val")))
      .d153s_fail("D153 pinned clubSandwich output schema changed")
    result[1, c("estimate", "se", "df_satterthwaite", "ci95_low", "ci95_high", "p_value")] <-
      inference[1, c("Est", "SE", "df", "CI_L", "CI_U", "p_val")]
    ok <- all(is.finite(unlist(result[c("estimate", "se", "df_satterthwaite", "ci95_low", "ci95_high", "p_value")]))) &&
      result$df_satterthwaite > 0 && result$se > 0
    result$status <- if (ok) "estimable" else "nonestimable"
    result$reason <- if (ok && length(retain) == 16L) "complete_target_support" else if (ok)
      "restricted_to_complete_six_trait_prompts" else "CR2_nonfinite_or_zero_variance"
  }
  list(summary = result, support = support)
}

d153_holm <- function(x, n) {
  if (nrow(x) != n) .d153s_fail("D153 incorrect primary family size")
  x$p_holm <- NA_real_
  keep <- is.finite(x$p_value) & x$status == "estimable"
  # n retains the full prespecified family even when some tests are unavailable.
  x$p_holm[keep] <- stats::p.adjust(x$p_value[keep], method = "holm", n = n)
  x
}

d153_crossing <- function(B, value, threshold) {
  if (anyDuplicated(B) || length(B) != length(value) || !all(B %in% D153_BUDGETS))
    .d153s_fail("D153 invalid threshold trajectory")
  full <- value[match(D153_BUDGETS, B)]
  finite <- is.finite(full)
  hit <- which(finite & full >= threshold)
  first <- if (length(hit)) hit[1] else NA_integer_
  first_known <- !is.na(first) && all(finite[seq_len(first)])
  sustained <- which(vapply(seq_along(full), function(i) all(finite[i:8]) && all(full[i:8] >= threshold), logical(1)))
  data.frame(first_B = if (length(hit)) D153_BUDGETS[first] else NA_real_,
    first_known = first_known, sustained_B = if (length(sustained)) D153_BUDGETS[sustained[1]] else NA_real_,
    status = if (length(hit)) if (first_known) "attained" else "observed_crossing_prior_unresolved" else
      if (all(finite)) "right_censored" else "unresolved_missing", n_valid = sum(finite),
    cap_B = 16, stringsAsFactors = FALSE)
}

d153_thresholds <- function(x, cells) {
  stopping <- list()
  for (i in seq_len(nrow(cells))) for (s in D153_STRATEGIES) for (e in c("B1", "B2", "F1")) {
    z <- x[x$cell_index == cells$cell_index[i] & x$strategy == s & x$estimator == e, , drop = FALSE]
    z <- z[order(z$B), , drop = FALSE]
    N <- if ("N" %in% names(z) && nrow(z) && length(unique(z$N)) == 1L && is.finite(z$N[1])) z$N[1] else NA_real_
    identity <- cbind(cells[i, , drop = FALSE], data.frame(strategy = s, estimator = e))
    for (threshold in c(.90, .70)) {
      r <- d153_crossing(z$B, z$R2, threshold)
      q <- d153_crossing(z$B, z$reliability, threshold)
      at_stop <- match(q$first_B, z$B)
      premature <- if (q$first_known && !is.na(at_stop) && is.finite(z$R2[at_stop])) z$R2[at_stop] < threshold else NA
      ready_index <- match(r$first_B, D153_BUDGETS)
      observed_I <- z$reliability[match(D153_BUDGETS, z$B)]
      ready_without_stop <- if (r$first_known && !is.na(ready_index) && all(is.finite(observed_I[seq_len(ready_index)])))
        !any(observed_I[seq_len(ready_index)] >= threshold) else NA
      delay <- if (r$first_known && q$first_known) q$first_B - r$first_B else NA_real_
      stopping[[length(stopping) + 1L]] <- cbind(identity, data.frame(threshold = threshold,
        rule = if (e == "F1") "SSR_threshold_only" else "EAP_threshold_only",
        stop_B = q$first_B, readiness_B = r$first_B, stop_status = q$status, readiness_status = r$status,
        stop_first_known = q$first_known, readiness_first_known = r$first_known,
        stop_sustained_B = q$sustained_B, readiness_sustained_B = r$sustained_B,
        premature_stop = premature, readiness_without_stopping = ready_without_stop,
        stop_minus_readiness_B = delay, stop_minus_readiness_M = delay * N / 2,
        stop_M = q$first_B * N / 2, readiness_M = r$first_B * N / 2,
        observed_extra_M_to_cap = if (r$first_known && q$status == "right_censored") (16 - r$first_B) * N / 2 else NA_real_,
        cap_B = 16, stringsAsFactors = FALSE))
    }
  }
  list(stopping = .d153s_bind(stopping))
}

# Descriptive rates have explicit classified denominators. Unconditional
# endpoints use only fully classified six-trait prompts; conditional premature
# stopping and missed readiness retain their observed event denominators.
d153_stopping_summaries <- function(stopping) {
  grouped <- split(stopping, .d153s_key(stopping, c("estimator", "strategy", "threshold")))
  by_prompt <- list(); summaries <- list()
  for (z in grouped) for (endpoint in c("stop_attained_by_cap", "readiness_attained_by_cap",
      "premature_stop", "readiness_without_stopping")) {
    conditional <- endpoint %in% c("premature_stop", "readiness_without_stopping")
    value <- switch(endpoint,
      stop_attained_by_cap = ifelse(is.finite(z$stop_B), TRUE, ifelse(z$stop_status == "right_censored", FALSE, NA)),
      readiness_attained_by_cap = ifelse(is.finite(z$readiness_B), TRUE, ifelse(z$readiness_status == "right_censored", FALSE, NA)),
      premature_stop = z$premature_stop,
      readiness_without_stopping = z$readiness_without_stopping)
    eligible <- switch(endpoint, premature_stop = z$stop_first_known,
      readiness_without_stopping = z$readiness_first_known, rep(TRUE, nrow(z)))
    z$value <- value; z$eligible <- eligible
    current <- lapply(split(z, z$prompt_key), function(q) {
      observed <- q$eligible & !is.na(q$value)
      complete <- if (conditional) any(observed) else nrow(q) == 6L && all(observed)
      data.frame(prompt_key = q$prompt_key[1], estimator = q$estimator[1], strategy = q$strategy[1],
        threshold = q$threshold[1], endpoint = endpoint,
        rate = if (complete) mean(q$value[observed]) else NA_real_,
        n_observed = sum(observed), n_eligible = sum(q$eligible), n_missing = sum(q$eligible & is.na(q$value)),
        n_events = sum(q$value[observed]), target_traits = 6L,
        weighting = if (conditional) "within_prompt_classified_events" else "six_equal_traits",
        stringsAsFactors = FALSE)
    })
    p <- .d153s_bind(current)
    by_prompt[[length(by_prompt) + 1L]] <- p
    summaries[[length(summaries) + 1L]] <- data.frame(estimator = z$estimator[1], strategy = z$strategy[1],
      threshold = z$threshold[1], endpoint = endpoint,
      rate = if (any(is.finite(p$rate))) mean(p$rate[is.finite(p$rate)]) else NA_real_,
      n_prompts = sum(is.finite(p$rate)), n_observed = sum(p$n_observed[is.finite(p$rate)]),
      n_eligible = sum(p$n_eligible), n_missing = sum(p$n_missing), n_events = sum(p$n_events[is.finite(p$rate)]),
      n_classified_all = sum(p$n_observed),
      n_classified_excluded_with_incomplete_prompt = sum(p$n_observed[!is.finite(p$rate)]),
      n_known_stops = sum(z$stop_first_known), n_observed_stop_hits = sum(is.finite(z$stop_B)),
      n_stop_right_censored = sum(z$stop_status == "right_censored"),
      n_stop_unresolved = sum(z$stop_status %in% c("unresolved_missing", "observed_crossing_prior_unresolved")),
      n_known_readiness = sum(z$readiness_first_known), n_observed_readiness_hits = sum(is.finite(z$readiness_B)),
      n_readiness_right_censored = sum(z$readiness_status == "right_censored"),
      n_readiness_unresolved = sum(z$readiness_status %in% c("unresolved_missing", "observed_crossing_prior_unresolved")),
      weighting = if (conditional) "equal_prompt_classified_event_rates" else "equal_prompt_six_equal_traits",
      target_prompts = 16L, target_traits = 6L, stringsAsFactors = FALSE)
  }
  list(stopping_by_prompt = .d153s_bind(by_prompt), stopping_summary = .d153s_bind(summaries))
}

