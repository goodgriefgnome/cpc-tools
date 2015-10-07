#!/usr/bin/env python3

"""The options file should look like:

{
  "user": "cpcwebeditor",
  "passwd": "PASSWORD"
}
"""

import argparse
import html
import html.parser
import json
import os.path
import re
import requests

def PrependTableRow(original_html, contents):
  contents = ''.join('<td>{}</td>'.format(c) for c in contents)
  contents = '<tbody>\n<tr>{}</tr>'.format(contents)
  return contents.join(original_html.split('<tbody>', 1))


class FormParser(html.parser.HTMLParser):
  def __init__(self):
    super().__init__(convert_charrefs=True)
    self.data = {}
    self.__stack = []

  def _Last(self, tag):
    for t, attrs in reversed(self.__stack):
      if t == tag:
        return attrs

  def handle_starttag(self, tag, attrs):
    attrs = dict(attrs)
    self.__stack.append((tag, attrs))

    if tag == 'input':
      input_type = attrs.get('type', 'text').lower()
      if input_type in ('radio', 'checkbox') and not 'checked' in attrs:
        return
      if input_type in ('submit', 'image', 'reset', 'button', 'file'):
        return
      self.data[attrs['name']] = attrs.get('value', '')
    elif tag == 'option' and 'selected' in attrs:
      self.data[self._Last('select')['name']] = attrs.get('value', '')

  def handle_data(self, data):
    if not self.__stack:
      return

    tag, attrs = self.__stack[-1]
    if tag == 'option' and 'selected' in attrs and 'value' not in attrs:
      self.data[self._Last('select')['name']] = data
    elif tag == 'textarea':
      self.data[attrs['name']] = data

  def handle_endtag(self, tag):
    while tag != self.__stack.pop()[0]:
      pass


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--conf", default="~/.update-sermon-page.conf")
  args = parser.parse_args()
  conf_file = os.path.expanduser(args.conf)
  with open(conf_file) as f:
    conf = json.load(f)

  s = requests.Session()
  r = s.post('http://www.cpc.org.au/user',
             data={
                 'form_id': 'user_login',
                 'op': 'Log in',
                 'name': conf['user'],
                 'pass': conf['passwd']})
  edit_html = s.get('http://www.cpc.org.au/node/229/edit').text
  edit_html = re.sub(' xmlns="[^"]+"', '', edit_html, count=1)

  form = FormParser()
  form.feed(edit_html)
  form.close()

  file_re = re.compile('([0-9]{4,4})_([0-9]{2,2})_([0-9]{2,2})_([0-9]*).mp3')
  d = form.data['body[und][0][value]']
  while True:
    try:
      line = [s.strip() for s in input().split(' | ')]
      if not line: continue
      filename, topic, scripture, preacher = line
      filename = os.path.basename(filename)
      m = file_re.match(filename)
      year = m.group(1)
      month = m.group(2)
      day = m.group(3)
      time = m.group(4)

      d = PrependTableRow(d, [
          html.escape('{}/{}/{} {}:{}'.format(day, month, year, time[:-2], time[-2:])),
          html.escape(topic),
          html.escape(scripture),
          html.escape(preacher),
          '<a href="/sites/default/files/{}">mp3</a>'.format(html.escape(filename)),
          '&nbsp;'])

    except EOFError:
      break
    
  form.data['body[und][0][value]'] = d
  form.data['op'] = 'Save'

  r = s.post('http://www.cpc.org.au/node/229/edit', data=form.data)
