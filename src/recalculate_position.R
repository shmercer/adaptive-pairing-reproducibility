#!/usr/bin/env Rscript
# Recalculate position and lapse summaries from stored model draws.
# Epsilon is the lapse probability; beta is the first-position preference.
position_need <- function(ok, message) if (!isTRUE(ok)) stop(message, call. = FALSE)
POSITION_SOURCE_SHA <- "285f970e88ffc95724a5c8585ddd8fcb8868a09edb8759bf72e21d32735c2b6b"
POSITION_PACKAGE_SHA <- "4c4c01453077f90e987040c6a3c3d3cd711c6f21"
POSITION_STAN_SHA <- "7868ec442712f00492ad2f4191ce34782cbd9fd57be80f6c411804d957ec014f"
POSITION_FILES <- c(paste0("joint-", 1:4, ".csv"), "provenance.json")
position_sha <- function(path) digest::digest(file = path, algo = "sha256")
position_link <- function(path) {
  link <- Sys.readlink(path)
  !is.na(link) && nzchar(link)
}
position_regular <- function(path) {
  link <- Sys.readlink(path)
  file.exists(path) && !dir.exists(path) && (is.na(link) || !nzchar(link))
}
position_read <- function(directory, kernel) {
  for (p in c("digest", "jsonlite"))
    position_need(requireNamespace(p, quietly = TRUE), paste("Missing local dependency:", p))
  files <- list.files(directory, all.files = TRUE, no.. = TRUE)
  position_need(setequal(files, c(POSITION_FILES, "SHA256SUMS")) &&
    all(vapply(file.path(directory, files), position_regular, TRUE)),
    "Unexpected, absent or symlinked position intermediate")
  sums <- readLines(file.path(directory, "SHA256SUMS"), warn = FALSE)
  position_need(length(sums) == length(POSITION_FILES) &&
    all(grepl("^[a-f0-9]{64}  [a-z0-9.-]+$", sums)), "Invalid position SHA manifest")
  names <- substring(sums, 67L)
  position_need(!anyDuplicated(names) && setequal(names, POSITION_FILES),
                "Position manifest membership differs")
  for (i in seq_along(names)) position_need(identical(
    position_sha(file.path(directory, names[i])), substr(sums[i], 1L, 64L)),
    "Position intermediate SHA mismatch")
  p <- jsonlite::fromJSON(file.path(directory, "provenance.json"))
  expected <- c("schema", "source_script_sha256", "kernel_sha256", "package_sha",
    "stan_sha256", "w012_audit_sha256", "w013_scores_sha256", "cell_audit_sha256",
    "posterior_set_sha256", "private_manifest_sha256", "seed", "n_cells",
    "draws_per_cell", "R", "algorithm", "scope")
  position_need(setequal(names(p), expected) &&
    identical(p$schema, "JEM-position-joint-v1") &&
    identical(p$source_script_sha256, POSITION_SOURCE_SHA) &&
    identical(p$kernel_sha256, position_sha(kernel)) &&
    identical(p$package_sha, POSITION_PACKAGE_SHA) && identical(p$stan_sha256, POSITION_STAN_SHA) &&
    identical(p$w012_audit_sha256, "8dc0d5cedf6a81aa11098b0a0b7f4a55d3219fc39a8dc145dc0dc1f77c7e9aef") &&
    identical(p$w013_scores_sha256, "98b68a081abbe1af5e83f5e538e240a779c489fe751601f1d5425711609d805c") &&
    identical(p$cell_audit_sha256, "7f3d3c77afd03db2c35a15352dc94e37d1a12bb9d865f711d1886f4703438eb9") &&
    all(grepl("^[a-f0-9]{64}$", c(p$posterior_set_sha256, p$private_manifest_sha256))) &&
    identical(p$seed, 20261028L) && identical(p$n_cells, 96L) &&
    identical(p$draws_per_cell, 4000L) && identical(p$R, "4.6.1") &&
    identical(p$algorithm, "paired within cell; independent resampling across 96 cells; panel median per draw; type-7 quantiles") &&
    identical(p$scope, "conditional on original W012 posteriors; no independent model fitting"),
    "Position provenance differs from original model/aggregation contract")
  parts <- lapply(seq_len(4L), function(i) {
    z <- utils::read.csv(file.path(directory, paste0("joint-", i, ".csv")), check.names = FALSE)
    position_need(identical(names(z), c("slot", "draw", "epsilon", "beta")) &&
      nrow(z) == 96000L && !anyNA(z) &&
      identical(z$slot, rep(seq_len(96L), each = 1000L)) &&
      identical(z$draw, rep(seq.int((i - 1L)*1000L + 1L, i*1000L), 96L)) &&
      is.numeric(z$epsilon) && is.numeric(z$beta) &&
      all(is.finite(z$epsilon)) && all(is.finite(z$beta)) &&
      all(z$epsilon >= 0 & z$epsilon <= 1),
      "Invalid, reordered, duplicated or incomplete paired position draws")
    z
  })
  # Slots keep draws from one fitted model together without identifying its essays.
  lapply(seq_len(96L), function(i) {
    z <- do.call(rbind, lapply(parts, function(x) x[x$slot == i, , drop = FALSE]))
    position_need(identical(z$draw, seq_len(4000L)), "Joint draw identity lost")
    data.frame(epsilon = z$epsilon, beta = z$beta,
      first_probability = (1-z$epsilon)*plogis(z$beta) + z$epsilon/2) |>
      transform(epsilon = as.double(epsilon), beta = as.double(beta))
  })
}
position_check_reported <- function(overall) {
  position_need(identical(as.character(overall$parameter), c("epsilon", "beta", "first_probability")),
                "Position summary parameter identity differs")
  values <- as.matrix(overall[c("estimate", "cri_lower", "cri_upper")])
  shown <- c(sprintf("%.3f", 100*values[1, ]), sprintf("%.3f", values[2, ]),
             sprintf("%.1f", 100*values[3, ]))
  position_need(identical(shown, c("0.113", "0.088", "0.142", "1.301", "1.254", "1.346",
                                  "78.5", "77.7", "79.3")),
                "Position summaries do not match the manuscript at reported precision")
  invisible(shown)
}
position_calculate <- function(directory, kernel) {
  position_need(identical(as.character(getRversion()), "4.6.1"), "Original aggregation requires R 4.6.1")
  fits <- position_read(directory, kernel)
  env <- new.env(parent = globalenv())
  sys.source(kernel, envir = env)
  result <- env$synthesize(fits)
  position_check_reported(result$overall)
  result$overall[c("parameter", "estimate", "cri_lower", "cri_upper",
                   "n_cells", "n_prompts", "draws_per_cell")]
}
position_main <- function() {
  args <- commandArgs(TRUE)
  position_need(length(args) == 2L && sum(startsWith(args, "--data=")) == 1L &&
    sum(startsWith(args, "--output=")) == 1L, "Use --data=DIR --output=NEW.csv")
  directory <- sub("^--data=", "", args[startsWith(args, "--data=")])
  output <- sub("^--output=", "", args[startsWith(args, "--output=")])
  script <- sub("^--file=", "", commandArgs()[startsWith(commandArgs(), "--file=")])
  kernel <- file.path(dirname(normalizePath(script)), "position-kernel.R")
  position_need(!file.exists(output) && !dir.exists(output) && !position_link(output),
                "Position output must be new")
  root <- normalizePath(file.path(dirname(script), ".."), mustWork = TRUE)
  parent <- normalizePath(dirname(output), mustWork = TRUE)
  position_need(startsWith(parent, paste0(root, "/output")) &&
    (identical(parent, file.path(root, "output")) || startsWith(parent, paste0(root, "/output/"))),
    "Position output must be inside reviewer output/")
  result <- position_calculate(directory, kernel)
  utils::write.csv(result, output, row.names = FALSE)
  cat("PASS: all three position/lapse estimates and CrIs match reported precision; conditional posterior recalculation, zero fits\n")
}
if (sys.nframe() == 0L) position_main()
