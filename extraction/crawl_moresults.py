"""Download the consolidated olympiad results from moresults.org.

moresults.org is a client-side application: every page (competition, contestant,
country) is rendered in the browser from one data file, /data/olympiad_data.json.gz,
whose URL is referenced in the site's JavaScript bundle. Instead of rendering
~22,000 contestant pages listed in the sitemap, we locate that data file the same
way the browser does and download it once.

robots.txt (checked 2026-10-20): "User-agent: * / Allow: /".

Output: data/cache/moresults.org/olympiad_data.json.gz
"""
import re

from http_cache import CACHE_DIR, fetch

BASE = "https://moresults.org"
OUTPUT = CACHE_DIR / "moresults.org" / "olympiad_data.json.gz"


def find_data_url() -> str:
    home = fetch(BASE + "/", refresh=True).decode("utf-8")
    bundle_path = re.search(r'src="(/bundle\.[0-9a-f]+\.js)"', home).group(1)
    bundle = fetch(BASE + bundle_path, suffix=".js").decode("utf-8")
    version = re.search(r'const \w+="([0-9a-f]+)",\w+=\w+\?`/data/olympiad_data', bundle)
    data_path = "/data/olympiad_data.json.gz"
    return BASE + data_path + (f"?v={version.group(1)}" if version else "")


def main() -> None:
    sitemap = fetch(BASE + "/sitemap.xml", suffix=".xml").decode("utf-8")
    print(f"sitemap: {sitemap.count('<loc>')} URLs "
          f"({sitemap.count('/contestants/')} contestant pages)")

    url = find_data_url()
    print(f"data file: {url}")
    body = fetch(url, suffix=".json.gz")
    OUTPUT.write_bytes(body)
    print(f"saved {len(body) / 1e6:.1f} MB to {OUTPUT.relative_to(CACHE_DIR.parents[1])}")


if __name__ == "__main__":
    main()
