import itertools

def get_batches(iterable, batch_size: int, include_incomplete: bool=True):
    batches = list(itertools.batched(iterable, batch_size))
    if (not include_incomplete) and batches and (len(batches[-1]) < batch_size):
        batches.pop()
    return batches
