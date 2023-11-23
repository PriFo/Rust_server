
def main() -> None:
    a: int = 5
    b: int = a
    print(id(a) == id(b))
    a = 10
    print(id(a) == id(b))


if __name__ == '__main__':
    main()