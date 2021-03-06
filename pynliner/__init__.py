#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pynliner : Convert CSS to inline styles

Python CSS-to-inline-styles conversion tool for HTML using BeautifulSoup and
cssutils

Copyright (c) 2011-2013 Tanner Netterville

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

The generated output of this software shall not be used in a mass marketing
service.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR 
THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""

__version__ = "0.5.1.12"

import re
import urlparse
import urllib2
import cssutils
from BeautifulSoup import BeautifulSoup, Tag, Comment
from soupselect import select, SelectorNotSupportedException

_CSS_RULE_TYPES_TO_PRESERVE = (
    cssutils.css.CSSRule.MEDIA_RULE,
    cssutils.css.CSSRule.IMPORT_RULE,
    cssutils.css.CSSRule.FONT_FACE_RULE,
)

class Pynliner(object):
    """Pynliner class"""

    soup = False
    style_string = False
    stylesheet = False
    output = False

    def __init__(self, log=None,
        allow_conditional_comments=False,
        preserve_media_queries=False,
        preserve_unknown_rules=False,
        ingore_unsupported_selectors=False):

        self.log = log
        cssutils.log.enabled = False if log is None else True
        self.extra_style_strings = []
        self.allow_conditional_comments = allow_conditional_comments
        self.preserve_media_queries = preserve_media_queries
        self.preserve_unknown_rules = preserve_unknown_rules
        self.ingore_unsupported_selectors = ingore_unsupported_selectors

        self.root_url = None
        self.relative_url = None

    def from_url(self, url):
        """Gets remote HTML page for conversion

        Downloads HTML page from `url` as a string and passes it to the
        `from_string` method. Also sets `self.root_url` and `self.relative_url`
        for use in importing <link> elements.

        Returns self.

        >>> p = Pynliner()
        >>> p.from_url('http://somewebsite.com/file.html')
        <Pynliner object at 0x26ac70>
        """
        self.url = url
        self.relative_url = '/'.join(url.split('/')[:-1]) + '/'
        self.root_url = '/'.join(url.split('/')[:3])
        self.source_string = self._get_url(self.url)
        return self

    def from_string(self, string):
        """Generates a Pynliner object from the given HTML string.

        Returns self.

        >>> p = Pynliner()
        >>> p.from_string('<style>h1 {color:#ffcc00;}</style><h1>Hi</h1>')
        <Pynliner object at 0x26ac70>
        """
        self.source_string = string
        return self

    def with_cssString(self, css_string):
        """Adds external CSS to the Pynliner object. Can be "chained".

        Returns self.

        >>> html = "<h1>Hello World!</h1>"
        >>> css = "h1 { color:#ffcc00; }"
        >>> p = Pynliner()
        >>> p.from_string(html).with_cssString(css)
        <pynliner.Pynliner object at 0x2ca810>
        """
        self.extra_style_strings.append(css_string)
        return self

    def run(self):
        """Applies each step of the process if they have not already been
        performed.

        Returns Unicode output with applied styles.

        >>> html = "<style>h1 { color:#ffcc00; }</style><h1>Hello World!</h1>"
        >>> Pynliner().from_string(html).run()
        u'<h1 style="color: #fc0">Hello World!</h1>'
        """
        if not self.soup:
            self._get_soup()
        if not self.stylesheet:
            self._get_styles()

        previous_spacer = cssutils.ser.prefs.propertyNameSpacer
        cssutils.ser.prefs.propertyNameSpacer = u''
        self._apply_styles()
        cssutils.ser.prefs.propertyNameSpacer = previous_spacer

        self._get_output()
        self._clean_output()
        return self.output

    def _get_url(self, url):
        """Returns the response content from the given url
        """
        return urllib2.urlopen(url).read()

    def _get_soup(self):
        """Convert source string to BeautifulSoup object. Sets it to self.soup.

        If using mod_wgsi, use html5 parsing to prevent BeautifulSoup
        incompatibility.
        """
        # Check if mod_wsgi is running
        # - see http://code.google.com/p/modwsgi/wiki/TipsAndTricks
        try:
            from mod_wsgi import version
            self.soup = BeautifulSoup(self.source_string, "html5lib")
        except:
            self.soup = BeautifulSoup(self.source_string)

    def _get_styles(self):
        """Gets all CSS content from and removes all <link rel="stylesheet"> and
        <style> tags concatenating into one CSS string which is then parsed with
        cssutils and the resulting CSSStyleSheet object set to
        `self.stylesheet`.
        """
        self._get_external_styles()
        self._get_internal_styles()
        for style_string in self.extra_style_strings:
            self.style_string += style_string
        cssparser = cssutils.CSSParser(log=self.log)
        self.stylesheet = cssparser.parseString(self.style_string)

    def _get_external_styles(self):
        """Gets <link> element styles
        """
        if not self.style_string:
            self.style_string = u''
        else:
            self.style_string += u'\n'

        link_tags = self.soup.findAll('link', {'rel': 'stylesheet'})

        if not link_tags:
            return

        css_parser = cssutils.CSSParser(log=self.log)

        for tag in link_tags:
            url = tag['href']

            # Convert the relative URL to an absolute URL ready to pass to urllib
            base_url = self.relative_url or self.root_url
            url = urlparse.urljoin(base_url, url)

            content = self._get_url(url)

            # Sanity check. Is this even a CSS stylesheet? If not, then move on.
            if not css_parser.parseString(content).cssRules:
                continue

            self.style_string += content
            tag.extract()

    def _get_internal_styles(self):
        """Gets <style> element styles
        """
        if not self.style_string:
            self.style_string = u''
        else:
            self.style_string += u'\n'

        # Parse out the media queries and save them in one style block.
        if self.preserve_media_queries:
            css_parser = cssutils.CSSParser(log=self.log)

        style_tags = self.soup.findAll('style')
        for tag in style_tags:
            strings_and_comments = filter(lambda c: isinstance(c, basestring), tag.contents)

            if not self.preserve_media_queries:
                self.style_string += u'\n'.join(strings_and_comments) + u'\n'
                tag.extract()
            else:
                stylesheet = css_parser.parseString('\n'.join(strings_and_comments))
                media_stylesheet = cssutils.css.CSSStyleSheet()
                other_stylesheet = cssutils.css.CSSStyleSheet()

                for rule in stylesheet.cssRules:
                    if rule.type in _CSS_RULE_TYPES_TO_PRESERVE or \
                        (self.preserve_unknown_rules and rule.type == cssutils.css.CSSRule.UNKNOWN_RULE):
                        media_stylesheet.add(rule)
                    else:
                        other_stylesheet.add(rule)

                if media_stylesheet.cssRules:
                    new_tag = Tag(self.soup, 'style')
                    for attr_name, attr_value in tag.attrs:
                        new_tag[attr_name] = attr_value
                    new_tag.insert(0, u'\n' + media_stylesheet.cssText.decode('utf-8') + u'\n')
                    tag.replaceWith(new_tag)

                    self.style_string += other_stylesheet.cssText.decode('utf-8') + u'\n'
                else:
                    self.style_string += u'\n'.join(strings_and_comments) + u'\n'
                    tag.extract()

    def _get_specificity_from_list(self, lst):
        """
        Takes an array of ints and returns an integer formed
        by adding all ints multiplied by the power of 10 of the current index

        (1, 0, 0, 1) => (1 * 10**3) + (0 * 10**2) + (0 * 10**1) + (1 * 10**0) => 1001
        """
        return int(''.join(map(str, lst)))

    def _get_rule_specificity(self, rule):
        """
        For a given CSSRule get its selector specificity in base 10
        """
        return sum(map(self._get_specificity_from_list, (s.specificity for s in rule.selectorList)))

    def _apply_styles(self):
        """Steps through CSS rules and applies each to all the proper elements
        as @style attributes prepending any current @style attributes.
        """
        rules = self.stylesheet.cssRules.rulesOfType(1)
        elem_prop_map = {}
        elem_style_map = {}

        # build up a property list for every styled element
        for rule in rules:
            # select elements for every selector
            selectors = map(lambda s: s.strip(), rule.selectorText.split(','))
            elements = []

            for selector in selectors:
                try:
                    elements += select(self.soup, selector)
                except SelectorNotSupportedException, ex:
                    if self.ingore_unsupported_selectors:
                        pass
                    else:
                        raise

            # build prop_list for each selected element
            for elem in elements:
                if elem not in elem_prop_map:
                    elem_prop_map[elem] = []
                elem_prop_map[elem].append({
                    'specificity': self._get_rule_specificity(rule),
                    'props': rule.style.getProperties(),
                })

        # build up another property list using selector specificity
        for elem, props in elem_prop_map.items():
            if elem not in elem_style_map:
                elem_style_map[elem] = cssutils.css.CSSStyleDeclaration()
            # ascending sort of prop_lists based on specificity
            props = sorted(props, key=lambda p: p['specificity'])
            # for each prop_list, apply to CSSStyleDeclaration
            for prop_list in map(lambda obj: obj['props'], props):
                for prop in prop_list:
                    elem_style_map[elem][prop.name] = prop.value


        # apply rules to elements
        for elem, style_declaration in elem_style_map.items():
            if elem.has_key('style'):
                elem['style'] = u'%s;%s' % (style_declaration.cssText.replace('\n', ''), elem['style'])
            else:
                elem['style'] = style_declaration.cssText.replace('\n', '')
        
    def _get_output(self):
        """Generate Unicode string of `self.soup` and set it to `self.output`

        Returns self.output
        """
        self.output = unicode(self.soup)
        return self.output
    
    def _clean_output(self):
        """Clean up after BeautifulSoup's output.
        """
        if self.allow_conditional_comments:
            matches = re.finditer('(<!--\[if .+\].+?&lt;!\[endif\]-->)', self.output, re.S)
            for match in matches:
                comment = match.group()
                comment = comment.replace('&gt;', '>')
                comment = comment.replace('&lt;', '<')
                self.output = (self.output[:match.start()] + comment +
                               self.output[match.end():])


def fromURL(url, log=None):
    """Shortcut Pynliner constructor. Equivalent to:

    >>> Pynliner().from_url(someURL).run()

    Returns processed HTML string.
    """
    return Pynliner(log).from_url(url).run()

def fromString(string, log=None):
    """Shortcut Pynliner constructor. Equivalent to:

    >>> Pynliner().from_string(someString).run()

    Returns processed HTML string.
    """
    return Pynliner(log).from_string(string).run()
