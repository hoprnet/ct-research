import os

OK_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_."
PREFIXES = ["param.", "params."]


def _find_parameters_in_file(file: str) -> list[str]:
    variables: list[str] = []
    with open(file, "r") as f:
        lines = f.readlines()

    # concatenate all lines into a single line
    data = " ".join(lines).lower()
    idx = 0

    while idx < len(data):
        # check if text starting at index idx is "param." or "params."
        for prefix in PREFIXES:
            if data[idx : idx + len(prefix)] == prefix:
                break
        else:
            idx += 1
            continue

        start_idx = idx + len(prefix)
        idx += len(prefix)

        while data[idx] in OK_CHARS:
            idx += 1
        variables.append(data[start_idx:idx].replace(".", "_").upper())

    return set(variables)


def list_parameters(*folders: list[str]):
    all_variables = set()

    for folder in folders:
        for file in os.listdir(folder):
            if not file.endswith(".py"):
                continue

            all_variables.update(_find_parameters_in_file(f"{folder}/{file}"))

    return sorted(list(all_variables))


if __name__ == "__main__":
    list_parameters("core", "database")
