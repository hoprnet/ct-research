class SubgraphEntry:
    def __str__(self):
        cls = self.__class__.__name__
        fields = ", ".join(f"{field}={value}" for field, value in vars(self).items())

        return f"{cls}({fields})"

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return vars(self) == vars(other)
