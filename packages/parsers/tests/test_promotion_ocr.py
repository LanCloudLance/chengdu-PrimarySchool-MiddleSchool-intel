from chengdu_edu_parsers.mapping_parser import merge_promotion_links
from chengdu_edu_parsers.promotion_ocr import parse_promotion_ocr_boxes


def _box(x0, y0, x1, y1, text):
    return ([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], text, 0.9)


def test_parse_promotion_ocr_boxes_single_zone():
    width = 700
    boxes = [
        _box(60, 80, 100, 100, "04046"),
        _box(180, 80, 320, 100, "成都市棕北小学"),
        _box(500, 120, 620, 140, "成都市棕北中学"),
    ]
    links = parse_promotion_ocr_boxes(boxes, image_width=width)
    assert len(links) == 1
    assert links[0].primary_name == "成都市棕北小学"
    assert "成都市棕北中学" in links[0].target_names


def test_merge_promotion_links_prefers_more_targets():
    from chengdu_edu_parsers.mapping_parser import PromotionLink

    a = PromotionLink("成都市玉林小学", ["成都市玉林中学"], "对口直升", "推断")
    b = PromotionLink(
        "成都市玉林小学",
        ["成都市第十二中学", "成都石室锦城外国语学校"],
        "多校划片摇号",
        "OCR",
    )
    merged = merge_promotion_links([a, b])
    assert len(merged) == 1
    assert len(merged[0].target_names) >= 2
