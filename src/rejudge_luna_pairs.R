#!/usr/bin/env Rscript
# Build and inspect requests offline by default. Paid operations require explicit
# authorization and a cap. Every run uses a new external local output directory.
# New judgments never replace the archived observations.

LUNA_PACKAGE_SHA <- "2526ab393d994530573af71bf15d89371c5f6228"
LUNA_MODEL <- "gpt-5.6-luna"
LUNA_CONTRACT_SHA <- "4c20ceec2134dd4db99aa1436d8d2b5578f9e54e595c954872772a48d2430350"
luna_need <- function(ok, message) if (!isTRUE(ok)) stop(message, call. = FALSE)
luna_sha <- function(path) digest::digest(file = path, algo = "sha256")
luna_text_sha <- function(text) digest::digest(enc2utf8(text), algo = "sha256", serialize = FALSE)
luna_text <- function(path) rawToChar(readBin(path, "raw", n = file.info(path)$size))
luna_json <- function(value, path) {
  luna_need(!file.exists(path), "Refusing to overwrite a local result")
  jsonlite::write_json(value, path, auto_unbox = TRUE, pretty = TRUE, null = "null")
}
luna_jsonl <- function(rows, path) {
  luna_need(!file.exists(path), "Refusing to overwrite a local result")
  con <- file(path, "wt", encoding = "UTF-8"); on.exit(close(con))
  for (row in rows) writeLines(jsonlite::toJSON(row, auto_unbox = TRUE, null = "null"), con)
}
luna_package <- function() {
  for (pkg in c("jsonlite", "digest", "pairwiseLLM"))
    luna_need(requireNamespace(pkg, quietly = TRUE), paste("Required package:", pkg))
  d <- utils::packageDescription("pairwiseLLM")
  luna_need(identical(d$Version, "1.6.0") && identical(d$RemoteSha, LUNA_PACKAGE_SHA),
            "Install the exact documented pairwiseLLM 1.6.0 Git SHA; no model/package substitution")
}
luna_within <- function(path, root) identical(path, root) || startsWith(path, paste0(root, "/"))
luna_external <- function(path, package_root, new = FALSE) {
  expanded <- path.expand(path)
  if (new) {
    luna_need(!file.exists(expanded) && !dir.exists(expanded), "Use a NEW external output directory")
    luna_need(dir.exists(dirname(expanded)), "Create the external parent directory first")
    resolved <- file.path(normalizePath(dirname(expanded), mustWork = TRUE), basename(expanded))
  } else resolved <- normalizePath(expanded, mustWork = TRUE)
  luna_need(!luna_within(resolved, normalizePath(package_root, mustWork = TRUE)),
            "Keep text-containing inputs and results outside the reviewer package")
  parent <- if (new) dirname(resolved) else if (dir.exists(resolved)) resolved else dirname(resolved)
  repeat {
    luna_need(!file.exists(file.path(parent, ".git")) && !dir.exists(file.path(parent, ".git")),
              "Keep inputs and results outside every Git checkout")
    next_parent <- dirname(parent)
    if (identical(next_parent, parent)) break
    parent <- next_parent
  }
  resolved
}
luna_args <- function(args) {
  flags <- c("authorize-paid", "acknowledge-full-study-cost", "help")
  values <- c("inputs", "chunk", "output", "resume", "max-paid-pairs")
  out <- list(); i <- 1L
  while (i <= length(args)) {
    key <- sub("^--", "", args[[i]])
    luna_need(startsWith(args[[i]], "--") && key %in% c(flags, values) && is.null(out[[key]]),
              "Unknown or duplicate command option; use --help")
    if (key %in% flags) out[[key]] <- TRUE else {
      i <- i + 1L
      luna_need(i <= length(args) && !startsWith(args[[i]], "--"), "Missing option value")
      out[[key]] <- args[[i]]
    }
    i <- i + 1L
  }
  out
}
luna_authorize <- function(options, n) {
  luna_need(isTRUE(options[["authorize-paid"]]), "Provider access requires --authorize-paid")
  cap <- options[["max-paid-pairs"]]
  luna_need(is.character(cap) && length(cap) == 1L && grepl("^[1-9][0-9]*$", cap),
            "Set an explicit positive --max-paid-pairs cap")
  cap <- as.numeric(cap)
  luna_need(is.finite(cap) && cap <= 710184 && n <= cap, "Selected pairs exceed the explicit paid cap")
  luna_need(cap <= 1000 || isTRUE(options[["acknowledge-full-study-cost"]]),
            "Caps above 1000 require --acknowledge-full-study-cost")
  invisible(cap)
}
luna_body_args <- function(trait, guidance, template) list(
  model = "gpt-5.6-luna", trait_name = trait, trait_description = guidance,
  prompt_template = template, endpoint = "responses", reasoning = "none",
  store = FALSE, max_output_tokens = 128L, prompt_caching = "implicit",
  temperature = NULL, top_p = NULL
)
luna_check_bodies <- function(built, rows) {
  luna_need(nrow(built) == length(rows) && !anyDuplicated(built$custom_id), "Request identity mismatch")
  for (i in seq_along(rows)) {
    row <- rows[[i]]; body <- built$body[[i]]
    luna_need(identical(built$custom_id[[i]], row$request_id) &&
      identical(built$method[[i]], "POST") && identical(built$url[[i]], "/v1/responses"),
      "Request ID or endpoint differs")
    luna_need(setequal(names(body), c("model", "input", "reasoning", "store", "max_output_tokens")) &&
      identical(body$model, LUNA_MODEL) && identical(body$input, row$input) &&
      identical(body$reasoning, list(effort = "none")) && identical(body$store, FALSE) &&
      identical(as.integer(body$max_output_tokens), 128L) &&
      identical(luna_text_sha(body$input), row$prompt_sha256), "Prompt or historical W007 body mismatch")
  }
  invisible(TRUE)
}
luna_assets <- function(assets, manifest) {
  path <- file.path(assets, "luna_prompt_contract.json")
  luna_need(identical(luna_sha(path), LUNA_CONTRACT_SHA), "Frozen prompt contract SHA256 mismatch")
  contract <- jsonlite::read_json(path)
  specs <- c(list(contract$template), contract$traits)
  luna_need(length(specs) == 7L && length(manifest$resources) == 8L, "Expected template and all six traits")
  for (spec in specs) {
    luna_need(identical(luna_sha(file.path(assets, spec$file)), spec$sha256) &&
      identical(manifest$resources[[spec$file]], spec$sha256), "Frozen scientific prompt asset mismatch")
  }
  luna_need(identical(manifest$resources[["luna_prompt_contract.json"]], LUNA_CONTRACT_SHA),
    "Input manifest used a different prompt contract")
  invisible(contract)
}
luna_load <- function(input_root, chunk, assets) {
  luna_need(basename(chunk) == chunk && grepl("^cell_[0-9]{3}_chunk_[0-9]{4}\\.jsonl$", chunk),
            "Select one named cell/trait chunk from the input manifest")
  manifest_path <- file.path(input_root, "manifest.json")
  manifest <- jsonlite::read_json(manifest_path, simplifyVector = FALSE)
  luna_assets(assets, manifest)
  entries <- Filter(function(x) identical(x$file, chunk), manifest$chunks)
  luna_need(length(entries) == 1L, "Chunk absent or duplicated in input manifest")
  path <- file.path(input_root, chunk)
  luna_need(file.exists(path) && identical(luna_sha(path), entries[[1]]$sha256), "Input chunk SHA256 mismatch")
  rows <- lapply(readLines(path, warn = FALSE, encoding = "UTF-8"), jsonlite::fromJSON, simplifyVector = FALSE)
  luna_need(length(rows) > 0L && length(rows) <= 20000L && length(rows) == entries[[1]]$n_requests,
            "Invalid input chunk count (maximum 20000)")
  fields <- c("request_id", "pair_id", "role", "partition", "cell_id", "trait", "prompt_id",
              "ID1", "text1", "ID2", "text2", "input", "prompt_sha256")
  for (r in rows) {
    luna_need(all(fields %in% names(r)) && all(vapply(r[setdiff(fields, "cell_id")],
      function(x) is.character(x) && length(x) == 1L && !is.na(x) && nzchar(x), logical(1))),
      "Invalid request record")
    luna_need(r$role %in% c("base", "reversal") && r$ID1 != r$ID2 &&
      identical(luna_text_sha(r$input), r$prompt_sha256), "Invalid pair orientation or prompt hash")
  }
  ids <- vapply(rows, `[[`, "", "request_id")
  traits <- unique(vapply(rows, `[[`, "", "trait"))
  cells <- unique(vapply(rows, function(x) as.integer(x$cell_id), 1L))
  luna_need(!anyDuplicated(ids) && length(traits) == 1L && length(cells) == 1L &&
    identical(traits, entries[[1]]$trait) && identical(cells, as.integer(entries[[1]]$cell_id)),
    "Do not mix cells/traits or duplicate request IDs in one call")
  luna_need(traits %in% c("Cohesion", "Syntax", "Vocabulary", "Phraseology", "Grammar", "Conventions"),
            "Unknown trait")
  template <- luna_text(file.path(assets, "luna_prompt_template.txt"))
  guidance <- luna_text(file.path(assets, "luna_traits", paste0(tolower(traits), ".txt")))
  # Frozen assets and every full rendered input are authenticated independently.
  pairs <- data.frame(ID1 = vapply(rows, `[[`, "", "ID1"), text1 = vapply(rows, `[[`, "", "text1"),
    ID2 = vapply(rows, `[[`, "", "ID2"), text2 = vapply(rows, `[[`, "", "text2"),
    pair_uid = ids, stringsAsFactors = FALSE)
  list(rows = rows, pairs = pairs, args = luna_body_args(traits, guidance, template),
       manifest_sha256 = luna_sha(manifest_path), chunk_sha256 = luna_sha(path), chunk = chunk)
}
luna_build <- function(data) {
  built <- do.call(pairwiseLLM::build_openai_batch_requests, c(list(pairs = data$pairs), data$args))
  luna_check_bodies(built, data$rows)
  built
}
luna_strict_reply <- function(value) {
  allowed <- c("<BETTER_SAMPLE>SAMPLE_1</BETTER_SAMPLE>", "<BETTER_SAMPLE>SAMPLE_2</BETTER_SAMPLE>")
  luna_need(is.character(value) && length(value) == 1L && !is.na(value) && value %in% allowed,
            "Invalid visible reply: expected exactly one permitted XML decision")
  if (identical(value, allowed[[1]])) 1L else 2L
}
luna_visible <- function(body) {
  luna_need(identical(body$status, "completed") && is.null(body$error) && is.null(body$incomplete_details),
            "Incomplete or failed model response")
  text <- character()
  for (output in body$output) {
    luna_need(identical(output$type, "message") && identical(output$role, "assistant") &&
      (is.null(output$status) || identical(output$status, "completed")), "Ambiguous response output")
    for (content in output$content) {
      luna_need(identical(content$type, "output_text") && is.character(content$text), "Non-text/refusal output")
      text <- c(text, content$text)
    }
  }
  luna_need(length(text) == 1L, "Ambiguous or missing visible decision")
  text[[1]]
}
luna_outcomes <- function(path, rows) {
  ids <- vapply(rows, `[[`, "", "request_id")
  result <- lapply(rows, function(r) list(request_id = r$request_id, pair_id = r$pair_id,
    role = r$role, partition = r$partition, cell_id = r$cell_id, trait = r$trait, prompt_id = r$prompt_id,
    prompt_sha256 = r$prompt_sha256, ID1 = r$ID1, ID2 = r$ID2,
    judgment_origin = "new judgments", status = "missing", new_winner_position = NULL, new_winner_item_id = NULL))
  if (!file.exists(path)) return(result)
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8"); seen <- character()
  for (line in lines) {
    x <- jsonlite::fromJSON(line, simplifyVector = FALSE)
    luna_need(is.character(x$custom_id) && length(x$custom_id) == 1L && x$custom_id %in% ids &&
      !x$custom_id %in% seen, "Unexpected or duplicate provider custom ID")
    seen <- c(seen, x$custom_id); i <- match(x$custom_id, ids)
    parsed <- tryCatch({
      luna_need(is.null(x$error) && identical(as.integer(x$response$status_code), 200L), "Failed provider request")
      luna_strict_reply(luna_visible(x$response$body))
    }, error = function(e) e)
    if (inherits(parsed, "error")) {
      result[[i]]$status <- "rejected"
      result[[i]]$reason <- conditionMessage(parsed)
    } else {
      result[[i]]$status <- "accepted"
      result[[i]]$new_winner_position <- parsed
      result[[i]]$response_model <- x$response$body$model
      result[[i]]$new_winner_item_id <- if (parsed == 1L) rows[[i]]$ID1 else rows[[i]]$ID2
    }
  }
  result
}
luna_provenance <- function(mode, n) list(judgment_origin = "new judgments", mode = mode,
  requested_model = LUNA_MODEL, pairwiseLLM_version = "1.6.0", pairwiseLLM_sha = LUNA_PACKAGE_SHA,
  R_version = as.character(getRversion()), requests = n,
  historical_custom_ids_recreated = FALSE, archived_decisions_replaced = FALSE,
  historical_body = list(endpoint = "/v1/responses", reasoning = list(effort = "none"), store = FALSE,
    max_output_tokens = 128L, temperature = "omitted", top_p = "omitted", prompt_caching = "implicit"),
  note = "New responses are not expected to match archived decisions exactly. Model access may end.")
luna_capture <- function(expression, output) {
  tryCatch(withCallingHandlers(expression, message = function(m) invokeRestart("muffleMessage"),
    warning = function(w) invokeRestart("muffleWarning")), error = function(e) {
      luna_json(list(status = "interrupted_or_failed", detail = conditionMessage(e),
        action = "Retain this directory. Resume known batch IDs only; never automatically resubmit an uncertain submission."),
        file.path(output, "failure.json"))
      stop("Operation failed; inspect the external failure record. No automatic resubmission is permitted.", call. = FALSE)
    })
}
luna_receipt <- function(output, registry) {
  fields <- c("batch_input_path", "pairs_path")
  files <- c("provenance.json", "requests.jsonl", basename(unlist(registry[1, fields])))
  luna_need(all(file.exists(file.path(output, files))), "Missing immutable submission artifact")
  luna_json(list(batch_id = registry$batch_id[[1]], model = registry$model[[1]],
    provider = registry$provider[[1]], files = stats::setNames(as.list(vapply(file.path(output, files), luna_sha, "")), files)),
    file.path(output, "state-receipt.json"))
}
luna_verify_receipt <- function(previous, registry) {
  receipt <- jsonlite::read_json(file.path(previous, "state-receipt.json"))
  luna_need(identical(receipt$batch_id, registry$batch_id[[1]]) && identical(receipt$model, LUNA_MODEL) &&
    identical(receipt$provider, "openai"), "Saved batch identity differs from immutable receipt")
  for (name in names(receipt$files)) {
    luna_need(basename(name) == name && identical(luna_sha(file.path(previous, name)), receipt$files[[name]]),
      "Saved requests/pairs/provenance differ from immutable receipt")
  }
  for (field in c("batch_input_path", "pairs_path")) {
    name <- basename(registry[[field]][[1]])
    luna_need(!is.null(receipt$files[[name]]), "Registry pair/input paths differ from receipt")
  }
  invisible(receipt)
}
luna_submit <- function(data, built, output, submit = pairwiseLLM::llm_submit_pairs_multi_batch) {
  # A single local chunk is one remotely submitted batch. Submission retries are
  # disabled to avoid creating another batch after an ambiguous create response.
  luna_json(list(status = "submission_intent", requests = nrow(data$pairs)), file.path(output, "submission-intent.json"))
  jobs <- luna_capture(do.call(submit, c(list(pairs = data$pairs, backend = "openai",
    batch_size = nrow(data$pairs), output_dir = output, write_registry = TRUE,
    keep_jsonl = TRUE, verbose = FALSE, openai_max_retries = 1L), data$args)), output)
  saveRDS(jobs, file.path(output, "submission.rds"))
  luna_need(length(jobs$jobs) == 1L && file.exists(file.path(output, "jobs_registry.csv")),
            "Submission did not save a resumable registry; retain evidence and inspect provider account")
  luna_receipt(output, jobs$registry)
  invisible(jobs)
}
luna_resume <- function(previous, output, options, resume = pairwiseLLM::llm_resume_multi_batches) {
  provenance <- jsonlite::read_json(file.path(previous, "provenance.json"))
  luna_need(identical(provenance$pairwiseLLM_sha, LUNA_PACKAGE_SHA) &&
    identical(provenance$requested_model, LUNA_MODEL) && provenance$mode %in% c("submit", "resume"),
    "Resume source must be a saved run at the exact model and package baseline")
  registry <- read.csv(file.path(previous, "jobs_registry.csv"), stringsAsFactors = FALSE)
  luna_need(nrow(registry) == 1L && identical(registry$provider, "openai") &&
    identical(registry$model, LUNA_MODEL) && nzchar(registry$batch_id), "Invalid saved batch registry")
  luna_verify_receipt(previous, registry)
  rows <- lapply(readLines(file.path(previous, "requests.jsonl"), warn = FALSE, encoding = "UTF-8"),
                 jsonlite::fromJSON, simplifyVector = FALSE)
  luna_authorize(options, length(rows))
  new_provenance <- luna_provenance("resume", length(rows))
  new_provenance$previous_state_receipt_sha256 <- luna_sha(file.path(previous, "state-receipt.json"))
  new_provenance$input_manifest_sha256 <- provenance$input_manifest_sha256
  luna_json(new_provenance, file.path(output, "provenance.json"))
  luna_jsonl(rows, file.path(output, "requests.jsonl"))
  job <- as.list(registry[1, ])
  # Copy artifacts to the new attempt; package writes can never replace earlier
  # inputs, registries, partial downloads or decisions.
  for (field in c("batch_input_path", "batch_output_path", "csv_path", "pairs_path")) {
    old <- normalizePath(job[[field]], mustWork = FALSE)
    luna_need(luna_within(old, previous), "Registry path leaves its saved run directory")
    target <- file.path(output, basename(old))
    if (file.exists(old)) luna_need(file.copy(old, target, overwrite = FALSE), "Could not preserve prior artifact")
    job[[field]] <- target
  }
  luna_need(file.exists(job$pairs_path), "Missing saved pair data")
  job$segment_index <- as.integer(job$segment_index); job$done <- isTRUE(job$done)
  job$results <- NULL
  # Keep a registry before polling so interruption retains a resumable state.
  saved <- registry
  for (field in c("batch_input_path", "batch_output_path", "csv_path", "pairs_path")) saved[[field]] <- job[[field]]
  write.csv(saved, file.path(output, "jobs_registry.csv"), row.names = FALSE)
  luna_receipt(output, saved)
  if (!job$done) {
    result <- luna_capture(resume(jobs = list(job), output_dir = output,
      interval_seconds = 60, per_job_delay = 2, write_results_csv = FALSE,
      keep_jsonl = TRUE, write_registry = TRUE, verbose = FALSE,
      write_combined_csv = FALSE, openai_max_retries = 3L), output)
    saveRDS(result, file.path(output, "retrieval.rds"))
  }
  outcomes <- luna_outcomes(job$batch_output_path, rows)
  luna_jsonl(outcomes, file.path(output, "new-judgments.jsonl"))
  luna_need(!any(vapply(outcomes, function(x) x$status == "rejected", logical(1))),
            "Rejected provider replies retained locally; no invalid reply is a new judgment")
  invisible(outcomes)
}
luna_main <- function(args = commandArgs(trailingOnly = TRUE), script = NULL) {
  options <- luna_args(args)
  if (isTRUE(options$help)) {
    cat("Offline: --inputs EXTERNAL --chunk cell_001_chunk_0001.jsonl --output NEW_EXTERNAL\n",
        "Paid submit: add --authorize-paid --max-paid-pairs N (own provider access and budget).\n",
        "Resume: --resume PRIOR_RUN --output NEW_EXTERNAL --authorize-paid --max-paid-pairs N\n",
        "Caps above 1000 also require --acknowledge-full-study-cost. Resume only retrieves; it never resubmits.\n",
        "Install pairwiseLLM 1.6.0 at Git SHA ", LUNA_PACKAGE_SHA, ".\n",
        "New responses are not expected to match archived decisions exactly; model access may end.\n", sep = "")
    return(invisible(NULL))
  }
  if (is.null(script)) script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[[1]])
  assets <- dirname(normalizePath(script, mustWork = TRUE)); package_root <- dirname(assets)
  luna_package()
  luna_need(!is.null(options$output), "Specify a NEW external --output directory")
  output <- luna_external(options$output, package_root, new = TRUE)
  if (!is.null(options$resume)) {
    luna_need(is.null(options$inputs) && is.null(options$chunk), "Resume uses the saved registry, not new inputs")
    previous <- luna_external(options$resume, package_root)
    luna_authorize(options, 1L)
    dir.create(output, mode = "0700")
    luna_resume(previous, output, options)
  } else {
    luna_need(!is.null(options$inputs) && !is.null(options$chunk), "Specify --inputs and --chunk")
    input <- luna_external(options$inputs, package_root)
    data <- luna_load(input, options$chunk, assets)
    built <- luna_build(data)
    paid <- isTRUE(options[["authorize-paid"]])
    if (paid) luna_authorize(options, length(data$rows)) else
      luna_need(is.null(options[["max-paid-pairs"]]) && !isTRUE(options[["acknowledge-full-study-cost"]]),
                "Paid controls require --authorize-paid")
    dir.create(output, mode = "0700")
    provenance <- luna_provenance(if (paid) "submit" else "offline", length(data$rows))
    provenance$input_manifest_sha256 <- data$manifest_sha256
    provenance$chunk <- data$chunk; provenance$chunk_sha256 <- data$chunk_sha256
    luna_json(provenance, file.path(output, "provenance.json"))
    luna_jsonl(data$rows, file.path(output, "requests.jsonl"))
    serial <- lapply(seq_len(nrow(built)), function(i) list(custom_id = built$custom_id[[i]],
      method = built$method[[i]], url = built$url[[i]], body = built$body[[i]]))
    luna_jsonl(serial, file.path(output, "validated-batch-requests.jsonl"))
    if (paid) luna_submit(data, built, output)
  }
  cat("PASS: local request validation/run evidence saved externally.\n")
  invisible(output)
}
if (sys.nframe() == 0L) {
  tryCatch(luna_main(), error = function(e) {
    # Never echo input lines, model replies or provider error payloads.
    message("Stopped: request validation or operation failed. Inspect external run evidence; use --help for requirements.")
    quit(status = 1L)
  })
}
