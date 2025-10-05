# clustering.py
"""
Semantic clustering of LLM answers using embeddings and HDBSCAN/KMeans.
Groups semantically equivalent answers to compute entropy.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import silhouette_score
import hdbscan
from sklearn.cluster import KMeans

from ..ambiguity_config import ClusteringConfig, DEFAULT_CONFIG


@dataclass
class ClusterResult:
    """Result of clustering operation.
    
    Attributes:
        labels: Cluster assignment for each answer (-1 for noise in HDBSCAN).
        num_clusters: Number of distinct clusters found.
        cluster_sizes: Count of items in each cluster.
        silhouette: Silhouette score (quality metric, -1 to 1).
        embeddings: The computed embeddings (for debugging).
        method: Clustering method used.
    """
    labels: np.ndarray
    num_clusters: int
    cluster_sizes: Dict[int, int]
    silhouette: Optional[float]
    embeddings: np.ndarray
    method: str


class SemanticClusterer:
    """Clusters text answers using semantic embeddings."""
    
    def __init__(
        self,
        config: Optional[ClusteringConfig] = None
    ):
        """Initialize the clusterer.
        
        Args:
            config: Configuration for clustering.
        """
        self.config = config or DEFAULT_CONFIG.clustering
        
        # Load embedding model (cached after first use)
        print(f"Loading embedding model: {self.config.embedding_model}...")
        self.encoder = SentenceTransformer(self.config.embedding_model)
        print("✓ Embedding model loaded")
    
    def _compute_embeddings(self, texts: List[str]) -> np.ndarray:
        """Compute sentence embeddings for texts.
        
        Args:
            texts: List of text strings.
            
        Returns:
            Numpy array of embeddings (shape: [num_texts, embedding_dim]).
        """
        embeddings = self.encoder.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return embeddings
    
    def _cluster_hdbscan(
        self,
        embeddings: np.ndarray,
        min_cluster_size: Optional[int] = None
    ) -> Tuple[np.ndarray, int]:
        """Cluster using HDBSCAN.
        
        Args:
            embeddings: Embedding vectors.
            min_cluster_size: Minimum cluster size override.
            
        Returns:
            Tuple of (cluster labels, num_clusters).
        """
        min_size = min_cluster_size or self.config.min_cluster_size
        
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_size,
            min_samples=self.config.min_samples,
            metric='euclidean',
            cluster_selection_method='eom'
        )
        
        labels = clusterer.fit_predict(embeddings)
        
        # Count clusters (excluding noise label -1)
        num_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        
        return labels, num_clusters
    
    def _cluster_kmeans(
        self,
        embeddings: np.ndarray,
        n_clusters: int
    ) -> Tuple[np.ndarray, int]:
        """Cluster using KMeans.
        
        Args:
            embeddings: Embedding vectors.
            n_clusters: Number of clusters to create.
            
        Returns:
            Tuple of (cluster labels, num_clusters).
        """
        kmeans = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10
        )
        
        labels = kmeans.fit_predict(embeddings)
        num_clusters = n_clusters
        
        return labels, num_clusters
    
    def _compute_silhouette(
        self,
        embeddings: np.ndarray,
        labels: np.ndarray
    ) -> Optional[float]:
        """Compute silhouette score for clustering quality.
        
        Args:
            embeddings: Embedding vectors.
            labels: Cluster assignments.
            
        Returns:
            Silhouette score (0 to 1) or None if not computable.
        """
        # Need at least 2 clusters and no noise-only clustering
        unique_labels = set(labels)
        if len(unique_labels) < 2:
            return None
        
        # Filter out noise points (-1) for silhouette calculation
        mask = labels != -1
        if mask.sum() < 2:
            return None
        
        try:
            score = silhouette_score(
                embeddings[mask],
                labels[mask],
                metric='euclidean'
            )
            return float(score)
        except:
            return None
    
    def cluster(
        self,
        texts: List[str],
        method: Optional[str] = None
    ) -> ClusterResult:
        """Cluster texts semantically.
        
        Args:
            texts: List of text strings to cluster.
            method: Override config method ('hdbscan' or 'kmeans').
            
        Returns:
            ClusterResult with labels and metadata.
        """
        if not texts:
            raise ValueError("No texts provided for clustering")
        
        if len(texts) == 1:
            # Single text - single cluster
            return ClusterResult(
                labels=np.array([0]),
                num_clusters=1,
                cluster_sizes={0: 1},
                silhouette=None,
                embeddings=self._compute_embeddings(texts),
                method="single_item"
            )
        
        # Compute embeddings
        embeddings = self._compute_embeddings(texts)
        
        # Select clustering method
        method = method or self.config.clustering_method
        
        if method == "hdbscan":
            labels, num_clusters = self._cluster_hdbscan(embeddings)
            
            # Fallback to KMeans if HDBSCAN gives poor results
            if num_clusters == 0 or num_clusters >= len(texts) - 1:
                print(f"⚠️  HDBSCAN gave poor results ({num_clusters} clusters), falling back to KMeans")
                # Heuristic: use sqrt(n) clusters
                n_clusters = max(2, int(np.sqrt(len(texts))))
                labels, num_clusters = self._cluster_kmeans(embeddings, n_clusters)
                method = "kmeans_fallback"
        
        elif method == "kmeans":
            # Auto-determine number of clusters (heuristic)
            n_clusters = max(2, min(len(texts) // 2, int(np.sqrt(len(texts)))))
            labels, num_clusters = self._cluster_kmeans(embeddings, n_clusters)
        
        else:
            raise ValueError(f"Unknown clustering method: {method}")
        
        # Compute cluster sizes
        cluster_sizes = {}
        for label in set(labels):
            cluster_sizes[int(label)] = int(np.sum(labels == label))
        
        # Compute silhouette score
        silhouette = self._compute_silhouette(embeddings, labels)
        
        return ClusterResult(
            labels=labels,
            num_clusters=num_clusters,
            cluster_sizes=cluster_sizes,
            silhouette=silhouette,
            embeddings=embeddings,
            method=method
        )


def format_clusters_for_storage(result: ClusterResult, texts: List[str]) -> Dict:
    """Convert cluster result to JSON-serializable dict.
    
    Args:
        result: ClusterResult object.
        texts: Original texts (for reference).
        
    Returns:
        Dict suitable for JSON storage.
    """
    # Group texts by cluster
    clusters_dict = {}
    for i, label in enumerate(result.labels):
        label_key = str(int(label))
        if label_key not in clusters_dict:
            clusters_dict[label_key] = []
        clusters_dict[label_key].append({
            "text": texts[i],
            "index": i
        })
    
    return {
        "num_clusters": result.num_clusters,
        "cluster_sizes": {str(k): v for k, v in result.cluster_sizes.items()},
        "silhouette_score": result.silhouette,
        "method": result.method,
        "clusters": clusters_dict
    }


def get_cluster_distribution(result: ClusterResult) -> np.ndarray:
    """Get probability distribution over clusters for entropy calculation.
    
    Args:
        result: ClusterResult object.
        
    Returns:
        Probability distribution (sums to 1.0).
    """
    # Exclude noise cluster (-1) if present
    sizes = [size for label, size in result.cluster_sizes.items() if label != -1]
    total = sum(sizes)
    
    if total == 0:
        return np.array([])
    
    distribution = np.array(sizes, dtype=float) / total
    return distribution
