"""Offline format diagnostics only: never dispatch or repair a model action."""
import re
import xml.etree.ElementTree as ET
from code_v3b.tool_dispatch import parse_tool_call, DispatchError

SOURCE='https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md'
TAG=re.compile(r'<(/?)(｜+DSML｜+) (calls|invoke|parameter)([^<>]*)>')

def inspect_dsml(raw):
    out={'dsml_detected':'DSML' in raw,'dsml_diagnostic_only':True}
    if not out['dsml_detected']:return out
    try:
        if '<!' in raw or '&' in raw:raise ValueError('DTD/entity syntax not accepted by offline checker')
        tags=list(TAG.finditer(raw))
        if not tags:raise ValueError('No complete DSML tags')
        out['dsml_official_tag_token']=all(t[2]=='｜DSML｜' for t in tags)
        # Noncanonical repeated bars are diagnosed separately, not called official-valid.
        text=TAG.sub(lambda m:'<'+m[1]+m[3]+m[4]+'>',raw.strip())
        if 'DSML' in text:raise ValueError('Unrecognized/incomplete DSML tag')
        root=ET.fromstring(text)
        if root.tag!='calls' or root.attrib or (root.text or '').strip():raise ValueError('Expected one calls block')
        if len(root)!=1:raise ValueError('Expected exactly one invoke; no best-of selection')
        call=root[0]
        if call.tag!='invoke' or set(call.attrib)!={'name'}:raise ValueError('Invalid invoke attributes')
        if (call.text or '').strip() or (call.tail or '').strip():raise ValueError('Unexpected call text')
        args={}
        for p in call:
            if p.tag!='parameter' or set(p.attrib)!={'name','string'}:raise ValueError('Invalid parameter attributes')
            if p.attrib['string']!='true' or len(p):raise ValueError('Only literal string parameters supported')
            if p.attrib['name'] in args:raise ValueError('Duplicate parameter')
            if (p.tail or '').strip():raise ValueError('Unbound text after parameter')
            args[p.attrib['name']]=p.text or ''
        expression=call.attrib['name']+'('+', '.join(k+'='+repr(v) for k,v in args.items())+')'
        # Reuse the original safe literal parser to validate tool names and signatures.
        bound=parse_tool_call(expression)
        out.update(dsml_structure_and_signature_valid=True,dsml_tool=bound.name,
                   dsml_arguments=list(bound.arguments),dsml_original_tool=bound.original_name,
                   dsml_literal_translation=expression)
    except (ET.ParseError,ValueError,DispatchError) as e:
        out.update(dsml_structure_and_signature_valid=False,dsml_diagnostic_error=str(e))
    return out

def check():
    raw='<｜DSML｜ calls><｜DSML｜ invoke name="get_code_of_file_function"><｜DSML｜ parameter name="file_name" string="true">a.py</｜DSML｜ parameter><｜DSML｜ parameter name="func_name" string="true">f</｜DSML｜ parameter></｜DSML｜ invoke></｜DSML｜ calls>'
    a=inspect_dsml(raw);assert a['dsml_structure_and_signature_valid'] and a['dsml_official_tag_token']
    b=inspect_dsml(raw.replace('｜DSML｜','｜｜DSML｜｜'));assert b['dsml_structure_and_signature_valid'] and not b['dsml_official_tag_token']
    assert not inspect_dsml(raw.replace('name="func_name"','name="file_name"'))['dsml_structure_and_signature_valid']
    assert not inspect_dsml(raw.replace('</｜DSML｜ parameter>','',1))['dsml_structure_and_signature_valid']
    assert not inspect_dsml(raw.replace('get_code_of_file_function','get_code_of_bad'))['dsml_structure_and_signature_valid']
    assert not inspect_dsml(raw.replace('string="true"','string="false"',1))['dsml_structure_and_signature_valid']
    assert not inspect_dsml(raw.replace('</｜DSML｜ calls>',raw[raw.index('<｜DSML｜ invoke'):raw.index('</｜DSML｜ calls>')]+'</｜DSML｜ calls>'))['dsml_structure_and_signature_valid']
    print('7 offline DSML diagnostic checks passed; no execution')

if __name__=='__main__':check()
