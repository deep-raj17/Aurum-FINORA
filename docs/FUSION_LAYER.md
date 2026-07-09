# Cross-attention fusion layer

`CrossAttentionFusion` combines eight feature families:

- market OHLCV;
- technical indicators;
- macro features;
- sentiment embeddings;
- filing/news embeddings;
- graph embeddings;
- risk features;
- regime features.

Each family has its own projection into the shared hidden dimension. Time/token inputs
are pooled by the current compact implementation, receive a learned modality identity,
and are attended by a learned financial-decision query. The returned modality
attention is diagnostic evidence, not a causal explanation.

An availability mask excludes missing modalities from attention. A row with no usable
modality fails closed. Do not replace missing modalities with fabricated predictions;
normal imputation may occur only under a versioned feature-store policy and must still
be represented in quality/availability features.

Specialist embeddings are combined after fusion using router weights. The fused
modality representation and expert mixture then feed a normalized decision embedding
shared by every prediction head. This keeps heads internally consistent while allowing
head-specific calibration and approval thresholds.

For training and audit, persist modality schemas, normalization versions, availability
masks, attention diagnostics, feature timestamps, and cutoff checks. Attention values
must not be presented to users as feature attribution without separate validation.
