# Exact original aggregation kernel; source SHA256 below.
# 285f970e88ffc95724a5c8585ddd8fcb8868a09edb8759bf72e21d32735c2b6b
fail <- function(...) stop(paste0(...), call. = FALSE)
need <- function(ok, ...) if (!isTRUE(ok)) fail(...)
ND <- 4000L; NC <- 96L; SEED <- 20261028L
synthesize <- function(fits) {
  need(length(fits)==NC,"exactly 96 fits required")
  previous <- RNGkind()
  on.exit(do.call(RNGkind,as.list(previous)),add=TRUE)
  RNGkind("Mersenne-Twister","Inversion","Rejection")
  set.seed(SEED)
  # Independent fit indices, but paired epsilon and beta within each fit.
  shuffled <- lapply(fits,function(z) z[sample.int(ND,ND,replace=TRUE),,drop=FALSE])
  metrics <- c("epsilon","beta","first_probability")
  overall <- do.call(rbind,lapply(metrics,function(key) {
    mat <- do.call(cbind,lapply(shuffled,function(z) z[[key]]))
    need(is.matrix(mat) && all(dim(mat)==c(ND,NC)) && all(is.finite(mat)),
         "posterior grid invalid")
    median_draw <- apply(mat,1L,median)
    p <- quantile(median_draw,c(.025,.975),names=FALSE)
    cm <- vapply(fits,function(z) mean(z[[key]]),numeric(1L))
    iq <- quantile(cm,c(.25,.75),names=FALSE)
    data.frame(parameter=key,estimate=median(median_draw),
               cri_lower=p[[1L]],cri_upper=p[[2L]],
               median_cell_posterior_mean=median(cm),
               cell_iqr_lower=iq[[1L]],cell_iqr_upper=iq[[2L]],
               n_cells=NC,n_prompts=16L,draws_per_cell=ND)
  }))
  cell <- do.call(rbind,lapply(seq_along(fits),function(i)
    do.call(rbind,lapply(metrics,function(key) {
      v <- fits[[i]][[key]]
      p <- quantile(v,c(.025,.975),names=FALSE)
      data.frame(cell_position=i,parameter=key,posterior_mean=mean(v),
                 posterior_median=median(v),cri_lower=p[[1]],cri_upper=p[[2]])
    }))))
  rownames(overall) <- rownames(cell) <- NULL
  list(overall=overall,cell=cell)
}
