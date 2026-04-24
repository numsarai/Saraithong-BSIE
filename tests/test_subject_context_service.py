from services.subject_context_service import build_subject_account_context, normalize_subject_account


def test_normalize_subject_account_preserves_supported_account_forms():
    assert normalize_subject_account("001-234-5678") == "0012345678"
    assert normalize_subject_account("1.23456789E+9") == "1234567890"
    assert normalize_subject_account("12345") == ""


def test_build_subject_account_context_marks_conflict_with_inferred_account():
    context = build_subject_account_context(
        subject_account="222-222-2222",
        subject_name="Known Holder",
        identity_guess={"account": "1111111111", "name": "Detected Holder", "account_source": "workbook_header"},
        sample_rows=[{"description": "transfer from 1111111111"}],
    )

    assert context["selected_account"] == "2222222222"
    assert context["selected_name"] == "Known Holder"
    assert context["inferred_account"] == "1111111111"
    assert context["account_match_status"] == "selected_conflicts_with_inferred"
    assert context["authority"] == "analyst_selected"
