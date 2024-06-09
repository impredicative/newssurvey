def dict_str(data: dict, *, sep: str = ", ") -> str:
    return sep.join(f"{k}={v}" for k, v in data.items())
