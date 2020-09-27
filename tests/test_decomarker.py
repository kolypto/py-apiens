from functools import wraps

from apiens.util import decomarker


def test_decomarkers_simple():
    # Create a class
    class A:
        @decomarker_1(1)
        def a(self): pass

        @decomarker_1(2)
        def b(self): pass

        @decomarker_2(3)
        def c(self): pass

    # is_decorated()
    assert decomarker_1.is_decorated(A.a) == True
    assert decomarker_1.is_decorated(A.b) == True
    assert decomarker_1.is_decorated(A.c) == False

    assert decomarker_2.is_decorated(A.a) == False
    assert decomarker_2.is_decorated(A.b) == False
    assert decomarker_2.is_decorated(A.c) == True

    # isinstance() checks
    assert isinstance(A.a, decomarker_1) == True
    assert isinstance(A.b, decomarker_1) == True
    assert isinstance(A.c, decomarker_1) == False

    assert isinstance(A.a, decomarker_2) == False
    assert isinstance(A.b, decomarker_2) == False
    assert isinstance(A.c, decomarker_2) == True

    # Collect: decorator 1
    m1s = decomarker_1.all_decorated_from(A)

    assert len(m1s) == 2
    assert (m1s[0].func_name, m1s[0].arg1) == ('a', 1)
    assert (m1s[1].func_name, m1s[1].arg1) == ('b', 2)

    # Collect: decorator 2
    m2s = decomarker_2.all_decorated_from(A)
    assert len(m2s) == 1
    assert (m2s[0].func_name, m2s[0].arg2) == ('c', 3)


def test_decomarkers_mixed_with_other_decorators():
    # === Test: now try to mix it with other decorators
    class B:
        @nop_decorator  # won't hide it
        @decomarker_1(0)
        def a(self): pass

        @decomarker_1(0)
        @nop_decorator
        def b(self): pass

    # isinstance() checks
    # They work even through the second decorator
    assert isinstance(B.a, decomarker_1) == True
    assert isinstance(B.b, decomarker_1) == True

    # Collect
    m1s = decomarker_1.all_decorated_from(B)
    assert len(m1s) == 2
    assert (m1s[0].func_name, m1s[0].arg1) == ('a', 0)
    assert (m1s[1].func_name, m1s[1].arg1) == ('b', 0)


def test_several_decomarkers_at_the_same_time():
    class C:
        @nop_decorator
        @decomarker_1(1)
        @decomarker_2(2)
        def a(self): pass

        @nop_decorator
        @decomarker_2(3)
        @decomarker_1(4)
        def b(self): pass

    # isinstance() checks
    assert isinstance(C.a, decomarker_1) == True
    assert isinstance(C.a, decomarker_2) == True
    assert isinstance(C.b, decomarker_1) == True
    assert isinstance(C.b, decomarker_2) == True

    # Collect: decorator 1
    m1s = decomarker_1.all_decorated_from(C)
    assert len(m1s) == 2
    assert (m1s[0].func_name, m1s[0].arg1) == ('a', 1)
    assert (m1s[1].func_name, m1s[1].arg1) == ('b', 4)

    # Collect: decorator 2
    m2s = decomarker_2.all_decorated_from(C)
    assert len(m2s) == 2
    assert (m2s[0].func_name, m2s[0].arg2) == ('a', 2)
    assert (m2s[1].func_name, m2s[1].arg2) == ('b', 3)



# Example wrappers


class decomarker_1(decomarker):
    arg1: str

    def __init__(self, arg1):
        super().__init__()
        self.arg1 = arg1


class decomarker_2(decomarker):
    arg2: str

    def __init__(self, arg2):
        super().__init__()
        self.arg2 = arg2


def nop_decorator(f):
    @wraps(f)
    def wrapper(*a, **k):
        return f(*a, **k)
    return wrapper
