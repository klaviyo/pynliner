#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import pynliner
import logging
import cssutils
import mock
import six

try:
    from StringIO import StringIO  # for Python 2
except ImportError:
    from io import StringIO  # for Python 3

from bs4 import BeautifulSoup
from pynliner import Pynliner


class BaseTestCase(unittest.TestCase):
    def assert_equal_body(self, output, expected):
        body_output = BeautifulSoup(output, 'lxml').select_one('body')
        body_expected = BeautifulSoup(expected, 'lxml').select_one('body')
        if not body_output == body_expected:
            # display results
            self.assertEqual(body_expected.prettify(), body_output.prettify())

    def assert_equal_style(self, output, expected):
        style_output = BeautifulSoup(output, 'lxml').select_one('style')
        style_expected = BeautifulSoup(expected, 'lxml').select_one('style')
        if not style_output == style_expected:
            # display results
            self.assertEqual(style_output.prettify(), style_expected.prettify())


class Basic(BaseTestCase):

    def setUp(self):
        self.html = "<style>h1 { color: #ffcc00; }</style><h1>Hello World!</h1>"
        self.p = Pynliner().from_string(self.html)

    def test_fromString(self):
        """Test 'fromString' constructor"""
        self.assertEqual(self.p.source_string, self.html)

    def test_get_sohtmlup(self):
        """Test '_get_soup' method"""
        self.p._get_soup()
        self.assert_equal_style(six.text_type(self.p.soup), self.html)

    def test_get_styles(self):
        """Test '_get_styles' method"""
        self.p._get_soup()
        self.p._get_styles()
        self.assertEqual(self.p.style_string, u'h1 { color: #ffcc00; }\n')
        self.assert_equal_body(six.text_type(self.p.soup), u'<h1>Hello World!</h1>')

    def test_apply_styles(self):
        """Test '_apply_styles' method"""
        self.p._get_soup()
        self.p._get_styles()
        self.p._apply_styles()
        attr_dict = dict(self.p.soup.select('h1')[0].attrs)
        self.assertIn('style', attr_dict)
        self.assertEqual(attr_dict['style'], u'color: #fc0')

    def test_run(self):
        """Test 'run' method"""
        output = self.p.run()
        self.assert_equal_body(output, u'<h1 style="color:#fc0">Hello World!</h1>')

    def test_with_cssString(self):
        """Test 'with_cssString' method"""
        cssString = 'h1 {color: #f00;}'
        self.p.with_cssString(cssString)
        output = self.p.run()
        self.assert_equal_body(output, u'<h1 style="color:#f00">Hello World!</h1>')

    def test_fromString_complete(self):
        """Test 'fromString' complete"""
        output = pynliner.fromString(self.html)
        desired = u'<h1 style="color:#fc0">Hello World!</h1>'
        self.assert_equal_body(output, desired)

    def test_fromURL(self):
        """Test 'fromURL' constructor"""
        url = 'http://media.tannern.com/pynliner/test.html'
        p = Pynliner()
        with mock.patch.object(Pynliner, '_get_url') as mocked:
            mocked.return_value = u"""<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>test</title>
<link rel="stylesheet" type="text/css" href="test.css"/>
<style type="text/css">h1 {color: #fc0;}</style>
</head>
<body>
<h1>Hello World!</h1>
<p>:)</p>
</body>
</html>"""
            p.from_url(url)
        self.assertEqual(p.root_url, 'http://media.tannern.com')
        self.assertEqual(p.relative_url, 'http://media.tannern.com/pynliner/')

        p._get_soup()

        with mock.patch.object(Pynliner, '_get_url') as mocked:
            mocked.return_value = 'p {color: #999}'
            p._get_external_styles()
        self.assertEqual(p.style_string, "p {color: #999}")

        p._get_internal_styles()
        self.assertEqual(p.style_string, "p {color: #999}\nh1 {color: #fc0;}\n")

        p._get_styles()

        output = p.run()
        desired = u"""<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>test</title>


</head>
<body>
<h1 style="color:#fc0">Hello World!</h1>
<p style="color:#999">:)</p>
</body>
</html>"""
        self.assert_equal_body(output, desired)

    def test_overloaded_styles(self):
        html = '<style>h1 { color: red; } #test { color: blue; }</style>' \
               '<h1 id="test">Hello world!</h1>'
        expected = '<h1 id="test" style="color:blue">Hello world!</h1>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(expected, output)

    def test_unicode_content(self):
        html = u"""<h1>Hello World!</h1><p>\u2022 point</p>"""
        css = """h1 { color: red; }"""
        expected = u"""<h1 style="color:red">Hello World!</h1><p>\u2022 point</p>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_conditional_comments(self):
        html = "<!-- <normal> --><!--[if condition]><p>special</p><![endif]-->"
        expected = "<!-- <normal> --><!--[if condition]><p>special</p><![endif]-->"
        output = Pynliner(allow_conditional_comments=True).from_string(html).run()
        self.assertEqual(output, expected)

    def test_multiline_conditional_comments(self):
        html = """<!--[if condition]>
    <p>special</p>
<![endif]-->"""
        expected = """<!--[if condition]>
    <p>special</p>
<![endif]-->"""
        output = Pynliner(allow_conditional_comments=True).from_string(html).run()
        self.assertEqual(output, expected)


class ExternalStyles(BaseTestCase):
    def setUp(self):
        self.html_template = """<link rel="stylesheet" href="{href}"></link><span class="b1">Bold</span><span class="b2 c">Bold Red</span>"""
        self.root_url = 'http://server.com'
        self.relative_url = 'http://server.com/parent/child/'

    def _test_external_url(self, url, expected_url):
        with mock.patch.object(Pynliner, '_get_url') as mocked:
            def check_url(url):
                self.assertEqual(url, expected_url)
                return ".b1,.b2 { font-weight:bold; } .c {color: red}"
            mocked.side_effect = check_url
            p = Pynliner()
            p.root_url = self.root_url
            p.relative_url = self.relative_url
            p.from_string(self.html_template.format(href=url))
            p._get_soup()
            p._get_styles()

    def test_simple_url(self):
        self._test_external_url('test.css', 'http://server.com/parent/child/test.css')

    def test_relative_url(self):
        self._test_external_url('../test.css', 'http://server.com/parent/test.css')

    def test_absolute_url(self):
        self._test_external_url('/something/test.css', 'http://server.com/something/test.css')

    def test_external_url(self):
        self._test_external_url('http://other.com/something/test.css', 'http://other.com/something/test.css')

    def test_external_ssl_url(self):
        self._test_external_url('https://other.com/something/test.css', 'https://other.com/something/test.css')

    def test_external_schemeless_url(self):
        self._test_external_url('//other.com/something/test.css', 'http://other.com/something/test.css')

    def test_duplicate_elements(self):
        html = '<style>div { color: black }</style><div></div><div></div>'
        desired_output = '<div style="color:black"></div><div style="color:black"></div>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(desired_output, output)

    def test_duplicate_elements_with_uniqe_props(self):
        html = '<style>div { color: black }</style><div id="d1"></div><div id="d2"></div>'
        desired_output = '<div id="d1" style="color:black"></div><div id="d2" style="color:black"></div>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(desired_output, output)

    def test_with_special_characters(self):
        html = '<style>div { color: black }</style><div>&gt;&gt;&gt;&gt;</div><div></div>'
        desired_output = '<div style="color:black">&gt;&gt;&gt;&gt;</div><div style="color:black"></div>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(desired_output, output)

    def test_nested_illegal_elements(self):
        html = '<style>p { color: black }</style><p><p></p></p>'
        desired_output = '<p style="color:black"></p><p style="color:black"></p>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(desired_output, output)


class CommaSelector(BaseTestCase):
    def setUp(self):
        self.html = """<style>.b1,.b2 { font-weight:bold; } .c {color: red}</style><span class="b1">Bold</span><span class="b2 c">Bold Red</span>"""
        self.p = Pynliner().from_string(self.html)

    def test_fromString(self):
        """Test 'fromString' constructor"""
        self.assertEqual(self.p.source_string, self.html)

    def test_get_soup(self):
        """Test '_get_soup' method"""
        self.p._get_soup()
        self.assert_equal_body(six.text_type(self.p.soup), self.html)

    def test_get_styles(self):
        """Test '_get_styles' method"""
        self.p._get_soup()
        self.p._get_styles()
        self.assertEqual(self.p.style_string, u'.b1,.b2 { font-weight:bold; } .c {color: red}\n')
        self.assert_equal_body(six.text_type(self.p.soup), u'<span class="b1">Bold</span><span class="b2 c">Bold Red</span>')

    def test_apply_styles(self):
        """Test '_apply_styles' method"""
        self.p._get_soup()
        self.p._get_styles()
        self.p._apply_styles()
        self.assert_equal_body(six.text_type(self.p.soup), u'<span class="b1" style="font-weight: bold">Bold</span><span class="b2 c" style="color: red;font-weight: bold">Bold Red</span>')

    def test_run(self):
        """Test 'run' method"""
        output = self.p.run()
        self.assert_equal_body(output, u'<span class="b1" style="font-weight:bold">Bold</span><span class="b2 c" style="color:red;font-weight:bold">Bold Red</span>')

    def test_with_cssString(self):
        """Test 'with_cssString' method"""
        cssString = '.b1,.b2 {font-size: 2em;}'
        self.p = Pynliner().from_string(self.html).with_cssString(cssString)
        output = self.p.run()
        self.assert_equal_body(output, u'<span class="b1" style="font-weight:bold;font-size:2em">Bold</span><span class="b2 c" style="color:red;font-weight:bold;font-size:2em">Bold Red</span>')

    def test_fromString_complete(self):
        """Test 'fromString' complete"""
        output = pynliner.fromString(self.html)
        desired = u'<span class="b1" style="font-weight:bold">Bold</span><span class="b2 c" style="color:red;font-weight:bold">Bold Red</span>'
        self.assert_equal_body(output, desired)

    def test_comma_whitespace(self):
        """Test excess whitespace in CSS"""
        html = '<style>h1,  h2   ,h3,\nh4{   color:    #000}  </style><h1>1</h1><h2>2</h2><h3>3</h3><h4>4</h4>'
        desired_output = '<h1 style="color:#000">1</h1><h2 style="color:#000">2</h2><h3 style="color:#000">3</h3><h4 style="color:#000">4</h4>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(output, desired_output)


class Extended(BaseTestCase):
    def test_overwrite(self):
        """Test overwrite inline styles"""
        html = '<style>h1 {color: #000;}</style><h1 style="color: #fff">Foo</h1>'
        desired_output = '<h1 style="color:#000;color: #fff">Foo</h1>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(output, desired_output)

    def test_overwrite_comma(self):
        """Test overwrite inline styles"""
        html = '<style>h1,h2,h3 {color: #000;}</style><h1 style="color: #fff">Foo</h1><h3 style="color: #fff">Foo</h3>'
        desired_output = '<h1 style="color:#000;color: #fff">Foo</h1><h3 style="color:#000;color: #fff">Foo</h3>'
        output = Pynliner().from_string(html).run()
        self.assert_equal_body(output, desired_output)


class LogOptions(BaseTestCase):
    def setUp(self):
        self.html = "<style>h1 { color:#ffcc00; }</style><h1>Hello World!</h1>"

    def test_no_log(self):
        self.p = Pynliner()
        self.assertEqual(self.p.log, None)
        self.assertEqual(cssutils.log.enabled, False)

    def test_custom_log(self):
        self.log = logging.getLogger('testlog')
        self.log.setLevel(logging.DEBUG)

        self.logstream = StringIO()
        handler = logging.StreamHandler(self.logstream)
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatter = logging.Formatter(log_format)
        handler.setFormatter(formatter)
        self.log.addHandler(handler)

        self.p = Pynliner(self.log).from_string(self.html)

        self.p.run()
        log_contents = self.logstream.getvalue()
        self.assertIn("DEBUG", log_contents)


class BeautifulSoupBugs(BaseTestCase):
    def test_double_doctype(self):
        self.html = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">"""
        output = pynliner.fromString(self.html)
        self.assertNotIn("<!<!", output)

    def test_double_comment(self):
        self.html = """<!-- comment -->"""
        output = pynliner.fromString(self.html)
        self.assertNotIn("<!--<!--", output)


class ComplexSelectors(BaseTestCase):
    def test_multiple_class_selector(self):
        html = """<section class="a b">Hello World!</section>"""
        css = """section.a.b { color: red; }"""
        expected = u'<section class="a b" style="color:red">Hello World!</section>'
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_combination_selector(self):
        html = """<section id="a" class="b">Hello World!</section>"""
        css = """section#a.b { color: red; }"""
        expected = u'<section class="b" id="a" style="color:red">Hello World!</section>'
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_descendant_selector(self):
        html = """<section><span>Hello World!</span></section>"""
        css = """section span { color: red; }"""
        expected = u'<section><span style="color:red">Hello World!</span></section>'
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_selector(self):
        html = """<section><span>Hello World!</span></section>"""
        css = """section > span { color: red; }"""
        expected = u'<section><span style="color:red">Hello World!</span></section>'
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_nested_child_selector(self):
        html = """<div><section><span>Hello World!</span></section></div>"""
        css = """div > section > span { color: red; }"""
        expected = u"""<div><section><span style="color:red">Hello World!</span></section></div>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_selector_complex_dom(self):
        html = """<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > span { color: red; }"""
        expected = u"""<section><span style="color:red">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_all_selector_complex_dom(self):
        html = """<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > * { color: red; }"""
        expected = u"""<section><span style="color:red">Hello World!</span><p style="color:red">foo</p><div class="barclass" style="color:red"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_adjacent_selector(self):
        html = """<section>Hello World!</section><h2>How are you?</h2>"""
        css = """section + h2 { color: red; }"""
        expected = (u'<section>Hello World!</section>'
                    u'<h2 style="color:red">How are you?</h2>')
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_unknown_pseudo_selector(self):
        html = """<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > span:css4-selector { color: red; }"""
        expected = u"""<section><span style="color:red">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_follow_by_adjacent_selector_complex_dom(self):
        html = """<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > span + p { color: red; }"""
        expected = u"""<section><span>Hello World!</span><p style="color:red">foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_follow_by_first_child_selector_with_white_spaces(self):
        html = """<section> <span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > :first-child { color: red; }"""
        expected = u"""<section> <span style="color:red">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_follow_by_first_child_selector_with_comments(self):
        html = """<section> <!-- enough said --><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > :first-child { color: red; }"""
        expected = u"""<section> <!-- enough said --><span style="color:red">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_follow_by_first_child_selector_complex_dom(self):
        html = """<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > :first-child { color: red; }"""
        expected = u"""<section><span style="color:red">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_last_child_selector(self):
        html = """<section><span>Hello World!</span></section>"""
        css = """section > :last-child { color: red; }"""
        expected = u"""<section><span style="color:red">Hello World!</span></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_multiple_pseudo_selectors(self):
        html = """<section><span>Hello World!</span></section>"""
        css = """span:first-child:last-child { color: red; }"""
        expected = u"""<section><span style="color:red">Hello World!</span></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)
        html = """<section><span>Hello World!</span><span>again!</span></section>"""
        css = """span:first-child:last-child { color: red; }"""
        expected = u"""<section><span>Hello World!</span><span>again!</span></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_parent_pseudo_selector(self):
        html = """<section><span><span>Hello World!</span></span></section>"""
        css = """span:last-child span { color: red; }"""
        expected = u"""<section><span><span style="color:red">Hello World!</span></span></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)
        html = """<section><span><span>Hello World!</span></span></section>"""
        css = """span:last-child > span { color: red; }"""
        expected = u"""<section><span><span style="color:red">Hello World!</span></span></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)
        html = """<section><span><span>Hello World!</span></span><span>nope</span></section>"""
        css = """span:last-child > span { color: red; }"""
        expected = u"""<section><span><span>Hello World!</span></span><span>nope</span></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_follow_by_last_child_selector_complex_dom(self):
        html = """<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > :last-child { color: red; }"""
        expected = u"""<section><span>Hello World!</span><p>foo</p><div class="barclass" style="color:red"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_with_first_child_override_selector_complex_dom(self):
        html = """<div><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></div>"""
        css = """div > * { color: green; } div > :first-child { color:red; }"""
        expected = u"""<div><span style="color:red">Hello World!</span><p style="color:green">foo</p><div class="barclass" style="color:green"><span style="color:red">baz</span>bar</div></div>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_id_el_child_with_first_child_override_selector_complex_dom(self):
        html = """<div id="abc"><span class="cde">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></div>"""
        css = """#abc > * { color: green; } #abc > :first-child { color: red; }"""
        expected = u"""<div id="abc"><span class="cde" style="color:red">Hello World!</span><p style="color:green">foo</p><div class="barclass" style="color:green"><span>baz</span>bar</div></div>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_with_first_and_last_child_override_selector(self):
        html = """<p><span>Hello World!</span></p>"""
        css = """p > * { color: green; } p > :first-child:last-child { color: red; }"""
        expected = u"""<p><span style="color:red">Hello World!</span></p>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_nested_child_with_first_child_override_selector_complex_dom(self):
        self.maxDiff = None

        html = """<div><div><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></div></div>"""
        css = """div > div > * { color: green; } div > div > :first-child { color: red; }"""
        expected = u"""<div><div><span style="color:red">Hello World!</span><p style="color:green">foo</p><div class="barclass" style="color:green"><span style="color:red">baz</span>bar</div></div></div>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_with_first_child_and_class_selector_complex_dom(self):
        html = """<section><span class="hello">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > .hello:first-child { color: green; }"""
        expected = u"""<section><span class="hello" style="color:green">Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_child_with_first_child_and_unmatched_class_selector_complex_dom(self):
        html = """<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section > .hello:first-child { color: green; }"""
        expected = u"""<section><span>Hello World!</span><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_first_child_descendant_selector(self):
        html = """<section><div><span>Hello World!</span></div></section>"""
        css = """section :first-child { color: red; }"""
        expected = u"""<section><div style="color:red"><span style="color:red">Hello World!</span></div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_last_child_descendant_selector(self):
        html = """<section><div><span>Hello World!</span></div></section>"""
        css = """section :last-child { color: red; }"""
        expected = u"""<section><div style="color:red"><span style="color:red">Hello World!</span></div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_first_child_descendant_selector_complex_dom(self):
        html = """<section><div><span>Hello World!</span></div><p>foo</p><div class="barclass"><span>baz</span>bar</div></section>"""
        css = """section :first-child { color: red; }"""
        expected = u"""<section><div style="color:red"><span style="color:red">Hello World!</span></div><p>foo</p><div class="barclass"><span style="color:red">baz</span>bar</div></section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_attribute_selector_match(self):
        html = """<section title="foo">Hello World!</section>"""
        css = """section[title="foo"] { color: red; }"""
        expected = u'<section style="color:red" title="foo">Hello World!</section>'
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)

    def test_attribute_selector_no_match(self):
        html = """<section title="bar">Hello World!</section>"""
        css = """section[title="foo"] { color: red; }"""
        expected = u"""<section title="bar">Hello World!</section>"""
        output = Pynliner().from_string(html).with_cssString(css).run()
        self.assert_equal_body(output, expected)


class MediaQueries(BaseTestCase):

    def test_media_queries_left_alone(self):
        html = """<html><head><title>Example</title>
<style type="text/css">
@media screen and (min-device-width: 480) { #content { width: 480px; } }
#content { border: 1px solid black; }
</style></head><body><div id="content"><h1>Hello world</h1></div></body></html>"""
        output = Pynliner(preserve_media_queries=True).from_string(html).run()

        self.assertEqual(output, """<html><head><title>Example</title>
<style type="text/css">
@media screen and (min-device-width: 480) {
    #content {
        width: 480px
        }
    }
</style></head><body><div id="content" style="border:1px solid black"><h1>Hello world</h1></div></body></html>""")

    def test_media_queries_stripped(self):
        html = """<html><head><title>Example</title>
<style type="text/css">
@media screen and (min-device-width: 480) { #content { width: 480px; } }
#content { border: 1px solid black; }
</style></head><body><div id="content"><h1>Hello world</h1></div></body></html>"""
        output = Pynliner().from_string(html).run()

        self.assertEqual(output, """<html><head><title>Example</title>
</head><body><div id="content" style="border:1px solid black"><h1>Hello world</h1></div></body></html>""")

    def test_one_removed_one_stays(self):
        html = """<html><head><title>Example</title>
<style type="text/css">
@media screen and (min-device-width: 480) { #content { width: 480px; } }
#content { border: 1px solid black; }
</style>
<style type="text/css">
#content { color: blue; }
</style></head><body><div id="content"><h1>Hello world</h1></div></body></html>"""
        output = Pynliner(preserve_media_queries=True).from_string(html).run()

        self.assertEqual(output, """<html><head><title>Example</title>
<style type="text/css">
@media screen and (min-device-width: 480) {
    #content {
        width: 480px
        }
    }
</style>
</head><body><div id="content" style="border:1px solid black;color:blue"><h1>Hello world</h1></div></body></html>""")


if __name__ == '__main__':
    unittest.main()
