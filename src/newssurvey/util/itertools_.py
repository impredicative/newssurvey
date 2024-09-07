import itertools


def get_batches(iterable, batch_size: int, include_incomplete: bool = True) -> list[list]:
    batches = [list(batch) for batch in itertools.batched(iterable, batch_size)]  # Note: Using `list` avoids returning tuples.
    if (not include_incomplete) and batches and (len(batches[-1]) < batch_size):
        batches.pop()
    return batches
