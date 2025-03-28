from core.components.config_parser import Parameters


def main():
    params = Parameters()

    _foo1 = params.group1.var1
    _foo2 = params.var2


if __name__ == "__main__":
    main()
