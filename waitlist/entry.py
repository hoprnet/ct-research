from pandas import DataFrame, Series, read_excel


class Entry:
    @classmethod
    def fromXLSX(cls, filename: str):
        data = read_excel(filename, sheet_name="Sheet1")
        return cls.fromDataFrame(data)

    @classmethod
    def fromDataFrame(cls, entries: DataFrame):
        entries = [cls.fromPandaSerie(entry) for _, entry in entries.iterrows()]
        entries = [entry for entry in entries if entry is not None]

        # write in bold
        print("\033[1m", end="")
        print(f"{cls.__name__} // Loaded {len(entries)} entries", end="")
        print("\033[0m")

        return entries

    @classmethod
    def fromPandaSerie(cls, entry: Series):
        items: dict[str, str] = cls._import_keys_and_values()

        return cls(**{key: entry[value] for key, value in items.items()})

    def __str__(self):
        attributes = [
            attr
            for attr in dir(self)
            if not attr.startswith("_") and not callable(getattr(self, attr))
        ]

        return (
            f"{self.__class__.__name__}("
            + ", ".join([f"{attr}='{getattr(self, attr)}'" for attr in attributes])
            + ")"
        )
