"""Shared mapping: Bitrix deal dict → electronic_case Supabase rows.

Used by:
- scripts/sync_bitrix_to_cases.py  (bulk initial sync)
- webhook_server.py                 (real-time onCrmDealUpdate)
"""
from datetime import datetime, timezone

import aiohttp

# ── Enum maps ──────────────────────────────────────────────────────────────────

CITY_MAP = {
    "288": "Воронеж", "290": "Краснодар", "292": "Липецк",
    "294": "Ростов-на-Дону", "1094": "Оренбург", "3190": "Тула",
    "3272": "Ставрополь", "3592": "Кемерово", "3594": "Казань",
    "4008": "Барнаул", "4060": "Новосибирск", "9856": "Томск",
    "10610": "Омск", "10611": "Самара",
}

COURT_REGION_MAP = {
    "2966": "Воронежской области", "2968": "Липецкой области",
    "2970": "Краснодарского края", "2972": "Оренбургской области",
    "2974": "Ростовской области", "3194": "Тульской области",
    "3276": "Ставропольского края", "3852": "Республика Татарстан",
    "4052": "Алтайского края", "4056": "Кемеровской области",
    "4076": "Новосибирской области",
}

MARITAL_MAP = {
    "45": "Не замужем/Не женат", "47": "Женат/Замужем",
    "49": "Разведён/а", "51": "Гражданский брак", "53": "Вдовец/Вдова",
}

HAS_PROPERTY_MAP = {
    "688": "Нет имущества", "690": "Более 1-го жилья", "692": "Автомобиль",
    "694": "Участок", "698": "Гараж", "700": "Другое",
    "702": "Частный дом", "704": "Доля в ООО", "706": "Квартира",
    "1130": "Дача",
}

PROP_TRANSFER_MAP = {
    "3388": "Ничего не продавал", "3390": "Продал квартиру/дом",
    "3392": "Продал землю", "3394": "Продал автомобиль",
    "3396": "Продал коммерческую недвижимость",
}

# Boolean enum: ID that means "да"
_BOOL_YES = {
    "was_ip":       "3546",
    "has_llc":      "3550",
    "guarantor":    "335",
    "alimony":      "407",
    "court_orders": "401",
    "prop_remove":  "4990",
    "court_paid":   "5464",
}

# Fields to select from crm.deal.get / crm.deal.list
DEAL_SELECT = [
    "ID", "STAGE_ID", "CONTACT_ID", "COMMENTS",
    "UF_CRM_1751273997835",  # inn
    "UF_CRM_1588167827780",  # birth_date
    "UF_CRM_1575949766986",  # city
    "UF_CRM_1575482962",     # marital_status
    "UF_CRM_1575960820589",  # dependents_count
    "UF_CRM_1614679272145",  # total_debt_amount (money)
    "UF_CRM_1575950599001",  # creditors_count
    "UF_CRM_1575961128893",  # monthly_loan_payment (double)
    "UF_CRM_1575960875693",  # official_income (double)
    "UF_CRM_1590060934920",  # current_employer
    "UF_CRM_1575961207685",  # income_change_reason
    "UF_CRM_1577191308",     # contract_number
    "UF_CRM_1577191364",     # contract_date
    "UF_CRM_1576047283",     # contract_amount (money)
    "UF_CRM_1605083957926",  # monthly_payment_amount
    "UF_CRM_1580811110539",  # prepayment_amount (money)
    "UF_CRM_1580811172764",  # prepayment_date
    "UF_CRM_1580470958092",  # court_region
    "UF_CRM_1602677906",     # filing_planned_date
    "UF_CRM_1615390023434",  # filing_actual_date
    "UF_CRM_1575489786",     # first_hearing_date
    "UF_CRM_1605095325471",  # last_hearing_date
    "UF_CRM_1603367403",     # suspended_date
    "UF_CRM_1605095304664",  # au_docs_sent_date
    "UF_CRM_1607524042544",  # arbitration_manager
    "UF_CRM_1606902989505",  # court_expenses_paid
    "UF_CRM_1601916846",     # folder_url
    "UF_CRM_1576085591208",  # has_property (enum multi)
    "UF_CRM_1575950661534",  # property_count
    "UF_CRM_1626923422",     # has_pledge (boolean)
    "UF_CRM_1602678216",     # property_removal_before_court
    "UF_CRM_1605094712952",  # au_property_to_sell
    "UF_CRM_1605093669733",  # au_property_excluded
    "UF_CRM_1575959539087",  # risk: transactions_3y
    "UF_CRM_1590074282739",  # risk: was_ip
    "UF_CRM_1590074475807",  # risk: has_llc
    "UF_CRM_1576008183687",  # risk: has_guarantor
    "UF_CRM_1576011948483",  # risk: alimony_debt
    "UF_CRM_1576011793928",  # risk: has_court_orders
    "UF_CRM_1587470558",     # risk: property_transfer
    # payment schedule 1–13 (amount + date pairs)
    "UF_CRM_1593006073786", "UF_CRM_1593006161020",
    "UF_CRM_1593006218088", "UF_CRM_1593006244133",
    "UF_CRM_1593006286132", "UF_CRM_1593006314870",
    "UF_CRM_1593006339322", "UF_CRM_1593006356437",
    "UF_CRM_1593006389262", "UF_CRM_1593006405427",
    "UF_CRM_1593006433323", "UF_CRM_1593006482049",
    "UF_CRM_1593006505297", "UF_CRM_1593006530231",
    "UF_CRM_1593006553903", "UF_CRM_1593006579685",
    "UF_CRM_1593006634513", "UF_CRM_1593006660594",
    "UF_CRM_1593006679899", "UF_CRM_1593006851055",
    "UF_CRM_1593006867904", "UF_CRM_1593006883920",
    "UF_CRM_1593006900478", "UF_CRM_1593006917013",
    "UF_CRM_1593006931764", "UF_CRM_1593006948374",
]

PAYMENT_FIELD_PAIRS = [
    ("UF_CRM_1593006073786", "UF_CRM_1593006161020"),
    ("UF_CRM_1593006218088", "UF_CRM_1593006244133"),
    ("UF_CRM_1593006286132", "UF_CRM_1593006314870"),
    ("UF_CRM_1593006339322", "UF_CRM_1593006356437"),
    ("UF_CRM_1593006389262", "UF_CRM_1593006405427"),
    ("UF_CRM_1593006433323", "UF_CRM_1593006482049"),
    ("UF_CRM_1593006505297", "UF_CRM_1593006530231"),
    ("UF_CRM_1593006553903", "UF_CRM_1593006579685"),
    ("UF_CRM_1593006634513", "UF_CRM_1593006660594"),
    ("UF_CRM_1593006679899", "UF_CRM_1593006851055"),
    ("UF_CRM_1593006867904", "UF_CRM_1593006883920"),
    ("UF_CRM_1593006900478", "UF_CRM_1593006917013"),
    ("UF_CRM_1593006931764", "UF_CRM_1593006948374"),
]

# ── Field helpers ──────────────────────────────────────────────────────────────

def _decode_enum(value, mapping: dict) -> str | None:
    if not value:
        return None
    ids = value if isinstance(value, list) else [value]
    decoded = [mapping[str(v)] for v in ids if mapping.get(str(v))]
    return ", ".join(decoded) if decoded else None


def _decode_bool_enum(value, yes_id: str) -> bool | None:
    if not value:
        return None
    first = value[0] if isinstance(value, list) else value
    return str(first) == yes_id


def _parse_money(value) -> float | None:
    if not value:
        return None
    try:
        return float(str(value).split("|")[0])
    except (ValueError, IndexError):
        return None


def _parse_date(value) -> str | None:
    if not value:
        return None
    return str(value)[:10]


def _parse_int(value) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _has_property_bool(value) -> bool | None:
    if not value:
        return None
    ids = value if isinstance(value, list) else [value]
    return any(str(v) != "688" for v in ids)  # 688 = "Нет имущества"


# ── Deal → cases row ──────────────────────────────────────────────────────────

def build_case_row(deal: dict, contact: dict | None) -> dict:
    """Map Bitrix deal + contact dicts to a cases table row."""
    d = deal
    c = contact or {}

    name_parts = [c.get("LAST_NAME", ""), c.get("NAME", ""), c.get("SECOND_NAME", "")]
    full_name = " ".join(p for p in name_parts if p).strip() or None
    phones = c.get("PHONE", [])
    phone = phones[0]["VALUE"] if phones else None

    schedule = []
    for amt_key, date_key in PAYMENT_FIELD_PAIRS:
        amount = _parse_money(d.get(amt_key))
        date = _parse_date(d.get(date_key))
        if amount or date:
            schedule.append({"amount": amount, "date": date})

    risk = {
        "transactions_3y":  d.get("UF_CRM_1575959539087") or None,
        "was_ip":           _decode_bool_enum(d.get("UF_CRM_1590074282739"), _BOOL_YES["was_ip"]),
        "has_llc_shares":   _decode_bool_enum(d.get("UF_CRM_1590074475807"), _BOOL_YES["has_llc"]),
        "has_guarantor":    _decode_bool_enum(d.get("UF_CRM_1576008183687"), _BOOL_YES["guarantor"]),
        "alimony_debt":     _decode_bool_enum(d.get("UF_CRM_1576011948483"), _BOOL_YES["alimony"]),
        "has_court_orders": _decode_bool_enum(d.get("UF_CRM_1576011793928"), _BOOL_YES["court_orders"]),
        "property_transfer":_decode_enum(d.get("UF_CRM_1587470558"), PROP_TRANSFER_MAP),
    }
    risk_flags = risk if any(v is not None for v in risk.values()) else None

    now = datetime.now(timezone.utc).isoformat()

    return {
        "inn":                           (d.get("UF_CRM_1751273997835") or "").strip(),
        "deal_id":                       str(d["ID"]),
        "stage":                         d.get("STAGE_ID"),
        "full_name":                     full_name,
        "phone":                         phone,
        "birth_date":                    _parse_date(d.get("UF_CRM_1588167827780")),
        "city":                          _decode_enum(d.get("UF_CRM_1575949766986"), CITY_MAP),
        "marital_status":                _decode_enum(d.get("UF_CRM_1575482962"), MARITAL_MAP),
        "dependents_count":              _parse_int(d.get("UF_CRM_1575960820589")),
        "total_debt_amount":             _parse_money(d.get("UF_CRM_1614679272145")),
        "creditors_count":               _parse_int(d.get("UF_CRM_1575950599001")),
        "monthly_loan_payment":          _parse_money(d.get("UF_CRM_1575961128893")),
        "official_income":               _parse_money(d.get("UF_CRM_1575960875693")),
        "current_employer":              d.get("UF_CRM_1590060934920") or None,
        "income_change_reason":          d.get("UF_CRM_1575961207685") or None,
        "contract_number":               d.get("UF_CRM_1577191308") or None,
        "contract_date":                 _parse_date(d.get("UF_CRM_1577191364")),
        "contract_amount":               _parse_money(d.get("UF_CRM_1576047283")),
        "monthly_payment_amount":        _parse_money(d.get("UF_CRM_1605083957926")),
        "prepayment_amount":             _parse_money(d.get("UF_CRM_1580811110539")),
        "prepayment_date":               _parse_date(d.get("UF_CRM_1580811172764")),
        "payment_schedule":              schedule if schedule else None,
        "court_region":                  _decode_enum(d.get("UF_CRM_1580470958092"), COURT_REGION_MAP),
        "filing_planned_date":           d.get("UF_CRM_1602677906") or None,
        "filing_actual_date":            _parse_date(d.get("UF_CRM_1615390023434")),
        "first_hearing_date":            _parse_date(d.get("UF_CRM_1575489786")),
        "last_hearing_date":             _parse_date(d.get("UF_CRM_1605095325471")),
        "suspended_date":                _parse_date(d.get("UF_CRM_1603367403")),
        "au_docs_sent_date":             _parse_date(d.get("UF_CRM_1605095304664")),
        "arbitration_manager":           d.get("UF_CRM_1607524042544") or None,
        "court_expenses_paid":           _decode_bool_enum(d.get("UF_CRM_1606902989505"), _BOOL_YES["court_paid"]),
        "folder_url":                    d.get("UF_CRM_1601916846") or None,
        "has_property":                  _has_property_bool(d.get("UF_CRM_1576085591208")),
        "property_count":                _parse_int(d.get("UF_CRM_1575950661534")),
        "has_pledge":                    bool(d["UF_CRM_1626923422"]) if d.get("UF_CRM_1626923422") else None,
        "property_removal_before_court": _decode_bool_enum(d.get("UF_CRM_1602678216"), _BOOL_YES["prop_remove"]),
        "au_property_to_sell":           d.get("UF_CRM_1605094712952") or None,
        "au_property_excluded":          d.get("UF_CRM_1605093669733") or None,
        "risk_flags":                    risk_flags,
        "synced_at":                     now,
    }


# ── Supabase helpers ───────────────────────────────────────────────────────────

def _supabase_headers(cases_key: str, prefer: str = "resolution=merge-duplicates") -> dict:
    return {
        "apikey": cases_key,
        "Authorization": f"Bearer {cases_key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


async def upsert_case(
    session: aiohttp.ClientSession, row: dict, cases_url: str, cases_key: str
) -> tuple[bool, str | None]:
    async with session.post(
        f"{cases_url}/rest/v1/cases",
        headers=_supabase_headers(cases_key),
        json=row,
    ) as resp:
        if resp.status not in (200, 201):
            text = await resp.text()
            return False, text[:200]
        return True, None


async def insert_communication(
    session: aiohttp.ClientSession,
    inn: str,
    deal_id: str,
    content: str,
    cases_url: str,
    cases_key: str,
) -> None:
    row = {
        "inn": inn,
        "source": "bitrix_comment",
        "content": content.strip(),
        "author_type": "manager",
        "bitrix_id": f"deal_comment_{deal_id}",
    }
    async with session.post(
        f"{cases_url}/rest/v1/communications",
        headers=_supabase_headers(cases_key, prefer="resolution=ignore-duplicates"),
        json=row,
    ) as resp:
        if resp.status not in (200, 201):
            text = await resp.text()
            return text[:100]
    return None
