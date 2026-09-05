"""Retrieval/search layer for the ChatLens ML pipeline (Phase 7).

Sits ON TOP of the completed pipeline (ingestion, OCR, CLIP, text embeddings,
ChromaDB indexing). Reuses existing components through their public interfaces:

  - CLIPImageEmbedder      (ml/embeddings/clip_embedder.py) for visual queries
  - TextEmbedder           (ml/embeddings/text_embedder.py) for text queries
  - ChromaStore            (ml/vectorstore/chroma_store.py) for the collections

Operations:
    - search_visual(image_path | text | embedding, account_id, top_k) -> visual similarity
    - search_text(query_text, account_id, top_k)                       -> semantic OCR/text
    - search_hybrid(query_text, account_id, top_k)                     -> fused visual + OCR
    - search(query, account_id, top_k, signal=...)                     -> unified dispatch

SCORE SEMANTICS
---------------
ChromaDB uses cosine space and returns a *distance* (lower = more similar). All
stored embeddings are unit-normalized, so cosine_distance = 1 - cosine_sim.
``RankedResult.score`` is a SIMILARITY in [0,1] (higher is better) via
``max(0, 1 - distance)``. ``raw_distance`` keeps the underlying distance.

HYBRID FUSION
-------------
Visual (CLIP, 512-d) and OCR/text (Sentence Transformer, 384-d) live in
DIFFERENT embedding spaces with different score distributions, so their raw
similarities are NOT directly comparable. Hybrid retrieval therefore:
  1. queries each channel independently,
  2. min-max normalizes similarity scores WITHIN each channel,
  3. joins candidates by image_id,
  4. fuses normalized scores with configurable weights,
  5. applies a relevance threshold so top_k is not padded with junk.

Read-only: never inserts/updates/deletes ChromaDB records or modifies images.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

# Retrieval signals (project Retrieval_Signal terminology).
SIGNAL_VISUAL = "visual"
SIGNAL_SEMANTIC_OCR = "semantic_ocr"
SIGNAL_VLM = "vlm_description"
SIGNAL_HYBRID = "hybrid"

# --- Hybrid fusion configuration (dataset-independent) ---
#
# Fusion uses Reciprocal Rank Fusion (RRF) over each channel's within-channel
# ranking, weighted by a per-query, evidence-derived modality weight. RRF is
# scale-free (it consumes ranks, not raw similarities), so it is robust to the
# fact that CLIP and Sentence-Transformer similarities live on different,
# non-comparable scales, and to a single anomalous absolute score. No query
# keywords, categories, or fixed modality weights are used.
#
# RRF_K is the standard rank-fusion damping constant. Larger K flattens the
# advantage of top ranks; 60 is the widely used default and is dataset-agnostic.
RRF_K = 60

# Lower bound on either channel's fused weight, so neither modality can be
# almost entirely silenced by a single extreme outlier in the other. The
# adaptive weight still tilts within [floor, 1-floor]. Dataset-independent.
MODALITY_WEIGHT_FLOOR = 0.35

# Conservative additive weight for the VLM description channel (Phase 3C).
# VLM description similarity is fused as an ADDITIONAL positive-evidence term
# ON TOP of the existing visual+OCR fusion, never replacing it. It is kept
# below MODALITY_WEIGHT_FLOOR (0.35) so it can enrich ranking / surface a
# VLM-only match, but cannot dominate the established CLIP/OCR behavior.
# Tune here (single knob). 0.25 chosen as a modest starting weight.
VLM_WEIGHT = 0.25

# Candidate pool per channel before fusion. A generous pool ensures a candidate
# that ranks well in one channel is still considered even if it is weak/absent
# in the other. Scales with top_k and has a floor; not dataset-specific.
CANDIDATE_MULTIPLIER = 5
MIN_CANDIDATE_POOL = 30

# "Strong" is defined RELATIVE to each channel's own score distribution for THIS
# query (a z-score style standout), never as a fixed absolute similarity. Used
# only for generating evidence-grounded explanations, not for ranking.
STRONG_STDDEV_ABOVE_MEAN = 1.0

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class RankedResult:
    """One retrieval result, traceable to the original image via image_id."""

    image_id: str
    file_path: str
    filename: Optional[str]
    category: Optional[str]
    score: float                 # final/fused similarity in [0,1], higher better
    retrieval_signal: str        # visual | semantic_ocr | hybrid
    raw_distance: float          # channel distance (single-channel modes)
    # Filesystem provenance (from stored metadata; falls back to file_path for
    # records indexed before provenance metadata existed).
    absolute_path: Optional[str] = None
    source_root: Optional[str] = None
    extracted_text: Optional[str] = None
    # Per-channel raw similarities in [0,1] (None when that channel did not
    # return this image -> "no evidence", not "evidence against").
    visual_score: Optional[float] = None
    text_score: Optional[float] = None
    # VLM description channel raw similarity in [0,1] (None when absent).
    vlm_score: Optional[float] = None
    # Per-channel within-channel rank (1 = best in that channel; None if absent).
    visual_rank: Optional[int] = None
    text_rank: Optional[int] = None
    vlm_rank: Optional[int] = None
    # Per-channel standardized (z-score) strength within this query's channel
    # distribution; comparable across channels. None if channel absent.
    visual_z: Optional[float] = None
    text_z: Optional[float] = None
    # Which modalities provided evidence: "visual" | "ocr" | "both" | "none".
    modality: Optional[str] = None
    reason: Optional[str] = None  # deterministic, signal-grounded explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "file_path": self.file_path,
            "filename": self.filename,
            "category": self.category,
            "score": self.score,
            "retrieval_signal": self.retrieval_signal,
            "raw_distance": self.raw_distance,
            "absolute_path": self.absolute_path,
            "source_root": self.source_root,
            "extracted_text": self.extracted_text,
            "visual_score": self.visual_score,
            "text_score": self.text_score,
            "vlm_score": self.vlm_score,
            "visual_rank": self.visual_rank,
            "text_rank": self.text_rank,
            "vlm_rank": self.vlm_rank,
            "visual_z": self.visual_z,
            "text_z": self.text_z,
            "modality": self.modality,
            "reason": self.reason,
        }


def _similarity_from_distance(distance: float) -> float:
    """Convert cosine distance (lower better) to similarity in [0,1] (higher better)."""
    sim = 1.0 - float(distance)
    if sim < 0.0:
        sim = 0.0
    if sim > 1.0:
        sim = 1.0
    return round(sim, 6)


def _min_max_normalize(values: Dict[str, float]) -> Dict[str, float]:
    """Min-max normalize a map of image_id -> score into [0,1].

    If all values are equal (or a single value), returns 1.0 for each present
    entry (they are equally and maximally relevant within this channel).
    """
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if hi - lo < 1e-12:
        return {k: 1.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def _zscores(values: Dict[str, float]) -> Dict[str, float]:
    """Standardize a channel's scores: z = (x - mean) / stddev.

    Z-scores express each candidate's strength RELATIVE to that channel's own
    distribution for this query, making the two incomparable channels comparable
    without assuming any fixed score range. If the channel has <2 items or ~zero
    variance, returns 0.0 for each (no discriminative information).
    """
    if not values:
        return {}
    xs = list(values.values())
    n = len(xs)
    mean = sum(xs) / n
    if n < 2:
        return {k: 0.0 for k in values}
    var = sum((x - mean) ** 2 for x in xs) / n
    std = var ** 0.5
    if std < 1e-12:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / std for k, v in values.items()}


def _channel_discriminativeness(zscores: Dict[str, float]) -> float:
    """How decisively a channel separates its best candidate(s) from the pack.

    Derived purely from the channel's own score distribution for this query:
    the top z-score (how many standard deviations the best candidate stands
    above the channel mean). A channel whose top item sharply stands out is
    providing reliable evidence and should influence ranking more; a flat,
    indecisive channel should influence it less. Returns >= 0.0.

    This is the adaptive, evidence-derived modality signal that replaces fixed
    weights. It uses no query text, keywords, or dataset categories.
    """
    if not zscores:
        return 0.0
    top_z = max(zscores.values())
    return max(0.0, top_z)


class Retriever:
    """Similarity search over the existing ChromaDB collections."""

    def __init__(self, store: Optional[Any] = None) -> None:
        # Reuse the existing ChromaStore abstraction (canonical DB path).
        if store is None:
            from ml.vectorstore.chroma_store import ChromaStore
            store = ChromaStore()
        self.store = store
        self._clip = None   # lazy, reused
        self._text = None   # lazy, reused

    # -- lazy, reused embedders (existing implementations) --------------------

    def _clip_embedder(self):
        if self._clip is None:
            from ml.embeddings.clip_embedder import CLIPImageEmbedder
            self._clip = CLIPImageEmbedder()
        return self._clip

    def _text_embedder(self):
        if self._text is None:
            from ml.embeddings.text_embedder import TextEmbedder
            self._text = TextEmbedder()
        return self._text

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _valid_top_k(top_k: int) -> int:
        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be an integer >= 1")
        return top_k

    def _query_collection(
        self, collection, query_embedding: Sequence[float], account_id: str,
        top_k: int, signal: str,
    ) -> List[RankedResult]:
        count = collection.count()
        if count == 0:
            return []  # empty collection -> no results (no fabrication)
        n = min(top_k, count)
        res = collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=n,
            include=["metadatas", "distances"],
            where={"account_id": account_id},
        )
        ids = (res.get("ids") or [[]])[0]
        metadatas = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        results: List[RankedResult] = []
        for md, dist in zip(metadatas, distances):
            md = md or {}
            sim = _similarity_from_distance(dist)
            fpath = md.get("file_path", "")
            results.append(
                RankedResult(
                    image_id=md.get("image_id", ""),
                    file_path=fpath,
                    filename=md.get("filename"),
                    category=md.get("category"),
                    score=sim,
                    retrieval_signal=signal,
                    raw_distance=round(float(dist), 6),
                    absolute_path=md.get("absolute_path") or fpath,
                    source_root=md.get("source_root"),
                    extracted_text=md.get("extracted_text"),
                    visual_score=sim if signal == SIGNAL_VISUAL else None,
                    text_score=sim if signal == SIGNAL_SEMANTIC_OCR else None,
                    vlm_score=sim if signal == SIGNAL_VLM else None,
                    reason=self._single_channel_reason(signal),
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    @staticmethod
    def _single_channel_reason(signal: str) -> str:
        if signal == SIGNAL_VISUAL:
            return "Visual (CLIP) match"
        if signal == SIGNAL_SEMANTIC_OCR:
            return "OCR semantic (text) match"
        if signal == SIGNAL_VLM:
            return "VLM description semantic match"
        return "match"

    def _embed_visual_query(self, query: Union[str, Path, Sequence[float]]) -> List[float]:
        """Produce a 512-d CLIP query embedding from an image path, text, or vector."""
        if isinstance(query, (str, Path)):
            path = Path(query)
            if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES:
                rec = self._clip_embedder().embed_one(
                    image_id="__query__", file_path=str(path), category="__query__"
                )
                if not rec.ok or rec.visual_embedding is None:
                    raise ValueError(f"failed to embed query image: {rec.error}")
                return rec.visual_embedding
            # Natural-language query -> CLIP text embedding (same 512-d space).
            return self._clip_embedder().embed_text_query(str(query))
        embedding = list(query)
        if not embedding:
            raise ValueError("empty visual query embedding")
        return embedding

    # -- public retrieval operations ------------------------------------------

    def search_visual(
        self,
        query: Union[str, Path, Sequence[float]], account_id: str,
        top_k: int = 5,
    ) -> List[RankedResult]:
        """Visual similarity search against chatlens_visual_embeddings.

        ``query`` may be an image path (CLIP image embedding), a natural-language
        string (CLIP text embedding in the same 512-d space), or a precomputed
        CLIP embedding (sequence of floats).
        """
        top_k = self._valid_top_k(top_k)
        embedding = self._embed_visual_query(query)
        return self._query_collection(self.store.visual, embedding, account_id, top_k, SIGNAL_VISUAL)

    def search_text(self, query_text: str, account_id: str, top_k: int = 5) -> List[RankedResult]:
        """Semantic OCR/text search against chatlens_text_embeddings."""
        top_k = self._valid_top_k(top_k)
        if query_text is None or not str(query_text).strip():
            raise ValueError("query text must be a non-empty string")
        vec = self._text_embedder()._encode(str(query_text).strip())
        return self._query_collection(self.store.text, vec, account_id, top_k, SIGNAL_SEMANTIC_OCR)

    def search_vlm(self, query_text: str, account_id: str, top_k: int = 5) -> List[RankedResult]:
        """Semantic search against the VLM description collection
        (chatlens_vlm_description_embeddings).

        VLM descriptions are embedded with the SAME MiniLM text model as the
        OCR/text channel (384-d, cosine), so the query is encoded identically
        and compared in the same space. Account isolation is enforced by the
        ``where={"account_id": account_id}`` filter inside _query_collection,
        exactly like the visual/text channels - a VLM match for another
        account can never be returned. Returns [] for an empty/absent VLM
        collection (no fabrication).
        """
        top_k = self._valid_top_k(top_k)
        if query_text is None or not str(query_text).strip():
            raise ValueError("query text must be a non-empty string")
        vec = self._text_embedder()._encode(str(query_text).strip())
        return self._query_collection(self.store.vlm, vec, account_id, top_k, SIGNAL_VLM)

    def search_hybrid(
        self,
        query_text: str, account_id: str,
        top_k: int = 5,
    ) -> List[RankedResult]:
        """Modality-aware hybrid retrieval via adaptive-weight Reciprocal Rank Fusion.

        Pipeline (fully dataset/query independent):
          1. Query both channels independently for a generous candidate pool.
          2. Standardize each channel's similarities to z-scores (relative to
             that channel's own distribution for THIS query) so the two
             non-comparable spaces become comparable without fixed ranges.
          3. Derive a per-query modality weight for each channel from how
             DECISIVELY that channel separates its best candidate(s) from its
             own pack (top z-score). A channel that gives sharp evidence counts
             more; a flat/indecisive channel counts less. No keywords/categories.
          4. Fuse with weighted Reciprocal Rank Fusion (RRF) over the union of
             candidates, keyed by image_id (evidence merged, not duplicated).
             RRF consumes ranks, so it is immune to anomalous absolute scores and
             to cross-channel scale differences.
          5. A missing channel simply contributes nothing for that image
             (absence = "no evidence", never negative evidence), so a strong
             visual-only image is not penalized for lacking OCR.
        """
        top_k = self._valid_top_k(top_k)
        if query_text is None or not str(query_text).strip():
            raise ValueError("query text must be a non-empty string")
        query_text = str(query_text).strip()

        pool = max(top_k * CANDIDATE_MULTIPLIER, MIN_CANDIDATE_POOL)

        # 1. Independent candidate generation from each channel.
        visual_hits = self.search_visual(query_text, account_id=account_id, top_k=pool)   # all images
        text_hits = self.search_text(query_text, account_id=account_id, top_k=pool)       # text-bearing
        # VLM description channel (Phase 3C): an ADDITIONAL signal. Wrapped so
        # an empty/unavailable/failing VLM collection can NEVER break hybrid
        # search - on any error we simply proceed with visual+OCR as before.
        try:
            vlm_hits = self.search_vlm(query_text, account_id=account_id, top_k=pool)
        except Exception:  # noqa: BLE001 - VLM is optional; degrade gracefully
            vlm_hits = []

        # Per-channel raw similarity + within-channel rank (1-based).
        v_raw = {h.image_id: h.score for h in visual_hits if h.image_id}
        t_raw = {h.image_id: h.score for h in text_hits if h.image_id}
        m_raw = {h.image_id: h.score for h in vlm_hits if h.image_id}
        v_rank = {h.image_id: i + 1 for i, h in enumerate(visual_hits) if h.image_id}
        t_rank = {h.image_id: i + 1 for i, h in enumerate(text_hits) if h.image_id}
        m_rank = {h.image_id: i + 1 for i, h in enumerate(vlm_hits) if h.image_id}

        # 2. Standardize each channel (comparable strength, no fixed ranges).
        v_z = _zscores(v_raw)
        t_z = _zscores(t_raw)
        m_z = _zscores(m_raw)

        # 3. Adaptive, evidence-derived per-query modality weights.
        #    Each channel's influence grows with how decisively it separates its
        #    best candidate from its own pack (top z-score). Weights are then
        #    CLAMPED to a bounded band so a single extreme outlier in one channel
        #    (e.g. one document whose text coincidentally matches the query)
        #    cannot seize almost all influence and bury a strong standout from
        #    the other channel. The band keeps both channels materially involved
        #    while still tilting toward the more decisive one. Fully generic: no
        #    keywords, categories, or query inspection.
        v_disc = _channel_discriminativeness(v_z)
        t_disc = _channel_discriminativeness(t_z)
        total_disc = v_disc + t_disc
        if total_disc <= 1e-12:
            v_weight = t_weight = 0.5
        else:
            v_weight = v_disc / total_disc
            t_weight = t_disc / total_disc
            # Clamp to a bounded band [MODALITY_WEIGHT_FLOOR, 1-floor] and renorm.
            v_weight = min(max(v_weight, MODALITY_WEIGHT_FLOOR), 1.0 - MODALITY_WEIGHT_FLOOR)
            t_weight = 1.0 - v_weight

        # 4. Weighted Reciprocal Rank Fusion over the candidate union.
        meta: Dict[str, RankedResult] = {}
        for h in visual_hits:
            meta.setdefault(h.image_id, h)
        for h in text_hits:
            meta[h.image_id] = h  # text hit carries extracted_text metadata
        for h in vlm_hits:
            meta.setdefault(h.image_id, h)  # VLM-only images enter the union
        # Provenance (absolute_path / source_root) is stored on VISUAL records,
        # so source it from the visual hit when available.
        visual_meta: Dict[str, RankedResult] = {h.image_id: h for h in visual_hits}

        # A channel contributes its RRF term only when it provides genuine
        # POSITIVE evidence for this image: the image must be at/above that
        # channel's own mean (z >= 0) for this query. This treats a
        # below-average score as "no positive evidence" rather than as support,
        # so a candidate cannot climb merely by being mediocre in both channels,
        # and a channel-#1 standout is not dragged down by a weak second channel.
        # (Absence and below-average are both non-negative-only gated; neither is
        # negative evidence.) A candidate positive in no channel still keeps a
        # small floor term from its best rank so it remains ordered, not dropped.
        fused: List[RankedResult] = []
        for image_id in set(v_rank) | set(t_rank) | set(m_rank):
            vr = v_rank.get(image_id)
            tr = t_rank.get(image_id)
            mr = m_rank.get(image_id)
            vz_i = v_z.get(image_id)
            tz_i = t_z.get(image_id)
            mz_i = m_z.get(image_id)
            # Fused score = weighted sum of each channel's POSITIVE standardized
            # strength (z-score, clamped at 0). Using z-scores (not ranks) means
            # a candidate that is a strong standout in ONE channel is rewarded on
            # the merit of that evidence and is NOT structurally beaten by a
            # weaker candidate merely for appearing in both channels. A channel
            # below its own mean contributes 0 (no positive evidence), and an
            # absent channel contributes 0 (no evidence) - neither is negative.
            # A tiny rank term breaks ties deterministically without changing
            # the evidence-based ordering.
            v_pos_z = max(0.0, vz_i) if (vr is not None and vz_i is not None) else 0.0
            t_pos_z = max(0.0, tz_i) if (tr is not None and tz_i is not None) else 0.0
            # VLM description evidence: ADDITIVE, conservatively weighted, and
            # positive-only (below-mean or absent VLM contributes nothing). It
            # enriches ranking / can surface a VLM-only match without altering
            # the existing visual+OCR evidence (whose weights still sum to 1).
            m_pos_z = max(0.0, mz_i) if (mr is not None and mz_i is not None) else 0.0
            evidence = v_weight * v_pos_z + t_weight * t_pos_z + VLM_WEIGHT * m_pos_z
            best_rank = min([r for r in (vr, tr, mr) if r is not None])
            rank_tiebreak = 1.0 / (RRF_K + best_rank)  # << evidence scale
            fused_score = evidence + 1e-3 * rank_tiebreak

            src = meta.get(image_id)
            vz = v_z.get(image_id)
            tz = t_z.get(image_id)
            has_v = vr is not None
            has_t = tr is not None
            has_m = mr is not None
            # Existing visual/OCR modality labels are preserved exactly. Only
            # when NEITHER visual nor OCR provided evidence but VLM did do we
            # surface a distinct "vlm" modality (a VLM-only match).
            modality = ("both" if has_v and has_t
                        else "visual" if has_v
                        else "ocr" if has_t
                        else "vlm" if has_m
                        else "none")
            fused.append(
                RankedResult(
                    image_id=image_id,
                    file_path=src.file_path if src else "",
                    filename=src.filename if src else None,
                    category=src.category if src else None,
                    score=round(fused_score, 8),
                    retrieval_signal=SIGNAL_HYBRID,
                    raw_distance=src.raw_distance if src else 0.0,
                    absolute_path=((visual_meta.get(image_id).absolute_path
                                    if visual_meta.get(image_id) else None)
                                   or (src.absolute_path if src else None)
                                   or (src.file_path if src else None)),
                    source_root=((visual_meta.get(image_id).source_root
                                  if visual_meta.get(image_id) else None)
                                 or (src.source_root if src else None)),
                    extracted_text=src.extracted_text if src else None,
                    visual_score=round(v_raw[image_id], 6) if has_v else None,
                    text_score=round(t_raw[image_id], 6) if has_t else None,
                    vlm_score=round(m_raw[image_id], 6) if has_m else None,
                    visual_rank=vr,
                    text_rank=tr,
                    vlm_rank=mr,
                    visual_z=round(vz, 4) if vz is not None else None,
                    text_z=round(tz, 4) if tz is not None else None,
                    modality=modality,
                    reason=self._hybrid_reason(vz, tz, has_v, has_t),
                )
            )

        # Deterministic ordering: fused score desc, then visual z, then id.
        fused.sort(
            key=lambda r: (r.score, r.visual_z or -9.9, r.text_z or -9.9, r.image_id),
            reverse=True,
        )
        return fused[:top_k]

    @staticmethod
    def _hybrid_reason(
        vz: Optional[float], tz: Optional[float],
        has_v: bool, has_t: bool,
    ) -> str:
        """Evidence-grounded explanation from standardized per-channel strength.

        "Strong" means the candidate stands >= STRONG_STDDEV_ABOVE_MEAN standard
        deviations above its channel's mean for THIS query (relative, not a fixed
        absolute similarity). OCR is only mentioned when the OCR channel actually
        returned this image. No query-specific or dataset-specific logic.
        """
        thr = STRONG_STDDEV_ABOVE_MEAN
        v_strong = has_v and vz is not None and vz >= thr
        t_strong = has_t and tz is not None and tz >= thr

        if has_v and has_t:
            if v_strong and t_strong:
                return "Strong visual and OCR agreement"
            if t_strong and not v_strong:
                return "Strong OCR semantic match; visual support"
            if v_strong and not t_strong:
                return "Strong visual semantic match; OCR support"
            return "Visual and OCR evidence"
        if has_t:
            return "Strong OCR semantic match" if t_strong else "OCR semantic match"
        if has_v:
            return ("Strong visual semantic match; no OCR evidence available"
                    if v_strong else "Visual match; no OCR evidence available")
        return "No modality evidence"
    def search(
        self,
        query: Union[str, Path, Sequence[float]], account_id: str,
        top_k: int = 5,
        signal: Optional[str] = None,
    ) -> List[RankedResult]:
        """Unified interface. Dispatches to visual, semantic_ocr, or hybrid.

        Dispatch rules:
          - signal == 'visual'       -> search_visual
          - signal == 'semantic_ocr' -> search_text
          - signal == 'hybrid'       -> search_hybrid
          - signal is None (default):
              * an existing image FILE path -> visual (query-by-image)
              * a precomputed embedding     -> visual
              * a natural-language string   -> HYBRID (the main behavior)
        """
        if signal == SIGNAL_VISUAL:
            return self.search_visual(query, account_id=account_id, top_k=top_k)
        if signal == SIGNAL_SEMANTIC_OCR:
            if not isinstance(query, (str, Path)):
                raise ValueError("semantic_ocr search requires a text query")
            return self.search_text(str(query), account_id=account_id, top_k=top_k)
        if signal == SIGNAL_HYBRID:
            if not isinstance(query, (str, Path)):
                raise ValueError("hybrid search requires a text query")
            return self.search_hybrid(str(query), account_id=account_id, top_k=top_k)

        # Inference (signal is None)
        if isinstance(query, (str, Path)):
            p = Path(query)
            if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES:
                return self.search_visual(p, account_id=account_id, top_k=top_k)   # query-by-image
            # Natural-language description -> hybrid is the default behavior.
            return self.search_hybrid(str(query), account_id=account_id, top_k=top_k)
        return self.search_visual(query, account_id=account_id, top_k=top_k)


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    parser = argparse.ArgumentParser(description="Query the ChatLens ChromaDB index (read-only).")
    parser.add_argument("query", help="natural-language query, or an image path for query-by-image")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--top_k", "--top-k", dest="top_k", type=int, default=5)
    parser.add_argument(
        "--signal",
        choices=[SIGNAL_VISUAL, SIGNAL_SEMANTIC_OCR, SIGNAL_HYBRID],
        default=None,
        help="visual | semantic_ocr | hybrid. Default: hybrid for text queries.",
    )
    parser.add_argument("--diagnostic", action="store_true",
                        help="print the ChromaDB path and collection counts")
    args = parser.parse_args()

    r = Retriever()
    if args.diagnostic:
        store = r.store
        store.open()
        stats = store.stats()
        print("ChromaDB:", store.db_path)
        for name, n in stats.items():
            print(f"  {name}: {n}")
        print("-" * 60)

    results = r.search(args.query, account_id=args.account_id, top_k=args.top_k, signal=args.signal)
    if not results:
        print("No results.")
    for i, res in enumerate(results, 1):
        v = f"{res.visual_score:.3f}" if res.visual_score is not None else "-"
        tx = f"{res.text_score:.3f}" if res.text_score is not None else "-"
        vr = res.visual_rank if res.visual_rank is not None else "-"
        tr = res.text_rank if res.text_rank is not None else "-"
        vz = f"{res.visual_z:+.2f}" if res.visual_z is not None else "-"
        tz = f"{res.text_z:+.2f}" if res.text_z is not None else "-"
        print(f"{i}. [{res.retrieval_signal}] final={res.score:.5f} "
              f"[{res.category}] {res.filename}")
        print(f"     visual: sim={v} rank={vr} z={vz} | "
              f"ocr: sim={tx} rank={tr} z={tz} | modality={res.modality}")
        if res.reason:
            print(f"     reason: {res.reason}")
