#!/usr/bin/env python3
"""
Test the semantic clustering module.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gum.ambiguity.clustering import SemanticClusterer, format_clusters_for_storage, get_cluster_distribution


def test_clustering():
    """Test clustering on sample answers."""
    print("="*80)
    print("SEMANTIC CLUSTERING TEST")
    print("="*80)
    
    # Sample answers (representing semantic groups)
    test_answers = [
        # Group 1: "Yes, accurate" responses
        "Yes, this interpretation accurately represents the user's Python usage based on the evidence.",
        "Yes, the evidence supports this interpretation of Python development work.",
        "This is correct based on the terminal session data.",
        
        # Group 2: "Partially accurate" responses
        "Partially. The evidence shows Python usage but doesn't fully confirm this specific interpretation.",
        "This interpretation is partially supported, though not all details are confirmed.",
        "Somewhat accurate, but lacks complete evidence for the specific claim.",
        
        # Group 3: "Not enough evidence" responses
        "The evidence is insufficient to confirm this interpretation.",
        "We cannot verify this based on the available data.",
        "There isn't enough information to support this interpretation.",
        
        # Group 4: "No, not accurate" responses
        "No, this interpretation doesn't match the observed behavior.",
        "This is not supported by the evidence provided.",
        
        # Additional varied responses
        "The data partially aligns with this, particularly regarding Python environments.",
        "Based on terminal commands, this seems accurate for development purposes.",
        "This may be true but requires more context to confirm definitively.",
        "The user's behavior suggests this, though alternative interpretations exist."
    ]
    
    print(f"\n📋 Test Data:")
    print(f"   Total answers: {len(test_answers)}")
    print(f"   Expected semantic groups: ~4")
    
    # Initialize clusterer
    print("\n🔄 Initializing SemanticClusterer...")
    clusterer = SemanticClusterer()
    
    # Perform clustering
    print("\n🔄 Clustering answers...")
    result = clusterer.cluster(test_answers)
    
    # Display results
    print(f"\n{'='*80}")
    print("CLUSTERING RESULTS")
    print(f"{'='*80}")
    print(f"Method: {result.method}")
    print(f"Number of clusters: {result.num_clusters}")
    print(f"Silhouette score: {result.silhouette:.3f}" if result.silhouette else "Silhouette score: N/A")
    
    print(f"\n📊 Cluster Sizes:")
    for label, size in sorted(result.cluster_sizes.items()):
        print(f"   Cluster {label}: {size} items")
    
    # Show cluster contents
    print(f"\n📝 Cluster Contents:")
    clusters_by_label = {}
    for i, label in enumerate(result.labels):
        if label not in clusters_by_label:
            clusters_by_label[label] = []
        clusters_by_label[label].append((i, test_answers[i]))
    
    for label in sorted(clusters_by_label.keys()):
        print(f"\n   [Cluster {label}] ({len(clusters_by_label[label])} items)")
        for idx, text in clusters_by_label[label][:3]:  # Show first 3
            print(f"      {idx}. {text[:80]}...")
        if len(clusters_by_label[label]) > 3:
            print(f"      ... and {len(clusters_by_label[label]) - 3} more")
    
    # Test distribution extraction
    distribution = get_cluster_distribution(result)
    print(f"\n📈 Cluster Distribution (for entropy):")
    print(f"   {distribution}")
    print(f"   Sum: {distribution.sum():.3f} (should be 1.0)")
    
    # Test storage formatting
    print(f"\n💾 Storage Format Sample:")
    storage_format = format_clusters_for_storage(result, test_answers)
    print(json.dumps(storage_format, indent=2)[:400] + "...")
    
    # Validate results
    print(f"\n{'='*80}")
    print("VALIDATION")
    print(f"{'='*80}")
    
    checks = []
    
    # Check 1: Reasonable number of clusters
    reasonable_clusters = 2 <= result.num_clusters <= len(test_answers) // 2
    checks.append(("Reasonable cluster count", reasonable_clusters))
    
    # Check 2: All items assigned
    all_assigned = len(result.labels) == len(test_answers)
    checks.append(("All items assigned", all_assigned))
    
    # Check 3: Distribution sums to 1
    dist_valid = abs(distribution.sum() - 1.0) < 0.01
    checks.append(("Distribution valid", dist_valid))
    
    # Check 4: Silhouette score reasonable (if available)
    if result.silhouette is not None:
        silhouette_ok = result.silhouette > 0.0
        checks.append(("Silhouette score positive", silhouette_ok))
    
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"   {status} {check_name}")
    
    all_passed = all(passed for _, passed in checks)
    
    if all_passed:
        print(f"\n✅ CLUSTERING TEST PASSED")
    else:
        print(f"\n❌ CLUSTERING TEST FAILED")
    
    print(f"{'='*80}")
    
    return all_passed


def main():
    """Run test."""
    print("\n🧪 SEMANTIC CLUSTERING TEST SUITE\n")
    
    success = test_clustering()
    
    if success:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
