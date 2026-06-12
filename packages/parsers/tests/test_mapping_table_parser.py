from chengdu_edu_parsers.mapping_parser import parse_bendibao_mapping_tables

TABLE_HTML = """
<table>
<tr><td>片号</td><td>小学名称</td><td>服务范围</td></tr>
<tr><td>1</td><td>成都市</td><td>弟维小学</td><td>小税巷、国学巷、小天竺街（63号以后）。</td></tr>
<tr><td>2</td><td>成都市</td><td>武侯计算机</td><td>实验小学</td><td>小学路、中学路、金陵路、金陵横路。</td></tr>
<tr><td>3</td><td>成都市</td><td>磨子桥小学</td><td>一环路南二段（双号）、磨子巷、科华北路。</td></tr>
<tr><td>10</td><td>成都市龙江路小学分校</td><td>武侯祠大街（89号以后部分）、蜀汉街、体院路。</td></tr>
</table>
"""


def test_parse_bendibao_mapping_tables():
    scopes = parse_bendibao_mapping_tables(TABLE_HTML)
    assert len(scopes) == 4
    names = {s.school_name for s in scopes}
    assert "成都市弟维小学" in names
    assert "成都市武侯计算机实验小学" in names
    assert "成都市磨子桥小学" in names
    assert "成都市龙江路小学分校" in names
