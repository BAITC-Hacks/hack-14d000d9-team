import copy
import json
from decimal import Decimal

import pytest

from app.exceptions import BridgeError
from app.schemas.product import NormalizedProduct
from app.services.normalization import current_tokens, normalize_product


def test_supplied_mapping_articles_and_conflict(raw_product):
    untouched = copy.deepcopy(raw_product)
    product = normalize_product(raw_product, expected_id=515291)
    assert raw_product == untouched
    assert product.id == 515291
    assert product.article == "200300285_"
    assert product.supplier_article == "027228"
    assert product.name == raw_product["name"]
    assert product.description == raw_product["description"]
    assert product.price == Decimal("64920")
    assert product.total_quantity == 23
    assert product.available is True
    assert product.specifications.model_dump() == {
        "brand": "Legrand", "product_type": "Автоматический выключатель", "poles": 3,
        "rated_current": "250 А", "rated_voltage": "400В", "breaking_capacity": "18кА",
        "installation_type": "Винтовое",
    }
    assert [store.model_dump() for store in product.stores] == raw_product["stores"]
    conflict = next(issue for issue in product.issues if issue.code == "RATED_CURRENT_CONFLICT")
    assert conflict.observed_values == ["160A", "250A"]
    assert product.warnings == [issue.message for issue in product.issues]


def test_unknown_fields_remain_unknown():
    product = normalize_product({"id": 1})
    for field in ["article", "supplier_article", "name", "description", "price", "total_quantity", "available", "image_url", "product_url"]:
        assert getattr(product, field) is None
    assert product.stores == []
    assert all(value is None for value in product.specifications.model_dump().values())
    assert "QUANTITY_MISSING" in {issue.code for issue in product.issues}
    assert "WAREHOUSE_LIST_MISSING" in {issue.code for issue in product.issues}


def test_zero_is_not_missing_and_total_is_not_a_warehouse_sum():
    product = normalize_product({"id": 1, "price": 0, "quantity": 0, "stores": [{"id": 3, "quantity": 20}]})
    assert product.price == Decimal(0)
    assert product.total_quantity == 0
    assert product.available is False
    assert product.stores[0].quantity == 20
    assert not hasattr(product, "warehouse_quantity_sum")
    assert not any(issue.code == "STOCK_TOTAL_MISMATCH" for issue in product.issues)


@pytest.mark.parametrize("value", [-1, True, False, "broken", "NaN", "Infinity", float("inf"), float("nan"), Decimal("-Infinity"), {}, "1e9999"])
def test_invalid_prices_become_null_with_evidence(value):
    product = normalize_product({"id": 1, "price": value})
    assert product.price is None
    finding = next(issue for issue in product.issues if issue.field == "price")
    assert finding.code == "INVALID_PRICE"
    assert finding.observed_values is not None
    if value == -1:
        assert finding.observed_values == [-1]
    json.loads(product.model_dump_json())  # Invalid scalars must not make invalid JSON.


@pytest.mark.parametrize("value", [-2, True, False, 2.5, "2.5", "bad", "NaN", float("inf"), [], "1e999"])
def test_invalid_quantities_remain_unknown(value):
    product = normalize_product({"id": 1, "quantity": value})
    assert product.total_quantity is None
    assert product.available is None
    finding = next(issue for issue in product.issues if issue.field == "quantity")
    assert finding.code == "INVALID_QUANTITY"
    if value == -2:
        assert finding.observed_values == [-2]


@pytest.mark.parametrize("value", [23, "23", Decimal("23.0"), 23.0])
def test_whole_unit_upstream_numbers_are_supported(value):
    assert normalize_product({"id": 1, "quantity": value}).total_quantity == 23


@pytest.mark.parametrize("raw", [None, [], {}, {"id": 0}, {"id": -1}, {"id": True}, {"id": "1"}, {"id": 1.0}])
def test_invalid_detail_identity_is_not_normalized(raw):
    with pytest.raises(BridgeError) as caught:
        normalize_product(raw)
    assert caught.value.code == "INVALID_EKT_RESPONSE"


def test_expected_identity_must_match():
    with pytest.raises(BridgeError):
        normalize_product({"id": 1}, expected_id=2)


@pytest.mark.parametrize("text,expected", [
    ("DRX250 18kA", ()), ("DRX250 18кА", ()), ("DRX250 18 кА", ()),
    ("DRX250 MT 160А 18ka", (Decimal("160"),)),
    ("160 A", (Decimal("160"),)), ("160\u00a0А", (Decimal("160"),)),
    ("device 16a", (Decimal("16"),)), ("DRX250", ()),
    ("10,5 А", (Decimal("10.5"),)),
    ("160 А / 250A", (Decimal("160"), Decimal("250"))),
])
def test_lightweight_current_tokens(text, expected):
    assert current_tokens(text) == expected


def test_multiple_currents_are_ambiguous_not_a_confident_conflict():
    product = normalize_product({"id": 1, "name": "160 A / 250 А", "properties": {"NOMINALNYY_TOK": "250 А"}})
    codes = {issue.code for issue in product.issues}
    assert "RATED_CURRENT_AMBIGUITY" in codes
    assert "RATED_CURRENT_CONFLICT" not in codes
    assert product.specifications.rated_current == "250 А"


def test_matching_current_and_title_model_number_do_not_create_conflicts():
    product = normalize_product({"id": 1, "name": "DRX250 160A 18кА", "properties": {"NOMINALNYY_TOK": "160 А"}})
    assert not any(issue.code.startswith("RATED_CURRENT_") for issue in product.issues)


def test_malformed_optional_text_and_properties_are_not_guessed():
    product = normalize_product({"id": 1, "name": "Legrand 160A", "article": 123, "properties": []})
    assert product.article is None
    assert product.specifications.brand is None
    assert product.specifications.rated_current is None
    assert "INVALID_PROPERTIES" in {issue.code for issue in product.issues}


def test_top_level_article_is_not_replaced_by_other_fields():
    product = normalize_product({"id": 1, "properties": {"CML2_ARTICLE": "001_", "ARTIKULPOSTAVSHCHIKA": "00001"}})
    assert product.article is None
    assert product.supplier_article == "00001"


def test_invalid_store_records_get_issues_without_invented_quantities():
    product = normalize_product({"id": 1, "stores": [
        "malformed", {"id": True}, {"id": 3, "name": "Source spelling", "quantity": -2},
        {"id": 4, "quantity": 0}, {"id": 5},
    ]})
    assert [(store.id, store.quantity) for store in product.stores] == [(3, None), (4, 0), (5, None)]
    assert product.stores[0].name == "Source spelling"
    assert len([issue for issue in product.issues if issue.code == "INVALID_WAREHOUSE_RECORD"]) == 2
    assert product.total_quantity is None


def test_variants_expose_only_a_normalization_limitation():
    product = normalize_product({"id": 1, "offers": [{"id": 9}]})
    assert "UNSUPPORTED_PRODUCT_VARIANT" in {issue.code for issue in product.issues}
    assert "offers" not in product.model_dump()


def test_money_strings_and_independent_list_defaults():
    first = NormalizedProduct(id=1, price=Decimal("0.10"))
    second = NormalizedProduct(id=2)
    assert json.loads(first.model_dump_json())["price"] == "0.10"
    first.issues.extend(normalize_product({"id": 1}).issues)
    assert second.issues == []
    assert second.warnings == []


def test_urls_are_display_data_and_unsafe_schemes_are_dropped():
    product = normalize_product({
        "id": 1, "image": "https://images.example.test/product.jpg",
        "url": "javascript:alert(1)", "url_api_detail": "https://attacker.invalid/detail",
    })
    assert product.image_url == "https://images.example.test/product.jpg"
    assert product.product_url is None
    assert "url_api_detail" not in product.model_dump()
    assert "INVALID_DISPLAY_URL" in {issue.code for issue in product.issues}
