"""Assert-based self-check: python -m app.services.pay_rules_check"""
from __future__ import annotations

from app.services.pay_rules import assert_first_or_partial_pay, min_first_pay
from package.common.errors import BadRequestError


def _ok(fn, *a, **kw):
    fn(*a, **kw)


def _fail(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except BadRequestError:
        return
    raise AssertionError("expected BadRequestError")


def main() -> None:
    assert min_first_pay(1000) == 800.0
    _ok(assert_first_or_partial_pay, total=1000, already_paid=0, pay=800)
    _ok(assert_first_or_partial_pay, total=1000, already_paid=0, pay=1000)
    _fail(assert_first_or_partial_pay, total=1000, already_paid=0, pay=799)
    _ok(assert_first_or_partial_pay, total=1000, already_paid=800, pay=50)
    _ok(assert_first_or_partial_pay, total=1000, already_paid=800, pay=200)
    _fail(assert_first_or_partial_pay, total=1000, already_paid=800, pay=201)
    print("pay_rules_check ok")


if __name__ == "__main__":
    main()
