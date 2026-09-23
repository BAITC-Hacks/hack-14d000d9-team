"""Pure detail normalization: no requests, purchase rules, or warehouse arithmetic."""
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from app.exceptions import BridgeError
from app.schemas.product import (
    MAX_ID, MAX_QUANTITY, DataIssue, NormalizedProduct, ProductSpecifications, StoreStock,
)

PROPERTY_MAPPING = {
    "TORGOVAYA_MARKA": "brand",
    "OBYEM": "product_type",
    "KOLICHESTVO_POLYUSOV": "poles",
    "NOMINALNYY_TOK": "rated_current",
    "NOMINALNOE_NAPRYAZHENIE": "rated_voltage",
    "NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST": "breaking_capacity",
    "TIP_USTANOVKI": "installation_type",
    "ARTIKULPOSTAVSHCHIKA": "supplier_article",
}
_CURRENT_TOKEN = re.compile(r"(?<![\w.,+\-])(\d+(?:[.,]\d+)?)\s*[AАaа](?!\w)")
_CURRENT_VALUE = re.compile(r"\s*(\d+(?:[.,]\d+)?)\s*[AАaа]\s*")


def valid_id(value: object) -> bool:
    return type(value) is int and 0 < value <= MAX_ID


def observed(value: object) -> str | int | bool | None:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, (str, Decimal, float)):
        return str(value)[:1024]
    return f"<{type(value).__name__}>"


def issue(code: str, field: str, message: str, *values: object) -> DataIssue:
    return DataIssue(
        code=code, field=field, message=message,
        observed_values=[observed(value) for value in values] if values else None,
    )


def decimal_scalar(value: object) -> Decimal | None:
    """No arithmetic on floats; live JSON fractions are decoded directly as Decimal."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    text = str(value).strip()
    if not text or len(text) > 160:
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    # Bounded prototype scalar sizes also prevent enormous expanded decimal strings.
    if not number.is_finite():
        return None
    if len(number.as_tuple().digits) > 100 or abs(number.as_tuple().exponent) > 100:
        return None
    return number


def optional_text(
    value: object, field: str, issues: list[DataIssue], *, material: bool = False,
) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if material:
            issues.append(issue("TEXT_MISSING", field, f"Catalog text is missing: {field}."))
        return None
    if not isinstance(value, str):
        issues.append(issue("INVALID_TEXT", field, f"Catalog text is malformed: {field}.", value))
        return None
    return value  # Preserve article zeros, underscores, source spelling, and whitespace.


def whole_quantity(
    value: object, field: str, issues: list[DataIssue], *, positive: bool = False,
) -> int | None:
    if value is None:
        issues.append(issue("QUANTITY_MISSING", field, f"Whole-unit quantity is unknown: {field}."))
        return None
    number = decimal_scalar(value)
    if (
        number is None or number < (1 if positive else 0) or number > MAX_QUANTITY
        or number != number.to_integral_value()
    ):
        issues.append(issue(
            "INVALID_QUANTITY", field,
            f"Quantity must be a finite {'positive' if positive else 'nonnegative'} whole number: {field}.",
            value,
        ))
        return None
    return int(number)


def current_tokens(text: str | None) -> tuple[Decimal, ...]:
    """Only explicit standalone A/А tokens; not DRX250 or kA/кА breaking capacity."""
    values: set[Decimal] = set()
    for match in _CURRENT_TOKEN.finditer(text or ""):
        number = decimal_scalar(match.group(1).replace(",", "."))
        if number is not None:
            values.add(number)
    return tuple(sorted(values))


def current_issues(name: str | None, rated_current: str | None) -> list[DataIssue]:
    title_tokens = current_tokens(name)
    property_tokens = current_tokens(rated_current)
    if len(title_tokens) > 1 or len(property_tokens) > 1:
        return [issue(
            "RATED_CURRENT_AMBIGUITY", "specifications.rated_current",
            "Multiple distinct rated-current tokens require authoritative clarification.",
            name, rated_current,
        )]
    match = _CURRENT_VALUE.fullmatch(rated_current or "")
    structured = decimal_scalar(match.group(1).replace(",", ".")) if match else None
    if len(title_tokens) == 1 and structured is not None and title_tokens[0] != structured:
        title_value = format(title_tokens[0], "f") + "A"
        property_value = format(structured, "f") + "A"
        return [issue(
            "RATED_CURRENT_CONFLICT", "specifications.rated_current",
            f"Possible rated current conflict: product name indicates {title_value} "
            f"but structured property indicates {property_value}.",
            title_value, property_value,
        )]
    return []


def display_url(value: object, field: str, issues: list[DataIssue]) -> str | None:
    text = optional_text(value, field, issues)
    if text is None:
        return None
    try:
        parts = urlsplit(text)
        valid = (
            parts.scheme in {"https", "http"} and bool(parts.hostname)
            and parts.username is None and parts.password is None
            and "\\" not in text and not any(character.isspace() for character in text)
        )
        _ = parts.port
    except ValueError:
        valid = False
    if not valid:
        issues.append(issue("INVALID_DISPLAY_URL", field, f"Unusable display URL: {field}."))
        return None
    return text  # Returned as data only; the backend never fetches it.


def normalize_stores(value: object, issues: list[DataIssue]) -> list[StoreStock]:
    """Map received records only. No sums, filtering, reconciliation, or stock policy."""
    if value is None:
        issues.append(issue("WAREHOUSE_LIST_MISSING", "stores", "Warehouse records were not supplied."))
        return []
    if not isinstance(value, list):
        issues.append(issue("INVALID_WAREHOUSE_LIST", "stores", "Warehouse records are malformed."))
        return []
    stores: list[StoreStock] = []
    for index, record in enumerate(value):
        field = f"stores[{index}]"
        if not isinstance(record, dict) or not valid_id(record.get("id")):
            issues.append(issue("INVALID_WAREHOUSE_RECORD", field, "Skipped a warehouse record with an invalid identity."))
            continue
        stores.append(StoreStock(
            id=record["id"],
            name=optional_text(record.get("name"), field + ".name", issues),
            quantity=whole_quantity(record.get("quantity"), field + ".quantity", issues),
        ))
    return stores


def normalize_product(raw: object, *, expected_id: int | None = None) -> NormalizedProduct:
    if not isinstance(raw, dict) or not valid_id(raw.get("id")):
        raise BridgeError("INVALID_EKT_RESPONSE", "The upstream product has an invalid identity.", 502)
    if expected_id is not None and raw["id"] != expected_id:
        raise BridgeError("INVALID_EKT_RESPONSE", "The upstream product identity does not match the request.", 502)

    issues: list[DataIssue] = []
    properties = raw.get("properties")
    if not isinstance(properties, dict):
        issues.append(issue(
            "PROPERTIES_MISSING" if properties is None else "INVALID_PROPERTIES",
            "properties", "Usable structured specifications were not supplied.",
        ))
        properties = {}
    mapped: dict[str, str | int | None] = {}
    for source, target in PROPERTY_MAPPING.items():
        value = properties.get(source)
        field = target if target == "supplier_article" else f"specifications.{target}"
        if target == "poles":
            mapped[target] = None if value is None else whole_quantity(value, field, issues, positive=True)
        else:
            mapped[target] = optional_text(value, field, issues)
    supplier_article = mapped.pop("supplier_article")
    specifications = ProductSpecifications.model_validate(mapped)

    name = optional_text(raw.get("name"), "name", issues, material=True)
    article = optional_text(raw.get("article"), "article", issues, material=True)
    price = decimal_scalar(raw.get("price"))
    if price is None or price < 0:
        issues.append(issue(
            "PRICE_MISSING" if raw.get("price") is None else "INVALID_PRICE",
            "price", "A usable finite nonnegative price was not supplied.", raw.get("price"),
        ))
        price = None
    total_quantity = whole_quantity(raw.get("quantity"), "quantity", issues)
    stores = normalize_stores(raw.get("stores"), issues)
    issues.extend(current_issues(name, specifications.rated_current))
    offers = raw.get("offers")
    if offers is not None and (not isinstance(offers, list) or offers):
        issues.append(issue(
            "UNSUPPORTED_PRODUCT_VARIANT", "offers",
            "Variant targeting cannot be interpreted without a supplied variant contract.",
        ))
    return NormalizedProduct(
        id=raw["id"], article=article, supplier_article=supplier_article, name=name,
        description=optional_text(raw.get("description"), "description", issues), price=price,
        total_quantity=total_quantity,
        available=None if total_quantity is None else total_quantity > 0,
        stores=stores, specifications=specifications,
        image_url=display_url(raw.get("image"), "image_url", issues),
        product_url=display_url(raw.get("url"), "product_url", issues), issues=issues,
    )
