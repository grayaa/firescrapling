"""Fixture HTML for offline media extractor tests."""

ANIME3RB_CATALOG = """
<!DOCTYPE html>
<html><head><title>Titles</title></head>
<body>
  <a href="/titles/one-piece"><img src="/img/op.jpg" alt=""/><span>One Piece</span></a>
  <a href="/titles/naruto"><img data-src="/img/naruto.jpg"/><span>Naruto</span></a>
  <a href="/titles/list">All titles</a>
</body></html>
"""

ANIME3RB_SERIES = """
<!DOCTYPE html>
<html><head>
  <title>One Piece</title>
  <meta property="og:image" content="https://cdn.example.com/op-poster.jpg"/>
</head>
<body>
  <h1>One Piece</h1>
  <a href="/titles/one-piece/episode/1">Episode 1</a>
  <a href="/titles/one-piece/episode/2">Episode 2</a>
</body></html>
"""

ANIME3RB_EPISODE = """
<!DOCTYPE html>
<html><head><title>One Piece Ep 1</title></head>
<body>
  <h1>One Piece — Episode 1</h1>
  <iframe src="https://player.example.com/embed/op1"></iframe>
  <script>
    var stream = "https://cdn.example.com/hls/op1/index.m3u8";
  </script>
</body></html>
"""

REELSHORT_CATALOG = """
<!DOCTYPE html>
<html><head><title>ReelShort</title></head>
<body>
  <a href="/movie/secret-love" title="Secret Love">
    <img src="/covers/secret.jpg" alt="Secret Love"/>
  </a>
  <a href="/movie/ceo-romance">
    <img data-src="/covers/ceo.jpg" alt="CEO Romance"/>
  </a>
</body></html>
"""

REELSHORT_SERIES = """
<!DOCTYPE html>
<html><head>
  <title>Secret Love</title>
  <meta property="og:image" content="https://cdn.reelshort.test/secret.jpg"/>
</head>
<body>
  <h1>Secret Love</h1>
  <a href="/movie/secret-love/episode/1">Ep 1</a>
  <a href="/movie/secret-love/episode/2">Ep 2</a>
</body></html>
"""

REELSHORT_EPISODE = """
<!DOCTYPE html>
<html><head><title>Secret Love Ep 1</title></head>
<body>
  <h1>Secret Love Episode 1</h1>
  <video>
    <source src="https://stream.reelshort.test/secret/ep1/master.m3u8" type="application/x-mpegURL"/>
  </video>
</body></html>
"""
