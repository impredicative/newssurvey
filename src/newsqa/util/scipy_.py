from typing import Literal

import numpy as np
from scipy.spatial.distance import cosine, euclidean, seuclidean, sqeuclidean

from newsqa.util.openai_ import EmbeddingModelSizeType, get_vector

DistanceType = Literal["cosine", "euclidean", "sqeuclidean", "seuclidean"]


def sort_by_distance(reference: str, items: list[str], *, model_size: EmbeddingModelSizeType, distance: str = DistanceType) -> list[str]:
    """Return items sorted by distance to the reference using the distance function."""
    fn_get_vector = lambda text: get_vector(text, model_size=model_size)
    reference_vector = fn_get_vector(reference)
    item_vectors = {item: fn_get_vector(item) for item in items}

    match distance:
        case "cosine" | "euclidean" | "sqeuclidean":
            fn_distance = {"cosine": cosine, "euclidean": euclidean, "sqeuclidean": sqeuclidean}[distance]
            distances = {item: fn_distance(reference_vector, item_vector) for item, item_vector in item_vectors.items()}
        case "seuclidean":
            variances = np.var(list(item_vectors.values()), axis=0)
            distances = {item: seuclidean(reference_vector, item_vector, variances) for item, item_vector in item_vectors.items()}
        case _:
            assert False, distance

    items = sorted(items, key=distances.get)  # Note: The sort is intentionally not done in-place to avoid modifying the input list.
    print(f"ITEM DISTANCES: ({distance})\n" + "\n".join([f"{num}. {item}: {distances[item]:.4f}" for num, item in enumerate(items, start=1)]))

    return items