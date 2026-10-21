from quorumy.workspace.config import load_product


def test_product_has_one_identity():
    product = load_product()
    assert product.project_id == "quorumy"
    assert product.display_name == "Quorumy"
    assert product.companion_name == "Quorumy"
    assert product.protocol_version == 14
