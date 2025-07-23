from typing import Optional


def print_path(*lines_comps: list[str], seps: Optional[list[str]] = None):
    if seps is None:
        seps = [" <> "] * len(lines_comps)

    comp_size = [0] * len(lines_comps[0])
    for i in range(len(lines_comps[0])):
        for line_comps in lines_comps:
            comp_size[i] = max(comp_size[i], len(line_comps[i]))

    lines: list[str] = []
    for line_comps, sep in zip(lines_comps, seps):
        lines.append(
            sep.join([f"{comp.center(size)}" for (comp, size) in zip(line_comps, comp_size)])
        )

    str_len: int = sum(comp_size) + (len(comp_size) - 1) * len(seps[0]) + 2
    print("/" + "=" * str_len + "\\")
    print("|" + " " * str_len + "|")
    for line in lines:
        print("| " + line + " |")
    print("|" + " " * str_len + "|")
    print("\\" + "=" * str_len + "/")


def packet_statistics(metrics_before: dict, metrics_after: dict, metric: str):
    print("Packets statistics:")
    for (dict_key, before), (dict_key, after) in zip(metrics_before.items(), metrics_after.items()):
        print("\t", dict_key)
        for key, value in getattr(after, metric).items():
            if key not in getattr(before, metric):
                print(f"\t\tKey `{key}` not found in before metrics")
                getattr(before, metric)[key] = 0

            print(f"\t\t{key}: {int(value - getattr(before, metric)[key]):+d}")
