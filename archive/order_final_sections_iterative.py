# https://chatgpt.com/share/d5b71d4e-b423-42f5-9351-a995b3399f60

import random


def simulate_oracle(items):
    """Simulate the oracle by randomly shuffling and returning the items with a small chance of inconsistency."""
    shuffled_items = random.sample(items, len(items))
    if random.random() < 0.05:  # 5% chance to introduce inconsistency
        shuffled_items[-1], shuffled_items[-2] = shuffled_items[-2], shuffled_items[-1]
    return sorted(shuffled_items)


def update_pairwise_scores(pairwise_scores, ordered_sample):
    """Update the pairwise scores based on the ordered sample."""
    n = len(ordered_sample)
    for i in range(n):
        for j in range(i + 1, n):
            pairwise_scores[ordered_sample[i]][ordered_sample[j]] += 1


def get_solution(items, pairwise_scores):
    """Get a solution (partial or full) based on the current pairwise_scores."""
    # Calculate scores for each item based solely on how often they precede others
    score_diff = {item: 0 for item in items}
    for item1 in items:
        for item2 in pairwise_scores[item1]:
            score_diff[item1] += pairwise_scores[item1][item2]

    # Sort items based on their scores
    sorted_items = sorted(items, key=lambda x: score_diff[x], reverse=True)

    # Verify if the sorted order is valid
    valid_order = True
    last_valid_index = 0
    for i in range(len(sorted_items) - 1):
        if pairwise_scores[sorted_items[i]][sorted_items[i + 1]] == 0:
            valid_order = False
            last_valid_index = i
            break

    if valid_order:
        return sorted_items  # Full valid solution
    else:
        return sorted_items[: last_valid_index + 1]  # Partial solution up to the last confirmed valid point


# Example usage
items = list(range(1, 90))  # Items from 1 to 89
pairwise_scores = {item1: {item2: 0 for item2 in items if item1 != item2} for item1 in items}

while True:
    sample = random.sample(items, 10)
    ordered_sample = simulate_oracle(sample)
    update_pairwise_scores(pairwise_scores, ordered_sample)
    solution = get_solution(items, pairwise_scores)
    if len(solution) == len(items):
        print("Full solution is available.")
        print(solution)
        break
    else:
        print(f"Partial solution of {len(solution)} out of {len(items)} is available.")
