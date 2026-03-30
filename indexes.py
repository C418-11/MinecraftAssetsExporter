import json
import traceback

import requests
from bs4 import BeautifulSoup
from requests import ConnectTimeout

import config as cfg
from utils import show_warning

HEADER = {
    "User-Agent": "Minecraft Hash Resource File Indexes Fetcher"
}
URL = "https://zh.minecraft.wiki/w/%E6%95%A3%E5%88%97%E8%B5%84%E6%BA%90%E6%96%87%E4%BB%B6"


def fetch_indexes() -> dict[str, str] | None:
    try:
        resp = requests.get(URL, headers=HEADER, timeout=10)
    except ConnectTimeout as e:
        show_warning(f"无法更新版本映射信息，链接超时: {str(e)}")
        return None
    except Exception as e:
        traceback.print_exc()
        show_warning(f"无法更新版本映射信息，发生错误: {str(e)}")
        return None
    if resp.status_code != 200:
        show_warning(f"无法更新版本映射信息，状态码：{resp.status_code}")
        return None
    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table', class_='wikitable mw-collapsible')
    if not table:
        show_warning("无法找到版本映射信息")
        return None

    rows = table.find_all('tr')
    data: dict[str, str] = {}
    for row in rows[1:]:  # 跳过表头
        cells = row.find_all(['th', 'td'])
        if len(cells) >= 2:
            index_name = cells[0].get_text(strip=True)
            version_info = cells[1].get_text(strip=True)
            data[index_name] = version_info

    return data


def get_indexes() -> dict[str, str]:
    data = fetch_indexes()
    if data is not None:
        with open(cfg.INDEXES_CACHE_PATH, "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return data or get_cached_indexes()


def get_cached_indexes() -> dict[str, str]:
    if cfg.INDEXES_CACHE_PATH.exists():
        with open(cfg.INDEXES_CACHE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}
