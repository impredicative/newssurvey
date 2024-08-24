import numpy as np
from scipy.spatial.distance import cosine, euclidean, seuclidean, sqeuclidean

from newsqa.util.openai_ import get_vector


def order_final_sections(user_query: str, sections: list[str], distance: str) -> list[str]:
    """Return a list of sections ordered by distance to the user query."""
    assert len(sections) == len(set(sections))  # Ensure there are no duplicate sections.

    fn_get_vector = lambda text: get_vector(text, model_size="large")
    query_vector = fn_get_vector(user_query)
    section_vectors = {section: fn_get_vector(section) for section in sections}

    match distance:
        case "cosine" | "euclidean" | "sqeuclidean":
            fn_distance = {"cosine": cosine, "euclidean": euclidean, "sqeuclidean": sqeuclidean}[distance]
            distances = {section: fn_distance(query_vector, section_vector) for section, section_vector in section_vectors.items()}
        case "seuclidean":
            variances = np.var(list(section_vectors.values()), axis=0)
            distances = {section: seuclidean(query_vector, section_vector, variances) for section, section_vector in section_vectors.items()}
        case _:
            assert False, distance

    sections = sorted(sections, key=distances.get)
    print(f"SECTION DISTANCES: ({distance})\n" + "\n".join([f"{num}. {section}: {distances[section]}" for num, section in enumerate(sections, start=1)]))

    return sections
