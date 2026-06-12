from chengdu_edu_parsers.mapping_ocr import (
    extract_mapping_image_urls,
    parse_ocr_table_boxes,
)


def test_extract_mapping_image_urls_from_data_echo():
    html = """
    <img data-echo="https://imgbdb4.bendibao.com/sl/600_0_/cdbdb/edu/20256/17/x_thumb.png"
         bigpicsrc="https://imgbdb4.bendibao.com/cdbdb/edu/20256/17/x_full.png" />
    """
    urls = extract_mapping_image_urls(html)
    assert "https://imgbdb4.bendibao.com/cdbdb/edu/20256/17/x_full.png" in urls
    assert all("/sl/" not in u for u in urls)


def test_parse_ocr_table_boxes_simple_row():
    boxes = [
        ([[10, 200], [120, 200], [120, 230], [10, 230]], "1成都市弟维小学", 0.95),
        ([[500, 200], [900, 200], [900, 230], [500, 230]], "小税巷、国学巷、武侯区某路1号。", 0.9),
    ]
    scopes = parse_ocr_table_boxes(boxes, image_width=1000)
    assert len(scopes) == 1
    assert scopes[0].school_name == "成都市弟维小学"
    assert "小税巷" in scopes[0].enrollment_scope


def test_parse_ocr_table_boxes_split_name_prefix():
    boxes = [
        ([[80, 300], [200, 300], [200, 330], [80, 330]], "成都市", 0.9),
        ([[80, 335], [260, 335], [260, 365], [80, 365]], "武侯计算机实验小学", 0.9),
        ([[500, 300], [900, 330], [900, 360], [500, 360]], "小学路、中学路、金陵路。", 0.9),
    ]
    scopes = parse_ocr_table_boxes(boxes, image_width=1000)
    assert len(scopes) == 1
    assert scopes[0].school_name == "成都市武侯计算机实验小学"
