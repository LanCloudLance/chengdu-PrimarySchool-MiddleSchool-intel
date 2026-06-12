from chengdu_edu_parsers.mapping_parser import (
    infer_group_promotion_links,
    merge_scope_dicts,
    parse_mapping_adjustment_sections,
    parse_mapping_document,
    parse_promotion_links,
    parse_road_name_scopes,
    parse_school_scopes,
    parse_zone_school_list_scopes,
)

GAOXIN_SCOPE_SAMPLE = """
三、各校划片范围详情
1.
成都师范银都紫菀小学
北至吉龙路，南至应龙路，西至锦韵路，东与锦江区交界。
2.
四川省教育科学研究院附属实验小学（成都高新区梓州小学）
天府大道和老成仁路（锦韵路）以东，梓州大道以西，会龙大道以北，应龙路以南。
"""

PROMO_SAMPLE = """
成都市棕北小学对口成都市棕北中学。
盐道街小学对应升入七中育才学校。
"""


def test_parse_numbered_school_scopes():
    scopes = parse_school_scopes(GAOXIN_SCOPE_SAMPLE)
    assert len(scopes) >= 2
    names = {s.school_name for s in scopes}
    assert any("银都紫菀" in n for n in names)
    assert scopes[0].enrollment_scope.startswith("北至") or "吉龙路" in scopes[0].enrollment_scope


def test_parse_promotion_pairs():
    links = parse_promotion_links(PROMO_SAMPLE)
    assert len(links) >= 1
    assert any("棕北" in link.primary_name for link in links)


def test_infer_group_promotion_links():
    links = infer_group_promotion_links(
        ["成都市棕北小学", "成都市玉林小学"],
        ["成都市棕北中学", "成都市玉林中学"],
    )
    primaries = {l.primary_name for l in links}
    assert "成都市棕北小学" in primaries


def test_parse_mapping_document_from_minimal_html():
    html = f"<div class='content'>{GAOXIN_SCOPE_SAMPLE}</div>"
    result = parse_mapping_document(html)
    assert len(result.school_scopes) >= 2


WUHOU_ADJUSTMENT = """
一、西川悦湖学校(小学)拟确定的入学划片范围
江安河以东，青羊区界以南，智远大道以西，永康路以北区域。
二、成都市龙江路小学悦湖学校调整后的入学划片范围
智远大道以东，青羊区界以南、武青北路以西，永康路以北区域。
三、川大附小明雅学校调整后的入学划片范围
江安河以东，永康路以南，智远大道以西，金瓦路以北区域。
四、其他事项
(一)以上入学划片范围的划定和调整均指武侯户籍儿童。
二、其他事项
(一)以上入学划片范围的政策说明不应被误解析为学校划片。
"""


def test_merge_scope_dicts_prefers_html_over_ocr():
    rows = merge_scope_dicts(
        [
            {
                "school_name": "成都市弟维小学",
                "enrollment_scope": "OCR污染" + "x" * 200,
                "scope_source": "ocr",
                "is_reference": True,
                "intel_year": 2025,
            },
            {
                "school_name": "成都市弟维小学",
                "enrollment_scope": "小税巷、国学巷、临江西路。",
                "scope_source": "html",
                "is_reference": True,
                "intel_year": 2024,
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["scope_source"] == "html"
    assert "小税巷" in rows[0]["enrollment_scope"]


def test_parse_mapping_adjustment_sections():
    scopes = parse_mapping_adjustment_sections(WUHOU_ADJUSTMENT)
    assert len(scopes) == 3
    names = {s.school_name for s in scopes}
    assert "成都市西川悦湖学校" in names
    assert "成都市龙江路小学悦湖学校" in names
    assert "四川大学附属实验小学明雅学校" in names


ROAD_NAME_SAMPLE = """
成都市泡桐树小学

划片范围涉及道路名称：泡桐树街，商业街，实业街。
"""


def test_parse_road_name_scopes():
    scopes = parse_road_name_scopes(ROAD_NAME_SAMPLE)
    assert len(scopes) == 1
    assert scopes[0].school_name == "成都市泡桐树小学"


ZONE_SCHOOL_SAMPLE = """
(一) A学区(华阳片区)
梓州大道以西，沈阳路以北的区域。
该学区学校(2所)
四川天府新区第三小学
四川天府新区第四小学
(二) C学区
通州路以西的区域。
该学区学校(1所)
四川天府新区第七小学
"""


def test_parse_zone_school_list_scopes():
    scopes, zones = parse_zone_school_list_scopes(ZONE_SCHOOL_SAMPLE)
    assert len(scopes) == 3
    assert len(zones) >= 2
    assert any("第三小学" in s.school_name for s in scopes)
