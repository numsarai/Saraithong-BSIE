from core.bank_logo_registry import build_bank_logo_catalog, find_bank_logo_record


def test_bank_logo_record_exposes_reviewed_reference_metadata():
    lh_bank = find_bank_logo_record("lh_bank")

    assert lh_bank["bank_name_th"] == "ธนาคารแลนด์ แอนด์ เฮ้าส์"
    assert lh_bank["bank_name_en"] == "Land and Houses Bank"
    assert "แขวงยานนาวา" in lh_bank["head_office_address"]
    assert "เขตสาทร" in lh_bank["head_office_address"]


def test_bank_logo_catalog_includes_bank_of_thailand_reference_entry():
    catalog = build_bank_logo_catalog()

    bot = next(item for item in catalog if item["key"] == "bot")
    assert bot["bank_type"] == "regulator"
    assert bot["bank_name_en"] == "Bank of Thailand"
    assert bot["head_office_address"].startswith("273 ถนนสามเสน")
