#!/usr/bin/env python3
"""Build an editable Chinese DOCX from the paper's reviewed JSON translation.

Uses only the Python standard library. No network, model, GPU, or historical
experiment files are accessed. Equations are native Office Math (OMML), not
screenshots. Run from any directory; paths in the JSON are relative to its parent.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'dcterms': 'http://purl.org/dc/terms/',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
CONTENT = 'http://schemas.openxmlformats.org/package/2006/content-types'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
BLUE = '244A73'
TEXT = '202D39'
FONT_CN = 'Noto Serif CJK SC'
FONT_WEST = 'Times New Roman'
PAGE_W, PAGE_H, MARGIN = 11906, 16838, 1247  # A4 and 22 mm in twips.
TEXT_W = PAGE_W - 2 * MARGIN
CITE = re.compile(r'\{cite:([^{}]+)\}')


def q(name):
    prefix, local = name.split(':')
    return '{' + NS[prefix] + '}' + local


def element(name, attrs=None, text=None):
    node = ET.Element(q(name), {q(k) if ':' in k and not k.startswith('{') else k: str(v)
                              for k, v in (attrs or {}).items()})
    if text is not None:
        node.text = str(text)
    return node


def sub(parent, name, attrs=None, text=None):
    node = element(name, attrs, text)
    parent.append(node)
    return node


def xml_bytes(root):
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def rpr(size=22, bold=False, color=TEXT, italic=False):
    prop = element('w:rPr')
    sub(prop, 'w:rFonts', {'w:ascii': FONT_WEST, 'w:hAnsi': FONT_WEST,
                         'w:eastAsia': FONT_CN, 'w:cs': FONT_WEST})
    sub(prop, 'w:sz', {'w:val': size})
    sub(prop, 'w:szCs', {'w:val': size})
    sub(prop, 'w:color', {'w:val': color})
    if bold:
        sub(prop, 'w:b')
    if italic:
        sub(prop, 'w:i')
    sub(prop, 'w:lang', {'w:val': 'en-US', 'w:eastAsia': 'zh-CN'})
    return prop


def text_run(text, size=22, bold=False, color=TEXT, italic=False):
    run = element('w:r')
    run.append(rpr(size, bold, color, italic))
    parts = str(text).split('\n')
    for i, part in enumerate(parts):
        if i:
            sub(run, 'w:br')
        sub(run, 'w:t', {XML_SPACE: 'preserve'}, part)
    return run


def p_properties(style='Normal', align=None, keep_next=False, before=0,
                 after=100, first_line=420, keep_lines=False):
    prop = element('w:pPr')
    sub(prop, 'w:pStyle', {'w:val': style})
    if align:
        sub(prop, 'w:jc', {'w:val': align})
    sub(prop, 'w:spacing', {'w:before': before, 'w:after': after,
                          'w:line': 276, 'w:lineRule': 'auto'})
    sub(prop, 'w:ind', {'w:firstLine': first_line})
    sub(prop, 'w:widowControl')
    if keep_next:
        sub(prop, 'w:keepNext')
    if keep_lines:
        sub(prop, 'w:keepLines')
    return prop


def math_run(text, normal=False):
    run = element('m:r')
    prop = sub(run, 'm:rPr')
    sub(prop, 'm:sty', {'m:val': 'p' if normal else 'i'})
    if normal:
        sub(prop, 'm:nor')
    run.append(rpr(22))
    sub(run, 'm:t', {XML_SPACE: 'preserve'}, text)
    return run


def math_seq(*items):
    nodes = []
    for item in items:
        if isinstance(item, str):
            nodes.append(math_run(item))
        elif isinstance(item, list):
            nodes.extend(item)
        else:
            nodes.append(item)
    return nodes


def math_sub(base, suffix):
    node = element('m:sSub')
    sub(node, 'm:e').extend(math_seq(base))
    sub(node, 'm:sub').extend(math_seq(suffix))
    return node


def math_sup(base, suffix):
    node = element('m:sSup')
    sub(node, 'm:e').extend(math_seq(base))
    sub(node, 'm:sup').extend(math_seq(suffix))
    return node


def fraction(numerator, denominator):
    node = element('m:f')
    sub(node, 'm:num').extend(math_seq(numerator))
    sub(node, 'm:den').extend(math_seq(denominator))
    return node


def delimited(items, left='(', right=')'):
    node = element('m:d')
    prop = sub(node, 'm:dPr')
    sub(prop, 'm:begChr', {'m:val': left})
    sub(prop, 'm:endChr', {'m:val': right})
    sub(node, 'm:e').extend(math_seq(items))
    return node


def equation_nodes(key):
    """Known manuscript equations, with real fractions/subscripts/case arrays."""
    lo, hi = math_sub('τ', math_run('lo', True)), math_sub('τ', math_run('hi', True))
    if key == 'score':
        score = fraction(math_seq(math_sub('z', math_run('yes', True)), '(x)−',
                                  math_sub('z', math_run('no', True)), '(x)'), 'T')
        return [math_seq('p(x)=σ', delimited(score), ',    σ(u)=',
                         fraction('1', math_seq('1+', math_sup('e', '−u'))))]
    if key == 'route':
        matrix = element('m:m')
        prop = sub(matrix, 'm:mPr')
        cols = sub(prop, 'm:mcs')
        for align in ['left', 'left']:
            col = sub(cols, 'm:mc')
            cp = sub(col, 'm:mcPr')
            sub(cp, 'm:count', {'m:val': 1})
            sub(cp, 'm:mcJc', {'m:val': align})
        for label, condition in [('Reject（剪除）', math_seq('p(x)≤', lo)),
                                 ('Retain（保留）', math_seq('p(x)≥', hi)),
                                 ('Escalate（升级）', math_seq(deepcopy(lo), '<p(x)<', deepcopy(hi)))]:
            row = sub(matrix, 'm:mr')
            sub(row, 'm:e').append(math_run(label, True))
            sub(row, 'm:e').extend(condition)
        return [math_seq('r(x)=', delimited(matrix, '{', ''))]
    if key == 'threshold':
        lim = element('m:limLow')
        sub(lim, 'm:e').append(math_run('min', True))
        sub(lim, 'm:lim').extend(math_seq('x∈', math_sub('G', math_run('val', True))))
        return [math_seq(lo, '=', math_run('nextafter', True),
                         delimited(math_seq(lim, 'p(x),−∞')))]
    if key == 'metrics':
        gi = lambda: math_sub('G', 'i')
        pi = lambda k: math_sup(math_sub('P', 'i'), str(k))
        intersection = lambda: delimited(math_seq(pi(5), '∩', gi()), '|', '|')
        hit = math_seq(math_sub(math_run('Hit', True), 'i'), '@k=1', delimited(math_seq(pi('k'), '∩', gi(), '≠∅'), '[', ']'))
        rec = math_seq(math_sub(math_run('Recall', True), 'i'), '@5=', fraction(intersection(), delimited(gi(), '|', '|')))
        prec = math_seq(math_sub(math_run('Prec', True), 'i'), '@5=', fraction(intersection(), '5'))
        all_ = math_seq(math_sub(math_run('All', True), 'i'), '@5=1', delimited(math_seq(gi(), '⊆', pi(5)), '[', ']'))
        return [math_seq(hit, '; ', rec), math_seq(prec, '; ', all_)]
    raise ValueError(f'Unknown equation key: {key}')


class WordBuilder:
    def __init__(self, content, base_dir):
        self.content = content
        self.base_dir = base_dir
        self.refs = {x['key']: int(x['number']) for x in content['references']}
        self.used_refs = set()
        self.media = {}
        self.rels = [
            ('rIdStyles', 'styles', 'styles.xml', None),
            ('rIdSettings', 'settings', 'settings.xml', None),
            ('rIdFonts', 'fontTable', 'fontTable.xml', None),
            ('rIdHeader', 'header', 'header1.xml', None),
            ('rIdFooter', 'footer', 'footer1.xml', None),
        ]
        self.doc = element('w:document')
        self.body = sub(self.doc, 'w:body')
        self.figure_count = 0
        self.table_count = 0
        self.equation_count = 0

    def citations(self, text):
        def replace(match):
            keys = [x.strip() for x in match.group(1).split(',')]
            missing = set(keys) - set(self.refs)
            if missing:
                raise ValueError(f'Unknown references: {missing}')
            self.used_refs.update(keys)
            return '[' + ', '.join(str(self.refs[k]) for k in keys) + ']'
        return CITE.sub(replace, str(text))

    def paragraph(self, text='', *, parent=None, style='Normal', align='both',
                  size=22, bold=False, color=TEXT, keep_next=False, before=0,
                  after=100, first_line=420, keep_lines=False):
        target = self.body if parent is None else parent
        node = sub(target, 'w:p')
        node.append(p_properties(style, align, keep_next, before, after, first_line, keep_lines))
        if text:
            node.append(text_run(self.citations(text), size, bold, color))
        return node

    def heading(self, text, level):
        return self.paragraph(text, style=f'Heading{level}', align='left',
                              size=28 if level == 1 else 24, bold=True,
                              color=BLUE, keep_next=True, before=220 if level == 1 else 160,
                              after=110, first_line=0, keep_lines=True)

    def equation(self, key, number):
        for i, nodes in enumerate(equation_nodes(key)):
            p = self.paragraph('', style='Equation', align='center', before=70,
                               after=100, first_line=0, keep_lines=True)
            om = sub(p, 'm:oMath')
            om.extend(nodes)
            if i == 0 and number:
                p.append(text_run('    ' + number, size=22))
        self.equation_count += 1

    def figure(self, path, caption):
        src = self.base_dir / path
        raw = src.read_bytes()
        if raw[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('Word figures must be PNG files: ' + str(src))
        width, height = struct.unpack('>II', raw[16:24])
        max_width = 16.2 / 2.54 * 914400
        max_height = 11.0 / 2.54 * 914400
        factor = min(max_width / width, max_height / height)
        cx, cy = int(width * factor), int(height * factor)
        idx = self.figure_count + 1
        media_name = f'figure{idx}.png'
        rid = f'rIdImage{idx}'
        self.media[media_name] = raw
        self.rels.append((rid, 'image', 'media/' + media_name, None))
        p = self.paragraph('', align='center', first_line=0, before=150,
                           after=60, keep_next=True)
        drawing = sub(sub(p, 'w:r'), 'w:drawing')
        inline = sub(drawing, 'wp:inline', {'distT': 0, 'distB': 0, 'distL': 0, 'distR': 0})
        sub(inline, 'wp:extent', {'cx': cx, 'cy': cy})
        sub(inline, 'wp:effectExtent', {'l': 0, 't': 0, 'r': 0, 'b': 0})
        sub(inline, 'wp:docPr', {'id': idx, 'name': f'图{idx}', 'descr': caption})
        prop = sub(inline, 'wp:cNvGraphicFramePr')
        sub(prop, 'a:graphicFrameLocks', {'noChangeAspect': 1})
        graphic = sub(inline, 'a:graphic')
        gd = sub(graphic, 'a:graphicData', {'uri': NS['pic']})
        pic = sub(gd, 'pic:pic')
        nv = sub(pic, 'pic:nvPicPr')
        sub(nv, 'pic:cNvPr', {'id': 0, 'name': media_name})
        sub(nv, 'pic:cNvPicPr')
        fill = sub(pic, 'pic:blipFill')
        sub(fill, 'a:blip', {'r:embed': rid})
        sub(sub(fill, 'a:stretch'), 'a:fillRect')
        sp = sub(pic, 'pic:spPr')
        xf = sub(sp, 'a:xfrm')
        sub(xf, 'a:off', {'x': 0, 'y': 0})
        sub(xf, 'a:ext', {'cx': cx, 'cy': cy})
        sub(sub(sp, 'a:prstGeom', {'prst': 'rect'}), 'a:avLst')
        self.paragraph(caption, style='Caption', align='both', size=19,
                       after=130, first_line=0, keep_lines=True)
        self.figure_count += 1

    def table(self, caption, headers, rows):
        self.paragraph(caption, style='Caption', size=20, bold=True,
                       align='left', before=140, after=70, first_line=0, keep_next=True)
        count = len(headers)
        if any(len(row) != count for row in rows):
            raise ValueError('Inconsistent table columns')
        if count == 2:
            widths = [round(TEXT_W * .29), TEXT_W - round(TEXT_W * .29)]
        elif count == 3:
            a = round(TEXT_W * .44)
            b = (TEXT_W - a) // 2
            widths = [a, b, TEXT_W - a - b]
        else:
            widths = [TEXT_W // count] * count
            widths[-1] += TEXT_W - sum(widths)
        tbl = sub(self.body, 'w:tbl')
        prop = sub(tbl, 'w:tblPr')
        sub(prop, 'w:tblW', {'w:w': TEXT_W, 'w:type': 'dxa'})
        sub(prop, 'w:jc', {'w:val': 'center'})
        borders = sub(prop, 'w:tblBorders')
        for tag in ['top', 'bottom']:
            sub(borders, 'w:' + tag, {'w:val': 'single', 'w:sz': 10, 'w:color': BLUE})
        for tag in ['left', 'right', 'insideV', 'insideH']:
            sub(borders, 'w:' + tag, {'w:val': 'nil'})
        sub(prop, 'w:tblLayout', {'w:type': 'fixed'})
        margins = sub(prop, 'w:tblCellMar')
        for tag in ['top', 'bottom']:
            sub(margins, 'w:' + tag, {'w:w': 65, 'w:type': 'dxa'})
        for tag in ['left', 'right']:
            sub(margins, 'w:' + tag, {'w:w': 80, 'w:type': 'dxa'})
        grid = sub(tbl, 'w:tblGrid')
        for width in widths:
            sub(grid, 'w:gridCol', {'w:w': width})
        for ri, row in enumerate([headers] + rows):
            tr = sub(tbl, 'w:tr')
            rp = sub(tr, 'w:trPr')
            sub(rp, 'w:cantSplit')
            if ri == 0:
                sub(rp, 'w:tblHeader')
            for ci, (value, width) in enumerate(zip(row, widths)):
                cell = sub(tr, 'w:tc')
                cp = sub(cell, 'w:tcPr')
                sub(cp, 'w:tcW', {'w:w': width, 'w:type': 'dxa'})
                sub(cp, 'w:vAlign', {'w:val': 'center'})
                if ri == 0:
                    sub(cp, 'w:shd', {'w:fill': 'EDF3F7', 'w:val': 'clear'})
                    cb = sub(cp, 'w:tcBorders')
                    sub(cb, 'w:bottom', {'w:val': 'single', 'w:sz': 5, 'w:color': BLUE})
                self.paragraph(str(value), parent=cell, style='TableText',
                               align='left' if ci == 0 or count == 2 else 'center',
                               size=20, bold=ri == 0, before=0, after=0,
                               first_line=0, keep_lines=True)
        self.paragraph('', size=8, after=40, first_line=0)
        self.table_count += 1

    def build(self):
        c = self.content
        self.paragraph(c['title'], style='Title', align='center', size=36,
                       bold=True, color=BLUE, before=0, after=130, first_line=0,
                       keep_next=True, keep_lines=True)
        if c.get('title_en'):
            self.paragraph(c['title_en'], style='Subtitle', align='center', size=23,
                           color=BLUE, after=180, first_line=0, keep_next=True)
        for field in ['author', 'affiliation']:
            if c.get(field):
                self.paragraph(c[field], align='center', size=20, after=70,
                               first_line=0, keep_next=True)
        self.paragraph('摘 要', style='Heading2', bold=True, align='left',
                       before=130, after=70, first_line=0, keep_next=True)
        self.paragraph(c['abstract'], first_line=0, size=21, after=90)
        keywords = c.get('keywords', '')
        if isinstance(keywords, list):
            keywords = '；'.join(keywords)
        self.paragraph('关键词：' + keywords, size=20, after=170, first_line=0)
        for block in c['blocks']:
            kind = block['type']
            if kind == 'heading':
                self.heading(block['text'], block['level'])
            elif kind == 'p':
                self.paragraph(block['text'])
            elif kind == 'equation':
                self.equation(block['key'], block.get('number', ''))
            elif kind == 'figure':
                self.figure(block['image'], block['caption'])
            elif kind == 'table':
                self.table(block['caption'], block['headers'], block['rows'])
            else:
                raise ValueError(f'Unknown block type: {kind}')
        self.heading('参考文献', 1)
        for ref in sorted(c['references'], key=lambda r: int(r['number'])):
            p = self.paragraph(f"[{ref['number']}] {ref['text']}", style='Reference',
                               size=18, first_line=0, after=90, keep_lines=True)
            prop = p.find(q('w:pPr'))
            ind = prop.find(q('w:ind'))
            ind.attrib.clear()
            ind.set(q('w:left'), '400')
            ind.set(q('w:hanging'), '400')
            if ref.get('url') and ref['url'] not in ref['text']:
                rid = f"rIdRef{ref['number']}"
                self.rels.append((rid, 'hyperlink', ref['url'], 'External'))
                link = sub(p, 'w:hyperlink', {'r:id': rid})
                # Use the URL as actual text to preserve exact bibliographic access.
                link.append(text_run(' ' + ref['url'], size=18, color=BLUE))
        if set(self.refs) != self.used_refs:
            raise ValueError('Uncited bibliography entries: ' + str(sorted(set(self.refs) - self.used_refs)))
        sec = sub(self.body, 'w:sectPr')
        sub(sec, 'w:headerReference', {'w:type': 'default', 'r:id': 'rIdHeader'})
        sub(sec, 'w:footerReference', {'w:type': 'default', 'r:id': 'rIdFooter'})
        sub(sec, 'w:pgSz', {'w:w': PAGE_W, 'w:h': PAGE_H})
        sub(sec, 'w:pgMar', {'w:top': MARGIN, 'w:right': MARGIN, 'w:bottom': MARGIN,
                            'w:left': MARGIN, 'w:header': 567, 'w:footer': 567,
                            'w:gutter': 0})
        sub(sec, 'w:cols', {'w:space': 720})
        return self

    def header(self):
        node = element('w:hdr')
        p = self.paragraph('SpecPrune · 函数剪枝与可靠性评测', parent=node,
                           align='right', size=17, color='52677A', after=40, first_line=0)
        borders = sub(p.find(q('w:pPr')), 'w:pBdr')
        sub(borders, 'w:bottom', {'w:val': 'single', 'w:sz': 4, 'w:space': 5, 'w:color': 'CBD5DE'})
        return node

    def footer(self):
        node = element('w:ftr')
        p = self.paragraph('— ', parent=node, align='center', size=18, first_line=0, after=0)
        field = sub(p, 'w:fldSimple', {'w:instr': 'PAGE'})
        field.append(text_run('1', size=18))
        p.append(text_run(' —', size=18))
        return node

    def styles(self):
        root = element('w:styles')
        defaults = sub(root, 'w:docDefaults')
        sub(defaults, 'w:rPrDefault').append(rpr())
        sub(defaults, 'w:pPrDefault').append(p_properties())
        for sid, name, size, bold, color in [
            ('Normal', 'Normal', 22, False, TEXT),
            ('Title', 'Title', 36, True, BLUE),
            ('Subtitle', 'Subtitle', 23, False, BLUE),
            ('Heading1', 'heading 1', 28, True, BLUE),
            ('Heading2', 'heading 2', 24, True, BLUE),
            ('Caption', 'Caption', 19, False, TEXT),
            ('Equation', 'Equation', 22, False, TEXT),
            ('TableText', 'Table Text', 20, False, TEXT),
            ('Reference', 'Reference', 18, False, TEXT),
        ]:
            s = sub(root, 'w:style', {'w:type': 'paragraph', 'w:styleId': sid,
                                     **({'w:default': '1'} if sid == 'Normal' else {})})
            sub(s, 'w:name', {'w:val': name})
            if sid != 'Normal':
                sub(s, 'w:basedOn', {'w:val': 'Normal'})
            sub(s, 'w:qFormat')
            if sid.startswith('Heading'):
                prop = sub(s, 'w:pPr')
                sub(prop, 'w:outlineLvl', {'w:val': int(sid[-1])-1})
                sub(prop, 'w:keepNext')
            s.append(rpr(size, bold, color))
        return root

    def save(self, path):
        rootrels = ET.Element('Relationships', {'xmlns': PKG})
        for rid, typ, target in [
            ('rId1', 'officeDocument', 'word/document.xml'),
            ('rId2', 'metadata/core-properties', 'docProps/core.xml'),
            ('rId3', 'extended-properties', 'docProps/app.xml'),
        ]:
            prefix = 'http://schemas.openxmlformats.org/package/2006/relationships/' if typ == 'metadata/core-properties' else NS['r'] + '/'
            ET.SubElement(rootrels, 'Relationship', {'Id': rid, 'Type': prefix + typ, 'Target': target})
        rels = ET.Element('Relationships', {'xmlns': PKG})
        for rid, typ, target, mode in self.rels:
            attrs = {'Id': rid, 'Type': NS['r'] + '/' + typ, 'Target': target}
            if mode:
                attrs['TargetMode'] = mode
            ET.SubElement(rels, 'Relationship', attrs)
        settings = element('w:settings')
        sub(settings, 'w:zoom', {'w:percent': 100})
        sub(settings, 'w:defaultTabStop', {'w:val': 420})
        sub(settings, 'w:updateFields', {'w:val': 'true'})
        compat = sub(settings, 'w:compat')
        sub(compat, 'w:compatSetting', {'w:name': 'compatibilityMode',
            'w:uri': 'http://schemas.microsoft.com/office/word', 'w:val': 15})
        mathpr = sub(settings, 'm:mathPr')
        sub(mathpr, 'm:mathFont', {'m:val': 'Cambria Math'})
        fonts = element('w:fonts')
        for name in [FONT_CN, FONT_WEST, 'Cambria Math']:
            sub(fonts, 'w:font', {'w:name': name})
        core = element('cp:coreProperties')
        sub(core, 'dc:title', text=self.content['title'])
        sub(core, 'dc:subject', text='中文全文翻译；17篇参考文献；作者审阅稿')
        sub(core, 'dc:creator', text=self.content.get('author', '作者待填写'))
        sub(core, 'cp:keywords', text='代码定位智能体;可靠性;函数剪枝;SpecPrune')
        sub(core, 'dcterms:created', {'xsi:type': 'dcterms:W3CDTF'},
            datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'))
        app = ET.Element('Properties', {'xmlns': 'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'})
        ET.SubElement(app, 'Application').text = 'Reproducible stdlib OOXML paper builder'
        content = ET.Element('Types', {'xmlns': CONTENT})
        for ext, mime in [('rels', 'application/vnd.openxmlformats-package.relationships+xml'),
                          ('xml', 'application/xml'), ('png', 'image/png')]:
            ET.SubElement(content, 'Default', {'Extension': ext, 'ContentType': mime})
        mime_base = 'application/vnd.openxmlformats-officedocument.wordprocessingml.'
        for name, typ in [('document', 'document.main'), ('styles', 'styles'), ('settings', 'settings'),
                          ('fontTable', 'fontTable'), ('header1', 'header'), ('footer1', 'footer')]:
            ET.SubElement(content, 'Override', {'PartName': '/word/' + name + '.xml', 'ContentType': mime_base + typ + '+xml'})
        ET.SubElement(content, 'Override', {'PartName': '/docProps/core.xml', 'ContentType': 'application/vnd.openxmlformats-package.core-properties+xml'})
        ET.SubElement(content, 'Override', {'PartName': '/docProps/app.xml', 'ContentType': 'application/vnd.openxmlformats-officedocument.extended-properties+xml'})
        parts = {
            '[Content_Types].xml': xml_bytes(content),
            '_rels/.rels': xml_bytes(rootrels),
            'word/document.xml': xml_bytes(self.doc),
            'word/styles.xml': xml_bytes(self.styles()),
            'word/settings.xml': xml_bytes(settings),
            'word/fontTable.xml': xml_bytes(fonts),
            'word/header1.xml': xml_bytes(self.header()),
            'word/footer1.xml': xml_bytes(self.footer()),
            'word/_rels/document.xml.rels': xml_bytes(rels),
            'docProps/core.xml': xml_bytes(core),
            'docProps/app.xml': xml_bytes(app),
        }
        parts.update({'word/media/' + name: raw for name, raw in self.media.items()})
        # Validate all XML and ZIP relationships before delivering the container.
        for name, raw in parts.items():
            if name.endswith('.xml') or name.endswith('.rels'):
                ET.fromstring(raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, raw in parts.items():
                archive.writestr(name, raw)
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            doc = ET.fromstring(archive.read('word/document.xml'))
            assert len(doc.findall('.//m:oMath', NS)) >= self.equation_count
            assert len(doc.findall('.//w:drawing', NS)) == self.figure_count
        return {'output': str(path), 'references': len(self.refs),
                'cited_references': len(self.used_refs), 'figures': self.figure_count,
                'tables': self.table_count, 'equation_groups': self.equation_count,
                'math_objects': len(doc.findall('.//m:oMath', NS)),
                'bytes': path.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'chinese_manuscript.json')
    parser.add_argument('--output', type=Path, default=ROOT / '论文_中文版_17篇参考文献.docx')
    parser.add_argument('--allow-reference-count', type=int, default=17,
                        help='Expected bibliography length, primarily useful for isolated smoke tests')
    args = parser.parse_args()
    content = json.loads(args.input.read_text(encoding='utf8'))
    refs = content['references']
    assert len(refs) == args.allow_reference_count
    assert len({x['key'] for x in refs}) == len(refs)
    assert sorted(int(x['number']) for x in refs) == list(range(1, len(refs) + 1))
    builder = WordBuilder(content, args.input.resolve().parent).build()
    receipt = builder.save(args.output.resolve())
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
