"""Shared HTML fixtures for unit and integration tests. Mirrors the fixture server pages."""

HTML_INDEX = """\
<!DOCTYPE html>
<html><head><title>Fixture Index</title></head>
<body>
<nav><p>Navigation sidebar noise that should be de-emphasized in main content mode.</p></nav>
<main>
  <h1>Welcome</h1>
  <p>Primary article body for testing.</p>
  <a href="/page2">Page two</a>
  <a href="relative">Relative link</a>
</main>
</body></html>"""

HTML_PAGE2 = """\
<!DOCTYPE html>
<html><head><title>Page Two</title></head>
<body><main><p>Second page content.</p><a href="/">Home</a></main></body></html>"""

HTML_RELATIVE = """\
<!DOCTYPE html>
<html><head><title>Relative</title></head>
<body><main><p>Relative path page.</p></main></body></html>"""

HTML_ROBOTS = """\
User-agent: *
Disallow: /secret/
"""
